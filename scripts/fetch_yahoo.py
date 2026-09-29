"""Yahoo Fantasy 리그 데이터(팀, 순위, 주차별 로스터·매치업)를 받아 rosters.json 으로 저장.

환경변수: YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_REFRESH_TOKEN, YAHOO_LEAGUE_ID
GitHub Actions(.github/workflows/rosters.yml)에서 주기적으로 실행된다.
"""
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'
API = 'https://fantasysports.yahooapis.com/fantasy/v2/'
SLEEPER_PLAYERS = 'https://api.sleeper.app/v1/players/nfl'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rosters.json')
REDIRECT_URI = 'https://sirius4lee-dot.github.io/nfl-fantasy/callback.html'
BENCH = {'BN', 'IR', 'IR+', 'NA'}
# Yahoo 팀 약어 -> Sleeper(DEF id) 약어
TEAM_FIX = {'WSH': 'WAS', 'JAC': 'JAX', 'LA': 'LAR', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR'}


def env(name):
    v = os.environ.get(name, '').strip()
    if not v:
        sys.exit(f'환경변수 {name} 가 비어 있습니다. (GitHub Secrets/Variables 설정 확인)')
    return v


def http(url, data=None, headers=None, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:500]
            if e.code in (429, 500, 502, 503, 504) and i < retries - 1:
                time.sleep(5 * (i + 1))
                continue
            raise RuntimeError(f'HTTP {e.code} {url}\n{body}') from None
        except urllib.error.URLError:
            if i < retries - 1:
                time.sleep(5 * (i + 1))
                continue
            raise


def access_token():
    cid, secret = env('YAHOO_CLIENT_ID'), env('YAHOO_CLIENT_SECRET')
    auth = base64.b64encode(f'{cid}:{secret}'.encode()).decode()
    body = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': env('YAHOO_REFRESH_TOKEN'),
        'redirect_uri': REDIRECT_URI,
    }).encode()
    try:
        res = json.loads(http(TOKEN_URL, body, {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }))
    except RuntimeError as e:
        sys.exit(f'Yahoo 토큰 갱신 실패 — setup_yahoo.py 로 다시 인증하세요.\n{e}')
    return res['access_token']


def strip_ns(root):
    for el in root.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    return root


class Yahoo:
    def __init__(self, token):
        self.token = token

    def get(self, path):
        raw = http(API + path, headers={'Authorization': f'Bearer {self.token}'})
        time.sleep(0.3)
        return strip_ns(ET.fromstring(raw))


def txt(el, path, default=''):
    if el is None:
        return default
    f = el.find(path)
    return f.text.strip() if f is not None and f.text else default


def num(el, path):
    v = txt(el, path)
    try:
        return float(v)
    except ValueError:
        return None


def norm_name(s):
    s = re.sub(r"[.'’\-]", '', s.lower())
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'\s+', '', s)


def load_sleeper():
    players = json.loads(http(SLEEPER_PLAYERS))
    by_yahoo, by_name = {}, {}
    for pid, p in players.items():
        if p.get('yahoo_id'):
            by_yahoo[str(p['yahoo_id'])] = pid
        full = p.get('full_name') or f"{p.get('first_name', '')} {p.get('last_name', '')}"
        by_name.setdefault((norm_name(full), p.get('position')), pid)
    return by_yahoo, by_name


def map_player(pl, by_yahoo, by_name):
    yid = txt(pl, 'player_id')
    pos = txt(pl, 'display_position').split(',')[0]
    nfl = txt(pl, 'editorial_team_abbr').upper()
    nfl = TEAM_FIX.get(nfl, nfl)
    if pos == 'DEF':
        return nfl or None, pos, nfl
    sid = by_yahoo.get(yid) or by_name.get((norm_name(txt(pl, 'name/full')), pos))
    return sid, pos, nfl


def main():
    league_key = env('YAHOO_LEAGUE_ID')
    if '.l.' not in league_key:
        league_key = f'nfl.l.{league_key}'
    y = Yahoo(access_token())
    by_yahoo, by_name = load_sleeper()

    lg = y.get(f'league/{league_key}/standings').find('league')
    current_week = int(txt(lg, 'current_week', '1'))
    start_week = int(txt(lg, 'start_week', '1'))
    league = {
        'key': txt(lg, 'league_key'), 'id': txt(lg, 'league_id'), 'name': txt(lg, 'name'),
        'season': int(txt(lg, 'season', '0')), 'currentWeek': current_week,
        'numTeams': int(txt(lg, 'num_teams', '0')), 'scoringType': txt(lg, 'scoring_type'),
        'url': txt(lg, 'url'),
    }
    teams = []
    for t in lg.findall('standings/teams/team'):
        teams.append({
            'id': txt(t, 'team_id'), 'key': txt(t, 'team_key'), 'name': txt(t, 'name'),
            'manager': txt(t, 'managers/manager/nickname'),
            'logo': txt(t, 'team_logos/team_logo/url'),
            'rank': int(txt(t, 'team_standings/rank', '0') or 0),
            'wins': int(txt(t, 'team_standings/outcome_totals/wins', '0') or 0),
            'losses': int(txt(t, 'team_standings/outcome_totals/losses', '0') or 0),
            'ties': int(txt(t, 'team_standings/outcome_totals/ties', '0') or 0),
            'pf': num(t, 'team_standings/points_for'), 'pa': num(t, 'team_standings/points_against'),
            'roster': [],
        })
    key2id = {t['key']: t['id'] for t in teams}

    unmatched, weeks = set(), {}
    for wk in range(start_week, current_week + 1):
        sb = y.get(f'league/{league_key}/scoreboard;week={wk}').find('league/scoreboard')
        matchups = []
        status = ''
        for m in sb.findall('matchups/matchup'):
            status = txt(m, 'status') or status
            ts = m.findall('teams/team')
            if len(ts) != 2:
                continue
            a, b = ts
            matchups.append({
                'a': key2id.get(txt(a, 'team_key')), 'b': key2id.get(txt(b, 'team_key')),
                'pa': num(a, 'team_points/total'), 'pb': num(b, 'team_points/total'),
                'projA': num(a, 'team_projected_points/total'), 'projB': num(b, 'team_projected_points/total'),
                'winner': key2id.get(txt(m, 'winner_team_key')), 'tied': txt(m, 'is_tied') == '1',
            })
        lineups = {}
        for t in teams:
            ro = y.get(f"team/{t['key']}/roster;week={wk}").find('team/roster')
            starters, bench, roster = [], [], []
            for pl in ro.findall('players/player'):
                sid, pos, nfl = map_player(pl, by_yahoo, by_name)
                slot = txt(pl, 'selected_position/position')
                name = txt(pl, 'name/full')
                if not sid:
                    unmatched.add(f"{name} ({pos}, {nfl})")
                    sid = 'y' + txt(pl, 'player_id')
                (bench if slot in BENCH else starters).append(sid)
                roster.append({'sid': sid, 'name': name, 'pos': pos, 'nfl': nfl, 'slot': slot})
            lineups[t['id']] = {'starters': starters, 'bench': bench}
            if wk == current_week:
                t['roster'] = roster
        weeks[str(wk)] = {'status': status, 'matchups': matchups, 'lineups': lineups}
        print(f'week {wk}: {len(matchups)} matchups, status={status}')

    out = {'league': league, 'teams': teams, 'weeks': weeks, 'unmatched': sorted(unmatched)}
    # 내용이 바뀌었을 때만 파일을 새로 써서 불필요한 커밋을 막는다
    try:
        with open(OUT, encoding='utf-8') as f:
            old = json.load(f)
        old.pop('updatedAt', None)
        if old == out:
            print('변경 없음')
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    out = {'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), **out}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"저장: {len(teams)}팀, {len(weeks)}주차, 매칭 실패 {len(unmatched)}명")
    for u in sorted(unmatched):
        print('  매칭 실패:', u)


if __name__ == '__main__':
    main()
