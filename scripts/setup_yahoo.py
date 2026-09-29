"""Yahoo 인증을 한 번 진행해서 GitHub Secrets 에 키를 저장하는 설정 스크립트 (로컬에서 1회 실행).

    python scripts/setup_yahoo.py

필요: gh CLI 로그인 상태. 입력한 키는 화면/채팅에 남지 않고 GitHub Secrets 로만 저장된다.
"""
import base64
import getpass
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET

REPO = 'sirius4lee-dot/nfl-fantasy'
REDIRECT_URI = 'https://sirius4lee-dot.github.io/nfl-fantasy/callback.html'
AUTH_URL = 'https://api.login.yahoo.com/oauth2/request_auth'
TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'


def gh(*args, stdin=None):
    r = subprocess.run(['gh', *args], input=stdin, text=True, capture_output=True)
    if r.returncode:
        sys.exit(f'gh {args[0]} {args[1]} 실패: {r.stderr.strip()}')
    return r.stdout


def yget(path, token):
    req = urllib.request.Request('https://fantasysports.yahooapis.com/fantasy/v2/' + path,
                                 headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except urllib.error.HTTPError as e:
        msg = ' '.join(re.sub(r'<[^>]+>', ' ', e.read().decode('utf-8', 'replace')).split())
        sys.exit(f'Yahoo API 오류 (HTTP {e.code}): {msg[:300]}\n'
                 '→ developer.yahoo.com/apps 에서 이 앱의 API Permissions 에 "Fantasy Sports - Read" 가 '
                 '체크돼 있는지 확인하고, 스크립트를 처음부터 다시 실행해 주세요.')
    for el in root.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    return root


def main():
    print('=== Yahoo Fantasy 연동 설정 ===\n')
    client_id = input('1) Client ID 붙여넣기: ').strip()
    client_secret = getpass.getpass('2) Client Secret 붙여넣기 (입력해도 화면에 안 보여요): ').strip()
    if not (client_id and client_secret):
        sys.exit('입력값을 확인해 주세요.')

    url = AUTH_URL + '?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': REDIRECT_URI, 'response_type': 'code', 'language': 'en-us'})
    print('\n3) 브라우저에서 Yahoo 로그인 후 "Agree(동의)"를 누르세요.')
    print('   (리그에 참여 중인 Yahoo 계정으로 로그인해야 해요)')
    print('   창이 안 열리면 이 주소를 직접 여세요:\n   ' + url)
    webbrowser.open(url)
    code = input('\n4) 이동한 페이지에 표시된 코드를 붙여넣기: ').strip()

    auth = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    body = urllib.parse.urlencode({'grant_type': 'authorization_code', 'code': code,
                                   'redirect_uri': REDIRECT_URI}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={
        'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'토큰 발급 실패 (HTTP {e.code}): {e.read().decode("utf-8", "replace")}\n'
                 '코드는 몇 분 안에 만료되고 한 번만 쓸 수 있어요. 처음부터 다시 실행해 주세요.')

    # 진단: 토큰 정보(값 제외)와 사용자 정보가 필요 없는 기본 호출부터 확인
    print(f"\n[진단] 앱 ID {client_id[-6:]} · 토큰 항목: {', '.join(sorted(tok))}")
    game = yget('game/nfl', tok['access_token']).find('game')
    print(f"[진단] Fantasy API 기본 호출 OK: {game.findtext('name')} {game.findtext('season')}")

    # 로그인한 계정이 참여 중인 NFL 리그 목록에서 고르기
    root = yget('users;use_login=1/games;game_codes=nfl/leagues', tok['access_token'])
    leagues = []
    for lg in root.iter('league'):
        leagues.append({k: (lg.findtext(k) or '') for k in ('league_key', 'league_id', 'name', 'season', 'num_teams')})
    if not leagues:
        sys.exit('이 Yahoo 계정에서 참여 중인 NFL 리그를 찾지 못했어요. 리그에 참여한 계정으로 로그인했는지 확인해 주세요.')
    leagues.sort(key=lambda x: x['season'], reverse=True)
    print('\n참여 중인 NFL 리그:')
    for i, lg in enumerate(leagues, 1):
        print(f"  {i}. {lg['name']} ({lg['season']}, {lg['num_teams']}팀, ID {lg['league_id']})")
    pick = input(f'5) 연동할 리그 번호 [1-{len(leagues)}, 엔터 = 1]: ').strip() or '1'
    if not pick.isdigit() or not 1 <= int(pick) <= len(leagues):
        sys.exit('번호를 확인해 주세요.')
    league = leagues[int(pick) - 1]
    print(f"선택: {league['name']} ({league['league_key']})")

    print('\n6) GitHub Secrets 에 저장 중...')
    gh('secret', 'set', 'YAHOO_CLIENT_ID', '--repo', REPO, stdin=client_id)
    gh('secret', 'set', 'YAHOO_CLIENT_SECRET', '--repo', REPO, stdin=client_secret)
    gh('secret', 'set', 'YAHOO_REFRESH_TOKEN', '--repo', REPO, stdin=tok['refresh_token'])
    gh('variable', 'set', 'YAHOO_LEAGUE_ID', '--repo', REPO, '--body', league['league_key'])
    gh('workflow', 'run', 'rosters.yml', '--repo', REPO)
    print('완료! 리그 데이터 첫 업데이트를 시작했어요. 1~2분 뒤 페이지를 새로고침해 보세요.')


if __name__ == '__main__':
    main()
