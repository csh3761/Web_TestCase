# skmr API - Postman 설정 방법

skmr 로그인은 서버가 낸 일회용 챌린지에 맞춰 로그인 정보를 암호화해서 보내는 방식입니다.
고정된 JSON 본문으로는 로그인할 수 없고, 요청 직전에 실행되는 Pre-request Script 가 암호화를 대신 해줘야 합니다.

스크립트는 외부 패키지나 Node crypto 없이 Postman 에 기본 내장된 `crypto-js` 만 사용합니다.
(Postman 스크립트 환경에는 Node crypto 가 없고, npm 패키지(pm.require)도 환경에 따라 막혀 있습니다.)

## 세트 목록

컬렉션과 환경은 항상 번호가 같은 것끼리 짝입니다 (`N. ...postman_collection.json` + `N. ...postman_environment.json`).

예전에는 1~4까지 네 세트였지만, 2·3번(로그인+조회 5종 / 1·2 병합+업로드)의 기능이 전부 4번에 포함되어 있어
2·3번은 지우고 4번을 **2번으로** 정리했습니다. 지금은 두 세트만 있습니다.

| 세트 | 컬렉션 | 내용 | 상태 |
|---|---|---|---|
| 1 | `1. Login Test Copy` | 로그인/로그아웃/토큰 갱신/청크 업로드 등 원본 설계 (가장 풍부한 검증 문구) | 실서버 로그인 확인. 업로드 구간은 폴더 설정에 따라 다름 |
| **2** | `2. API 전체 루틴` | 명세(OpenAPI) 기반 자동 생성. 로그인부터 끝까지 82개 요청이 한 루틴으로 연결 (인증 흐름, 조회, 업로드 5개 API, 조회 확장 포함). 읽기 전용 76개 + 확인된 서버 오류 참고 5개 | Postman CLI 로 2회 연속 82/82 요청·109~145/109~145 검증 통과 (서버 상태에 따라 검증 개수 변동) |

처음 쓰신다면 **세트 2**를 추천합니다. 범위가 가장 넓고 실서버로 반복 검증했습니다. 세트 1은 원본 설계 참고용으로 남겨뒀습니다.

## 파일

| 파일 | 용도 |
|---|---|
| `N. ...postman_collection.json` / `N. ...postman_environment.json` | 세트별 컬렉션/환경 (위 표 참고) |
| `skmr_login_prerequest.js` | 로그인 암호화 Pre-request Script 단독본 (아래 "방법 2"로 직접 설정할 때 사용) |
| `Jenkinsfile` | Postman CLI 로 컬렉션을 CI 에서 돌리는 파이프라인 예시 (아래 CI 섹션 참고) |

## 방법 1. 파일 가져오기 (권장)

세트 2 기준입니다. 세트 1도 번호만 맞춰 똑같이 하면 됩니다.

1. Postman 왼쪽 위 Import 클릭, `2. API 전체 루틴.postman_collection.json`과 `2. API 전체 루틴.postman_environment.json`을 끌어다 놓습니다. 이전에 가져온 같은 번호의 컬렉션/환경이 있으면 삭제하고 다시 가져옵니다.
2. 오른쪽 위 환경 선택 칸에서 `DocSphere API 전체 루틴`을 고릅니다.
3. 환경 편집에서 `password`의 Current value 에 비밀번호를 입력하고 저장합니다. `username`/`base_url`/`loginChannel`은 이미 채워져 있습니다 (`username`은 `seungho.choi`).
4. 컬렉션 우클릭 > Run 으로 `1. 전체 API 루틴` 폴더를 실행합니다. 로그인부터 끝까지 한 번에 돕니다.
5. 나머지 변수(`folder_id`, `revision_code` 등)는 실행 중 앞 요청들이 자동으로 채웁니다. 직접 입력할 필요 없습니다.

## 방법 2. 직접 설정 (가져오기가 안 될 때)

1. 환경 만들기: Environments - Create. 이름은 skmr, 변수 3개를 추가합니다.

   | 변수 | 값 |
   |---|---|
   | base_url | https://skmr-api.ifns.work |
   | username | 계정 아이디 (예: seungho.choi) |
   | password | 비밀번호 |

2. 새 요청 만들기: 메서드 POST, 주소 `{{base_url}}/api/v1/auth/login`
3. Headers 탭에 3개를 추가합니다.

   | Key | Value |
   |---|---|
   | Accept | application/json |
   | X-Requested-With | XMLHttpRequest |
   | Content-Type | application/json |

4. Body 탭: raw, JSON 을 고르고 내용에 `{{loginBody}}` 만 입력합니다.
5. Scripts(또는 Pre-request Script) 탭에 skmr_login_prerequest.js 의 내용 전체를 붙여넣습니다. 이전 버전 스크립트가 있으면 전부 지우고 붙여넣습니다.
6. 저장 후 Send. 로그인이 성공하면 이후 요청에는 헤더 Accept, X-Requested-With 만 같은 값으로 넣으면 됩니다 (쿠키는 자동).

## 자주 막히는 점

| 증상 | 원인과 해결 |
|---|---|
| 로그인 응답이 VALIDATION_ERROR (요청 본문의 형식이 올바르지 않습니다) | Pre-request Script 가 오류로 중단돼도 Postman 은 요청을 그대로 보냅니다. 그러면 loginBody 가 비어 이 오류가 납니다. View - Show Postman Console 에서 스크립트 오류를 확인하세요 |
| ReferenceError: globalThis is not defined | 이전 버전 스크립트의 버그입니다 (Postman 스크립트 환경에는 globalThis 가 없음). 최신 skmr_login_prerequest.js 로 교체하세요 |
| 콘솔에 http://undefined/... 또는 http://{{base_url}}/... 로 요청한 기록 | 환경(skmr)이 선택되지 않았거나 base_url 이 비어 있습니다. 오른쪽 위 환경 선택과 변수 값을 확인하세요 |
| 콘솔의 'Using CryptoJS is deprecated' 경고, 'Cannot read properties of undefined (reading to/json)' | 앞의 경고는 무시해도 됩니다. 뒤의 두 줄은 로그인 요청이 실패해서 응답이 없을 때 테스트 스크립트가 내는 부수 오류이므로 위의 원인을 먼저 해결하세요 |
| Cannot find module 'crypto' / Cannot find package 'npm:...' | 이전 버전 스크립트입니다. 최신 skmr_login_prerequest.js (crypto-js 만 사용) 로 교체하세요 |
| 404 Not Found | 주소를 skmr.ifns.work(화면 서버)로 쓴 경우. API 는 skmr-api.ifns.work 입니다 |
| 400 또는 401 (로그인) | 챌린지는 120초 안에 써야 합니다. 요청을 다시 Send 하면 새 챌린지로 재시도됩니다. username/password 변수도 확인 |
| 로그인은 되는데 다른 요청이 401 | 쿠키가 저장되지 않은 경우. Cookies 관리에서 skmr-api.ifns.work 쿠키 3개(__Host-DocSphere-Access, __Host-DocSphere-Session, refresh_token) 확인 |
| 한참 뒤 401 | 토큰 유효시간 900초 경과. 5번 토큰 갱신 또는 1번 로그인을 다시 실행 |

## 검증 범위

로그인 스크립트는 실제 Postman 앱과 Postman CLI 양쪽에서 실서버 로그인 성공을 확인했습니다.
세트 2는 Postman CLI(`postman collection run`)로 실서버에 반복 실행해 전수 통과를 확인했습니다.

## CI (Jenkins)

`Jenkinsfile`이 Postman CLI로 컬렉션을 돌리는 예시입니다. 쓰기 전에 다음을 본인 환경에 맞게 바꿔야 합니다.

1. Postman 앱에서 원하는 세트의 컬렉션/환경을 Import 하고, Postman 클라우드 워크스페이스에 저장(동기화)합니다.
2. 컬렉션 우클릭 > Share 로 나오는 링크에서 `{workspaceId}-{collectionId}` 형태의 ID 를 확인해 `Jenkinsfile`의 `COLLECTION_ID`/`ENVIRONMENT_ID`에 넣습니다.
3. Postman 계정 설정 > API keys 에서 키를 발급하고, Jenkins Job 의 Credentials 에 **Secret text**로 등록합니다 (ID: `postman-api-key`). 평문 환경변수로 넘기지 않고 `withCredentials`로 바인딩합니다.
4. `tools { nodejs ... }` 줄은 Postman CLI 설치 자체에는 필요 없습니다. 다른 스테이지가 Node 를 안 쓰면 지워도 됩니다.
5. `--output postman-results` 로 결과를 YAML 파일로 남기고, `archiveArtifacts`로 실패 시에도 보관합니다.

콘솔 출력(Console Output)에 터미널과 같은 Pass/Fail 표가 그대로 찍힙니다. 그 구간을 복사해서 공유하면 결과를 같이 볼 수 있습니다.

## 대안

- Python 도구로 로그인 검증: `.venv\Scripts\python.exe -m apitest smoke`
- Python 도구로 API 전체 카탈로그(실제 응답값 포함) 수집: `.venv\Scripts\python.exe -m apitest.targets.skmr.probe_spec --out-dir docs/api`
- Python 도구로 동시 접근 과부하/스트레스: `.venv\Scripts\python.exe -m apitest survey --users 30 --iterations 10`
