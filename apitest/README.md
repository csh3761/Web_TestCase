# apitest - 순수 API 자동 테스트 (기능 / 부하)

브라우저 없이 HTTP API만으로 로그인부터 업로드까지 수행하는 테스트 환경. 가상 유저(VU)를 동시에 띄워
기능 점검, 동시 접근, 부하 측정을 같은 코드로 한다. 공유 `.venv` 를 사용한다.

```
apitest/
  core/       config(대상 설정) · client(httpx 비동기, 401 자동 갱신) · metrics(p50/p95/p99, 오류율)
              runner(VU 생명주기, 동시 시작 게이트, ramp-up) · report(콘솔/JSON)
  targets/skmr/
    crypto.py   로그인 암호화 (평문 구조/AAD 는 미확인 -> 이 파일만 수정)
    auth.py     challenge -> 암호화 -> login, refresh/재로그인
    api.py      엔드포인트 래퍼 + 청크 업로드 5개 API
    scenarios.py  smoke(기능) / login(동시 로그인·부하) / upload(동시 업로드·부하)
  mock/       로컬 모의 서버 (프레임워크 자체 검증용, 실제 서버 동작을 보증하지 않음)
```

## 실행 (저장소 루트에서)

```powershell
.venv\Scripts\python.exe -m apitest list
.venv\Scripts\python.exe -m apitest smoke                      # 기능 점검
.venv\Scripts\python.exe -m apitest login --users 30 --iterations 5 --relogin --ramp-up 5
.venv\Scripts\python.exe -m apitest upload --folder-id <ID> --execute --iterations 3 --chunk-concurrency 4
```

- `upload` 처럼 서버에 데이터를 만드는 시나리오는 `--execute` 가 있어야 실행된다.
- 업로드 파일명에는 `ct<시각>_` 접두사가 붙어 테스트 문서를 구분/정리할 수 있다.
- `--users` 가 계정 수보다 많으면 계정을 순환 배정한다 (같은 계정 다중 세션).
- 합성 데이터가 기본이고, `--source <폴더>` 로 로컬 문서(예: 다운로드)를 쓸 수 있다.
- 결과는 `reports/apitest_<시나리오>_<시각>.json` (요청 단위 샘플 포함).

## 설정

`config/skmr_api.example.json` 을 `config/skmr_api.json` 으로 복사해 사용 (git 제외).
**API 서버는 화면 서버(skmr.ifns.work)가 아니라 `https://skmr-api.ifns.work`** 이다 (화면 서버에 /api 로 요청하면 404).
2026-10-06 기준 API key 는 필요 없고 `Accept`, `X-Requested-With: XMLHttpRequest` 헤더를 쓴다. 인증은 쿠키.
만약 API key 가 다시 필요해지면 `"X-API-Key": "env:SKMR_API_KEY"` 처럼 환경변수로 받는다.
계정은 `config/skmr_accounts.json`. 임시로는 `--base-url`, `--header NAME=VALUE` 로도 지정 가능.

## 모의 서버로 프레임워크 점검

```powershell
.venv\Scripts\python.exe -m apitest.mock.skmr_mock --port 8099                       # (별도 터미널)
.venv\Scripts\python.exe -m apitest smoke --base-url http://127.0.0.1:8099
```
옵션: `--token-ttl 2`(만료/갱신 경로), `--fail-rate 0.25`(chunk 오류 주입), `--latency-ms`, `--api-key`.

## 검증 상태 (2026-10-06)

| 항목 | 상태 |
|---|---|
| 순수 API 로그인 (challenge, RSA-OAEP + AES-GCM) | **실서버 검증됨** - 3계정 동시, 세션 섞임 없음. 규격은 프론트엔드 JS 에서 확인 |
| 기능 점검 smoke (me, roots, children, documents) | **실서버 검증됨** |
| 동시 로그인 login (--relogin 포함) | **실서버 검증됨** (3유저 x 4회) |
| 청크 업로드 5개 API | 규격은 프론트엔드 JS 에서 확인해 반영, **실서버 업로드는 아직 미실행** (모의 서버로만 검증) |
| 업로드 대상 folderId | 목록의 `folderId` 필드 값(예: DOCBOXM_...) 사용. 화면용 `id` 와 다름 |
| 문서 목록 items 필드 | 미확인 (대상 폴더가 비어 있음) |

## 업로드 규격 (프론트엔드 번들 기준)

- create 본문: `operation("UPLOAD"), folderId, fileName, fileSize, mimeType, expectedFileSha256(hex)` + 선택 필드
- create 응답: `status`(COMPLETED면 동일 내용 중복 -> 청크 생략, UPLOADING), `uploadId, chunkSize, totalChunks, uploadedChunks`
- chunk: `PUT .../chunks/{i}`, 헤더 `Content-Type: application/octet-stream`, `X-Chunk-SHA256`(청크 hex)
- complete 후 상태가 ASSEMBLING, VERIFYING, READY_TO_STORE, STORING 을 거쳐 COMPLETED 가 될 수 있어 상태 조회로 대기
- 프론트엔드 동시성: 파일 2개, 파일당 청크 3개 (이 값이 `upload` 시나리오 기본값)
