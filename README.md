# NFL 판타지 기록장

Yahoo Fantasy Football 리그(**Icheon to SanJose world League**, ID 1430993, 10팀)를 위한 개인 기록 페이지예요.
NFL 전체 선수의 주차별 Fan Pts와 리그 10팀의 로스터·매치업·순위를 한 화면에서 보고, 선수별 메모를 남길 수 있어요.

- **기록장**: https://sirius4lee-dot.github.io/nfl-fantasy/
- **로스터 가져오기 안내 (북마클릿)**: https://sirius4lee-dot.github.io/nfl-fantasy/bookmarklet.html
- **저장소**: https://github.com/sirius4lee-dot/nfl-fantasy (공개, GitHub Pages로 배포)
- **메모 저장소**: https://github.com/sirius4lee-dot/nfl-fantasy-notes (비공개)
- **로컬 폴더**: `C:\Downloads\Claude\풋볼매니저`

내 팀: **Sangchun's Playbook** (Yahoo 팀 번호 9)

---

## 매주 할 일

| 언제 | 할 일 | 결과 |
|---|---|---|
| 경기가 끝난 뒤 | 기록장을 열거나 **업데이트** 버튼 | 모든 선수의 주차별 Fan Pts 갱신 (1시간이 지났으면 열 때 자동) |
| 한 주가 끝났을 때, 트레이드·웨이버 뒤 | Yahoo 리그 홈에서 북마크바의 **🏈 NFL 로스터 올리기** 클릭 | 10팀 로스터·선발/벤치·매치업 점수·순위가 GitHub에 자동 커밋 → 1~2분 뒤 모든 기기 반영 |
| 언제든 | 선수 이름 클릭 → **내 메모** 입력 | 자동 저장, PC·폰 동기화 |

기록장이 이상하게 보이면 먼저 **Ctrl+F5** (강력 새로고침).

---

## 화면 구성 (index.html)

- **전체 선수**: 주차별 Fan Pts 표. 포지션(QB/RB/WR/TE/FLEX/K/DEF)·NFL 팀·소유 팀 필터, 이름 검색, 열 클릭 정렬, CSV 내보내기.
  소유 열에 리그 팀 이름, 자유계약 선수는 **빨간색 FA**. 내 팀 선수는 노란 배경.
- **리그**: 10팀 순위·전적·득점/실점, 주차별 Yahoo 공식 점수(승리는 초록), 주차 선택 시 그 주 매치업 카드.
- **팀 로스터**: 팀을 골라 선수별 주차 점수. 흐린 칸은 벤치, 맨 아래에 "선발 합계(계산)"와 "Yahoo 공식 점수". **내 팀으로 설정** 가능.
- **관심 선수 ★**: 별표한 선수만 모아보기. 메모 동기화를 연결하면 PC·폰 같이 보임.
- **선수 창**: 주차별 상대·스탯 라인·점수 + **내 메모**. 메모가 있는 선수는 이름 옆 📝.
- **점수 규칙**: 기본값은 Yahoo 기본 Half PPR. 리그 실제 점수와 일치 확인함. 프리셋(PPR/Standard)과 항목별 수정 가능.
- **메모 동기화**: 메모 전용 토큰 연결, QR 코드로 휴대폰 연결.
- **로스터 파일**: 북마클릿 데이터를 파일로 가진 경우 이 기기에만 적용 (평소엔 안 씀).

---

## 데이터 흐름

```
Sleeper 공개 API ──(브라우저가 직접 호출)──> 선수 스탯 → Fan Pts 계산 (index.html)
Yahoo 리그 페이지 ──(북마클릿, 로그인된 브라우저)──> rosters.json ──(GitHub API 커밋)──> 저장소 → Pages
메모 ──(GitHub API, 메모 토큰)──> nfl-fantasy-notes/notes.json (비공개)
```

### 선수 점수: Sleeper API
- `https://api.sleeper.app/v1/state/nfl` → 현재 시즌·주차
- `https://api.sleeper.com/stats/nfl/{season}/{week}?season_type=regular&position[]=QB…` → 주차별 원본 스탯 + 선수 이름/팀
- 원본 스탯으로 Fan Pts를 **직접 계산** (`calcPts`). Yahoo 기본 규칙: 패스 25yd=1, 패스TD 4, INT -1, 러시/리시브 10yd=1, TD 6, 리셉션 0.5, 펌블로스트 -2, FG 0-39=3/40-49=4/50+=5, PAT 1, DEF 실점 구간 10/7/4/1/0/-1/-4.
- Sleeper 자체 점수와의 차이: 키커 실축 감점 없음, DEF 강제 펌블 점수 없음 (Yahoo 기본 규칙을 따른 것).
- 받은 스탯은 브라우저 localStorage(`ffm.cache.{season}`)에 캐시.

### 리그 로스터: 북마클릿 (`yahoo-sync.js`)
- **Yahoo Fantasy API는 2026-07-22부터 막혀서 못 씀** (모든 요청이 403 "This application is not authorized"). 새 앱은 권한 선택 불가, sports.yahoo.com/developer 에서 수동 심사 신청 필요.
- 대신 Yahoo에 로그인된 브라우저에서 북마클릿이 같은 사이트 페이지를 읽음:
  - `/f1/1430993` 리그 홈 → 순위표 `#standingstable`, 현재 주차, 리그 이름
  - `/f1/1430993/starters?week=N&startertab=team` → 10팀 전체의 슬롯(QB…BN/IR)과 선수 (`table#Tst-team-{팀번호}`, 선수 번호 `data-ys-playerid`)
  - `/f1/1430993?matchup_week=N&module=matchups&lhst=matchups` → 그 주 매치업(`li[data-target*="matchup?week="]`의 mid1/mid2, `.Fz-lg` 점수, `.F-shade` 예상 점수). 실패 시 다른 주소 2개로 재시도.
- 누를 때마다 **1주차부터 현재 주차까지 전부** 다시 읽음.
- Yahoo 페이지는 **파일 다운로드를 막음** → GitHub API(`PUT contents/rosters.json`)로 직접 커밋. 토큰이 없거나 실패하면 "데이터 복사 → GitHub 편집 화면에 붙여넣기" 수동 방법을 안내.
- 기록장은 Yahoo 선수를 **이름+포지션**으로 Sleeper 선수와 연결 (DEF는 팀 약어). 173명 전원 연결 확인.

### rosters.json 형식 (북마클릿 출력)
```
{ source, updatedAt, errors[],
  league: { id, name, season, currentWeek, numTeams },
  players: { [yahooId]: { name, pos, nfl } },
  teams: [ { id, name, manager, rank, wins, losses, ties, pf, pa, roster: [ { yid, slot } ] } ],
  weeks: { [N]: { status, matchups: [ { a, b, pa, pb, projA, projB, winner, tied } ],
                  lineups: { [teamId]: { starters: [yid], bench: [yid] } } } } }
```

### 메모: notes.json (비공개 저장소)
- `{ [Sleeper 선수id]: { t: 메모, u: 수정시각(ms), n: 이름 } }`. 지운 메모도 `t: ''`로 남겨서 삭제가 동기화됨.
- 입력 1.5초 뒤 자동 저장, 선수별로 **나중에 수정한 쪽**이 이김. 409 충돌 시 다시 받아 합친 뒤 재시도.
- 탭으로 돌아올 때 다른 기기 메모를 다시 불러옴.
- QR 링크 `…/nfl-fantasy/#token=…` 로 휴대폰 연결 (열면 토큰 저장 후 주소에서 지움).

---

## 토큰 (GitHub fine-grained, 둘 다 366일 만료)

| 이름 | 권한 | 들어 있는 곳 | 만료되면 |
|---|---|---|---|
| **nfl-roster** | nfl-fantasy · Contents 읽기/쓰기 | 북마크바의 🏈 NFL 로스터 올리기 버튼 안 | 새로 만들고 bookmarklet.html 에서 버튼 다시 만들기 |
| **nfl-notes** | nfl-fantasy-notes · Contents 읽기/쓰기 | 각 기기 브라우저 localStorage (`ffm.notesToken`) | 새로 만들고 메모 동기화에서 다시 연결 + 폰은 QR |

- 토큰은 저장소에 절대 넣지 않음. 북마크·QR은 다른 사람과 공유 금지.
- 관리: https://github.com/settings/personal-access-tokens

---

## 파일

| 파일 | 내용 |
|---|---|
| `index.html` | 기록장 전체 (HTML/CSS/JS 한 파일) |
| `yahoo-sync.js` | 북마클릿 본체. `'__GH_TOKEN__'` 자리에 토큰이 들어간 버전이 개인 버튼이 됨 |
| `bookmarklet.html` | 북마클릿 설치·토큰 확인·콘솔 실행 안내 페이지 |
| `rosters.json` | 북마클릿이 커밋하는 리그 데이터 |
| `.gitignore` | 저장했던 Yahoo 페이지(roster*.html, matchup.html — 이름·이메일 포함) 제외 |

---

## 겪었던 문제와 해결

- **Yahoo API 403** → 앱 권한·계정 문제가 아니라 Yahoo가 API를 막은 것. 북마클릿 방식으로 전환. (API 연동 코드 `scripts/`, 워크플로는 삭제, git 기록에 남아 있음)
- **북마클릿 다운로드가 안 됨** → Yahoo 페이지가 다운로드를 막음. GitHub API 자동 커밋으로 해결.
- **매치업이 매주 같은 팀·틀린 점수로 보임** → 예전에 브라우저에 불러온 테스트 파일이 미래 날짜라 진짜 데이터를 가림. 로컬 파일은 "불러온 시각"으로 비교하고, GitHub 데이터가 더 새로우면 자동 삭제하도록 수정.
- **GitHub Pages 404** → 배포 직후 1분 정도는 404가 나올 수 있음. Ctrl+F5.
- GitHub 웹에서 커밋할 때 제목이 자동 제안("Update print statement…")으로 들어갈 수 있음. 내용엔 문제 없음.

---

## 앞으로 할 수 있는 것

- Yahoo가 API 신청을 승인하면 완전 자동(GitHub Actions 주기 수집)으로 전환 가능. 예전 코드는 git 기록의 `scripts/fetch_yahoo.py`.
- (완료) 관심 선수 ★도 메모와 같은 notes.json 에 `star:{선수id}` 로 저장되어 PC·폰 동기화됨.
