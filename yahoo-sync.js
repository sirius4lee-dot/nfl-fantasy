// Yahoo 판타지 리그 페이지에서 실행하는 북마클릿 본체.
// 로그인된 브라우저 안에서 같은 사이트의 페이지만 읽어 rosters.json 을 만든다 (로그인 정보는 밖으로 나가지 않음).
(async () => {
  const UPLOAD_URL = 'https://github.com/sirius4lee-dot/nfl-fantasy/upload/main';
  const BENCH = ['BN', 'IR', 'IR+', 'NA'];
  const m = location.pathname.match(/\/f1\/(\d+)/);
  if (location.hostname !== 'football.fantasysports.yahoo.com' || !m) {
    alert('Yahoo 판타지 풋볼 리그 페이지(football.fantasysports.yahoo.com/f1/...)에서 눌러 주세요.');
    return;
  }
  const lid = m[1], base = `/f1/${lid}`;

  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;z-index:2147483647;top:16px;right:16px;background:#1a1e24;color:#fff;' +
    'padding:14px 16px;border-radius:10px;font:14px/1.5 system-ui,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,.4);max-width:340px';
  document.body.appendChild(box);
  const say = html => { box.innerHTML = html; };

  const get = async url => {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
    let t = await r.text();
    if (/^\s*[{[]/.test(t)) { // 일부 모듈은 JSON 안에 HTML 을 담아 돌려준다
      try {
        const parts = [];
        (function walk(o) {
          if (typeof o === 'string') { if (o.includes('<')) parts.push(o); }
          else if (o && typeof o === 'object') Object.values(o).forEach(walk);
        })(JSON.parse(t));
        t = parts.join('');
      } catch { /* HTML 그대로 사용 */ }
    }
    return new DOMParser().parseFromString(t, 'text/html');
  };
  const num = s => { const v = parseFloat(String(s ?? '').replace(/[^\d.\-]/g, '')); return Number.isNaN(v) ? null : v; };
  const text = el => (el?.textContent || '').replace(/\s+/g, ' ').trim();

  try {
    say('리그 정보 읽는 중…');
    const home = await get(base);
    const leagueName = (home.title || document.title).split(' | ')[0].trim();
    const season = +(text(home.body).match(/Fantasy Football (20\d\d)/)?.[1] || new Date().getFullYear());
    let cur = num(home.querySelector('select[data-module="#matchupweek"] option[selected]')?.textContent) ||
      num(text(home.body).match(/Week (\d+) Matchups/)?.[1]);

    const teams = [...home.querySelectorAll('#standingstable tbody tr')].map(tr => {
      const id = (tr.dataset.target || tr.querySelector('a[href*="/f1/"]')?.getAttribute('href') || '').match(/\/f1\/\d+\/(\d+)/)?.[1];
      const tds = tr.querySelectorAll('td');
      const [w, l, t] = text(tr.querySelector('.Tst-wlt')).split('-').map(Number);
      return {
        id, name: text(tr.querySelector('.Tst-manager a.F-reset') || [...tr.querySelectorAll('a')].pop()),
        manager: '', rank: num(text(tds[0])) || 0, wins: w || 0, losses: l || 0, ties: t || 0,
        pf: num(text(tds[3])), pa: num(text(tds[4])), roster: [],
      };
    }).filter(t => t.id);
    if (!teams.length) throw new Error('순위표를 찾지 못했어요. 리그 홈 화면에서 다시 시도해 주세요.');

    if (!cur) { // 매치업 주차를 못 찾으면 로스터 페이지의 선택 주차 사용
      const st = await get(`${base}/starters`);
      cur = num(st.querySelector('option[selected]')?.textContent) || 1;
    }

    const players = {}, weeks = {};
    for (let w = 1; w <= cur; w++) {
      say(`W${w} / ${cur} 주차 로스터·매치업 읽는 중…`);
      const [st, mu] = await Promise.all([
        get(`${base}/starters?week=${w}&startertab=team`),
        get(`${base}?matchup_week=${w}&module=matchups&lhst=matchups`),
      ]);
      const lineups = {};
      for (const table of st.querySelectorAll('table[id^="Tst-team-"]')) {
        const tid = table.id.split('-').pop();
        const lu = { starters: [], bench: [], slots: [] };
        for (const tr of table.querySelectorAll('tbody tr')) {
          const a = tr.querySelector('a[data-ys-playerid]');
          if (!a) continue;
          const yid = a.dataset.ysPlayerid;
          const slot = text(tr.cells[0]);
          const tp = [...tr.querySelectorAll('.ysf-player-name .Fz-xxs')].map(text).find(s => / - /.test(s)) || '';
          const [nfl, pos] = tp.split(' - ');
          players[yid] = { name: a.getAttribute('title') || text(a), pos: (pos || '').split(',')[0], nfl: (nfl || '').toUpperCase() };
          (BENCH.includes(slot) ? lu.bench : lu.starters).push(yid);
          lu.slots.push([yid, slot]);
        }
        lineups[tid] = lu;
      }

      let lis = [...mu.querySelectorAll('li[data-target*="matchup?week="]')];
      if (!lis.some(li => li.dataset.target.includes(`week=${w}&`))) {
        const full = await get(`${base}?matchup_week=${w}`);
        lis = [...full.querySelectorAll('li[data-target*="matchup?week="]')];
      }
      lis = lis.filter(li => li.dataset.target.includes(`week=${w}&`));
      const matchups = lis.map(li => {
        const q = new URLSearchParams(li.dataset.target.split('?')[1]);
        const pts = [...li.querySelectorAll('.Fz-lg')].map(e => num(text(e)));
        const proj = [...li.querySelectorAll('.F-shade')].map(text).filter(s => /^-?\d+(\.\d+)?$/.test(s)).map(Number);
        const a = q.get('mid1'), b = q.get('mid2'), pa = pts[0] ?? null, pb = pts[1] ?? null;
        const done = w < cur;
        return { a, b, pa, pb, projA: proj[0] ?? null, projB: proj[1] ?? null,
          winner: done && pa != null && pb != null && pa !== pb ? (pa > pb ? a : b) : null, tied: done && pa === pb };
      });
      const started = matchups.some(x => (x.pa || 0) + (x.pb || 0) > 0);
      weeks[w] = { status: w < cur ? 'postevent' : started ? 'midevent' : 'preevent', matchups, lineups };
    }

    for (const t of teams) {
      t.roster = (weeks[cur]?.lineups[t.id]?.slots || []).map(([yid, slot]) => ({ yid, slot }));
    }
    for (const wk of Object.values(weeks)) for (const lu of Object.values(wk.lineups)) delete lu.slots;

    const out = {
      source: 'yahoo-bookmarklet', updatedAt: new Date().toISOString(),
      league: { id: lid, name: leagueName, season, currentWeek: cur, numTeams: teams.length },
      players, teams, weeks,
    };
    const blob = new Blob([JSON.stringify(out)], { type: 'application/json' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'rosters.json' });
    document.body.appendChild(a); a.click(); a.remove();

    say(`<b>완료!</b> ${teams.length}팀 · ${cur}개 주차 · 선수 ${Object.keys(players).length}명<br>` +
      `<b>rosters.json</b> 파일이 다운로드됐어요.<br><br>` +
      `<a href="${UPLOAD_URL}" target="_blank" style="color:#b388ff;font-weight:700">① GitHub에 올리기 (파일 끌어놓기 → Commit)</a><br>` +
      `<span style="opacity:.7;font-size:12px">또는 기록장의 ‘로스터 파일’ 버튼으로 이 기기에만 바로 적용</span><br><br>` +
      `<button style="all:revert;cursor:pointer" onclick="this.closest('div').remove()">닫기</button>`);
  } catch (e) {
    say(`<b>실패:</b> ${String(e.message || e).replace(/</g, '&lt;')}<br><br>` +
      `<button style="all:revert;cursor:pointer" onclick="this.closest('div').remove()">닫기</button>`);
  }
})();
