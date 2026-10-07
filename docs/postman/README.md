# skmr API - Postman 설정 방법

skmr 로그인은 서버가 낸 일회용 챌린지에 맞춰 로그인 정보를 암호화해서 보내는 방식입니다.
고정된 JSON 본문으로는 로그인할 수 없고, 요청 직전에 실행되는 Pre-request Script 가 암호화를 대신 해줘야 합니다.

스크립트는 외부 패키지나 Node crypto 없이 Postman 에 기본 내장된 `crypto-js` 만 사용합니다.
(Postman 스크립트 환경에는 Node crypto 가 없고, npm 패키지(pm.require)도 환경에 따라 막혀 있습니다.)

## 파일

| 파일 | 용도 |
|---|---|
| skmr_api.postman_collection.json | 요청 5개 (로그인, me, 루트 폴더, 문서 목록, 토큰 갱신) |
| skmr.postman_environment.json | 환경 변수 (base_url, username, password) |
| skmr_login_prerequest.js | 로그인 암호화 스크립트 단독본 |

## 방법 1. 파일 가져오기 (권장)

1. Postman 왼쪽 위 Import 클릭, JSON 파일 2개(collection, environment)를 끌어다 놓습니다. 이전에 가져온 컬렉션이 있으면 삭제하고 다시 가져옵니다.
2. 오른쪽 위 환경 선택 칸에서 skmr 를 고릅니다.
3. 환경 편집에서 password 의 Current value 에 비밀번호를 입력하고 저장합니다.
4. 컬렉션의 "1. 로그인 (암호화)" 를 Send 합니다. 200 과 "로그인에 성공했습니다." 가 나오면 성공입니다.
5. 이어서 2~5번 요청을 Send 합니다. 로그인 쿠키가 Postman Cookie Jar 에 저장되어 자동으로 인증됩니다.

## 방법 2. 직접 설정 (가져오기가 안 될 때)

1. 환경 만들기: Environments - Create. 이름은 skmr, 변수 3개를 추가합니다.

   | 변수 | 값 |
   |---|---|
   | base_url | https://skmr-api.ifns.work |
   | username | 계정 아이디 (예: new1) |
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

스크립트는 Postman 과 같은 조건(Node crypto 없음, Buffer 없음, require 는 crypto-js 3.1.9-1 만 허용)의 하네스에서 실행해,
실서버 로그인이 200 으로 연속 3회 통과하는 것까지 확인했습니다. Postman 앱 안에서의 실행은 직접 확인하지 못했습니다.

## 대안

- Python 도구로 로그인 검증: `.venv\Scripts\python.exe -m apitest smoke`
