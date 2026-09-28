# skmr.ifns.work REST API 목록 (파라미터 + 타입/허용값 포함)

DOM 자동 클릭 스캔(로그인 → 최상위 22개 기능 → 사이드바 트리 전개) 중 발생한 실제 XHR/fetch 요청을
`page.on("response")`로 가로채서 수집. resource_type이 xhr/fetch인 것만 걸러서 정적 리소스는 자동 제외됨.
총 76건 호출 / 고유 (method, path) 31개.

원본(호출별 상세, 상태코드, 발생시킨 액션 매핑): `reports/skmr_deep_menu_discovery.json`의
`api_endpoint_summary` / `all_captured_api_calls` / 각 `explorations[].api_calls`.
정리용 원본 덤프: `reports/api_endpoints_with_params.txt`

> **주의**: 각 API는 이번 스캔에서 1~수회만 호출됐다. 타입/허용값/필수여부/기본값은 실제 관측된 값
> 기준으로 추정한 것이며, 관측되지 않은 케이스(enum의 다른 값, 옵션 파라미터 생략 시 동작 등)는
> `(추정)`으로 표시했다. 실제 API 정의서로 확정하기 전에 백엔드 스펙(스웨거 등)이나 추가 호출로
> 교차 확인 필요.
> Response는 배열일 경우 앞 2건만 샘플로 남기고 잘랐음. `password`/`token`/`secret` 등이
> 들어간 키는 값이 `***MASKED***`로 마스킹됨.
>
> 표 컬럼: `No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고`

---

## 1. 인증 (AUTH)

### GET /api/v1/auth/login/challenge
Query: 없음

Response:
```json
{
  "challengeId": "ffc5767e-3f2c-4acf-9358-685e623750ea",
  "nonce": "ySVdyG8pj3v2Ot5DMJA--ryVzsVbYOY4OkWS6ZwL0g0",
  "keyId": "eShXoDt01w-8yFcs",
  "publicKey": "-----BEGIN PUBLIC KEY-----\n...(RSA PEM)...",
  "algorithm": "RSA-OAEP-256+A256GCM",
  "expiresIn": 120
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | challengeId | string | 필수 | 없음 | UUID v4 형식 | 챌린지 식별자 | 다음 요청(`/auth/login`)에 그대로 포함해서 전송 |
| 2 | nonce | string | 필수 | 없음 | base64url, 가변 길이 | 1회성 난수 | 재사용 방지용 |
| 3 | keyId | string | 필수 | 없음 | 영숫자+`-`/`_`, 16자 관측 | 서버측 RSA 키 식별자 | |
| 4 | publicKey | string | 필수 | 없음 | PEM 형식(`-----BEGIN PUBLIC KEY-----`로 시작) | 로그인 정보 암호화용 RSA 공개키 | |
| 5 | algorithm | string (enum) | 필수 | 없음 | 관측값: `RSA-OAEP-256+A256GCM` | 암호화 알고리즘 | 하이브리드 암호화(RSA로 AES키 감싸고 AES-GCM으로 본문 암호화) |
| 6 | expiresIn | integer | 필수 | 없음 | 초 단위, 관측값 `120` | 챌린지 유효시간 | |

비고: 로그인 폼 진입 시 서버가 매번 새 챌린지를 발급.

### POST /api/v1/auth/login
Query: 없음

Request Body:
```json
{
  "challengeId": "(challenge 응답의 challengeId 그대로)",
  "keyId": "(challenge 응답의 keyId 그대로)",
  "encryptedKey": "(RSA로 암호화한 AES 키, base64)",
  "iv": "(base64)",
  "ciphertext": "(base64, AES-GCM 암호문)"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | challengeId | string | 필수 | 없음 | UUID v4 | challenge 응답값 재사용 | |
| 2 | keyId | string | 필수 | 없음 | challenge 응답의 keyId와 동일 | | |
| 3 | encryptedKey | string | 필수 | 없음 | base64, 길이 344자 관측 | RSA로 암호화한 AES 키 | RSA-2048 암호문 추정 |
| 4 | iv | string | 필수 | 없음 | base64, 16자 관측 | GCM용 nonce | 디코드 시 12바이트 추정 |
| 5 | ciphertext | string | 필수 | 없음 | base64, 가변 길이 | AES-GCM 암호문 | 복호화하면 실제 아이디/비밀번호 JSON으로 추정(미확인) |

Response:
```json
{
  "message": "로그인에 성공했습니다.",
  "tokenType": "***MASKED***",
  "expiresIn": 240,
  "username": "new1",
  "loginChannel": "WEB"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | message | string | 필수 | 없음 | 자유 텍스트 | 성공 메시지 | 실패 시 다른 메시지로 추정(미확인) |
| 2 | tokenType | string | 필수 | 없음 | 마스킹됨 — 관측 불가 | 토큰 타입 | `Bearer` 등으로 추정, 실제 토큰값은 응답 바디에 없음(헤더/쿠키 추정) |
| 3 | expiresIn | integer | 필수 | 없음 | 초 단위, 관측값 `240` | 세션 만료 시간 | |
| 4 | username | string | 필수 | 없음 | 로그인 아이디 그대로 | 로그인한 아이디 | |
| 5 | loginChannel | string (enum) | 필수 | 없음 | 관측값: `WEB` | 로그인 채널 | 모바일 채널 등 다른 값 존재 가능(추정) |

비고: 평문 아이디/비번을 그대로 보내지 않는 challenge-response 암호화 로그인.

### GET /api/v1/auth/me
Query: 없음

Response:
```json
{
  "username": "new1",
  "loginChannel": "WEB",
  "userNm": "user_1",
  "departmentNames": "QnA",
  "enterpriseAdmin": false,
  "workboxAdmin": true
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | username | string | 필수 | 없음 | 로그인 아이디 | 현재 로그인한 사용자 아이디 | |
| 2 | loginChannel | string (enum) | 필수 | 없음 | 관측값: `WEB` | 로그인 채널 | |
| 3 | userNm | string | 필수 | 없음 | 자유 텍스트 | 표시 이름 | |
| 4 | departmentNames | string | 필수 | 없음 | 자유 텍스트 | 소속 부서명 | 콤마 구분 다중부서 가능성(미확인) |
| 5 | enterpriseAdmin | boolean | 필수 | 없음 | `true`/`false` | 전사관리자 권한 여부 | new1은 `false` |
| 6 | workboxAdmin | boolean | 필수 | 없음 | `true`/`false` | 업무함 관리자 권한 여부 | new1은 `true`(그런데 메뉴는 안 열림 — 원인 미확인) |

### POST /api/v1/auth/refresh
Query: 없음

Response (`401`):
```json
{
  "message": "리프레시 토큰이 없습니다. 다시 로그인해 주세요.",
  "code": "REFRESH_MISSING"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | message | string | 필수 | 없음 | 자유 텍스트 | 에러 메시지 | |
| 2 | code | string (enum) | 필수 | 없음 | 관측값: `REFRESH_MISSING` | 에러 코드 | 다른 에러 코드 존재 가능(추정) |

비고: 정상 세션(리프레시 토큰 보유)에서의 200 응답 스키마는 못 잡음 — 재확인 필요.

---

## 2. 메뉴/공통 (MENU/COMMON)

### GET /api/v1/menus/top
Query: 없음

Response:
```json
[
  { "menuCode": "MENU_000000000000020", "workboxId": "dept", "menuName": "부서문서함|TEAM WORK", "displayName": "부서문서함", "menuUrl": "-", "menuIcon": "", "menuSort": 2 },
  { "menuCode": "MENU_000000000000120", "workboxId": "project", "menuName": "그룹문서함|PROJECT WORK", "displayName": "그룹문서함", "menuUrl": "-", "menuIcon": "", "menuSort": 3 }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | menuCode | string | 필수 | 없음 | `MENU_` + 15자리 숫자 | 메뉴 고유 코드 | |
| 2 | workboxId | string (enum) | 필수 | 없음 | 관측값: `dept`, `project` | 업무함 종류 식별자 | `personal` 등 다른 값 존재 가능(추정) |
| 3 | menuName | string | 필수 | 없음 | `"한글명\|영문명"` 파이프(`\|`) 구분 | 메뉴 전체 표기 | |
| 4 | displayName | string | 필수 | 없음 | 자유 텍스트 | 화면 표시용 한글명 | |
| 5 | menuUrl | string | 필수 | 없음 | 관측값 `-` | 메뉴 URL | placeholder, 실질적으로 미사용 추정 |
| 6 | menuIcon | string | 필수 | `""` | 관측값 `""`(빈 문자열) | 아이콘 식별자 | |
| 7 | menuSort | integer | 필수 | 없음 | 정렬 순서, 관측값 2, 3 | 정렬 순번 | |

### GET /api/v1/common/doc-types
Query:
```json
{ "boxId": "root_vgCXaNZ1pC2QKLbfMkJLBw" }
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | boxId | string | 필수(추정) | 없음 | `root_` + 22자 base64url ID | 조회 대상 문서함 루트 ID | |

Response:
```json
{
  "documentTypes": [
    { "commoncodeId": "SECRET_DOC", "commoncodeNm": "비밀문서" }
  ],
  "securityLevels": [
    { "commoncodeId": "H4", "commoncodeNm": "Secret" },
    { "commoncodeId": "H5", "commoncodeNm": "Top Secret" }
  ],
  "retentionYears": [
    { "commoncodeId": "1-DOC", "commoncodeNm": "1Y" },
    { "commoncodeId": "3-DOC", "commoncodeNm": "3Y" }
  ]
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | documentTypes[].commoncodeId | string (enum) | 필수 | 없음 | 관측값: `SECRET_DOC` | 문서유형 코드 | 1건만 관측, 다른 코드 존재 가능(추정) |
| 2 | documentTypes[].commoncodeNm | string | 필수 | 없음 | 자유 텍스트 | 문서유형 코드의 한글명 | |
| 3 | securityLevels[].commoncodeId | string (enum) | 필수 | 없음 | 관측값: `H4`, `H5` | 보안등급 코드 | `H1`~`H3` 등 하위 등급 존재 가능(추정) |
| 4 | securityLevels[].commoncodeNm | string | 필수 | 없음 | 관측값: `Secret`, `Top Secret` | 보안등급 한글명 | |
| 5 | retentionYears[].commoncodeId | string (enum) | 필수 | 없음 | 관측값: `1-DOC`, `3-DOC` | 보존연한 코드 | 총 7건 중 2건만 샘플 — 나머지 값 미확인 |
| 6 | retentionYears[].commoncodeNm | string | 필수 | 없음 | 관측값: `1Y`, `3Y` | 보존연한 표시명 | |

---

## 3. 폴더/문서 탐색 (EXPLORER)

### GET /api/v1/folders/roots
Query: 없음

Response:
```json
[
  { "id": "root_vgCXaNZ1pC2QKLbfMkJLBw", "name": "바로가기", "parentFolderId": null, "gubun": "Q", "encryption_policy": "PLAIN" },
  { "id": "root_dDcGLsooazVf2vEWPpYcog", "name": "부서문서함", "parentFolderId": null, "gubun": "D", "encryption_policy": "PLAIN" }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | id | string | 필수 | 없음 | `root_` + 22자 base64url ID | 루트 폴더 ID | |
| 2 | name | string | 필수 | 없음 | 관측값: `바로가기`, `부서문서함`(`그룹문서함` 추정) | 루트 폴더명 | 총 3건 중 2건만 샘플 |
| 3 | parentFolderId | null | 필수 | `null` | 항상 `null`로 추정 | 상위 폴더 ID | 루트라서 부모 없음 |
| 4 | gubun | string (enum) | 필수 | 없음 | 관측값: `Q`, `D`(`G` 추정) | 폴더 구분 코드 | Quicklink/Department/Group 약자 추정 |
| 5 | encryption_policy | string (enum) | 필수 | 없음 | 관측값: `PLAIN` | 암호화 정책 | `ENCRYPTED` 등 다른 값 존재 가능(추정) |

### GET /api/v1/folders/{folderId}/children
Path 변수:

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | folderId | string | 필수 | 없음 | `fld_...` / `fldv_...` / `root_...` 세 프리픽스 관측 | 조회할 폴더 ID | URL 경로에 포함 |

Query:
```json
{
  "gubun": "D",
  "trash": "true"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | gubun | string (enum) | 필수 | 없음 | 관측값: `D`, `Q`, `G`, `U` | 폴더 구분 필터 | 모든 호출에 존재 |
| 2 | trash | boolean(문자열) | 선택 | `false`(추정) | `"true"` 관측, 생략 시 기본 조회 | 휴지통 하위 조회 여부 | `true`일 때만 휴지통 항목 조회 |

Response:
```json
[
  {
    "id": "fld_pN_DLyu4R_YwAW9TKMkeeA4HWNHwp9jQLdl9zGVEich-SB0fA2MrHuBW1HzzTumYE0JSUbjql2vy_0NFgJ7b",
    "name": "user1_하위폴더",
    "parentFolderId": "fld_2hZZtdtfQY882ej2UKxIoYuDCIQe87Rr4-i3Gn6pMHOX3qhSeE6seafvdygr0S_nVIwSIJkG25O5CAsTfcB7",
    "gubun": "D",
    "hasChildren": true,
    "userUniqCode": null,
    "departmentCode": "DEPT_00000000000035",
    "groupCode": null,
    "root_encryption_policy": "PLAIN"
  }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | id | string | 필수 | 없음 | `fld_`/`fldv_` + base64url ID | 하위 항목 ID | |
| 2 | name | string | 필수 | 없음 | 자유 텍스트 | 폴더/항목명 | |
| 3 | parentFolderId | string | 필수 | 없음 | 동일 ID 형식 | 상위 폴더 ID | |
| 4 | gubun | string (enum) | 필수 | 없음 | `D`,`Q`,`G`,`U` 관측 | 폴더 구분 코드 | |
| 5 | hasChildren | boolean | 필수 | 없음 | `true`/`false` | 자식 존재 여부 | |
| 6 | userUniqCode | string \| null | 선택 | `null` | `USER_` + 14자리 숫자 | 개인 소유자 코드 | 개인 소유 폴더일 때만 값 존재 |
| 7 | departmentCode | string \| null | 선택 | `null` | `DEPT_` + 11자리 숫자 | 부서 코드 | 부서 폴더일 때만 값 존재 |
| 8 | groupCode | string \| null | 선택 | `null` | `GROUP_` + 11자리 숫자 | 그룹 코드 | 그룹 폴더일 때만 값 존재 |
| 9 | root_encryption_policy | string (enum) | 필수 | 없음 | 관측값: `PLAIN` | 암호화 정책 | |

### GET /api/v1/folders/{folderId}/document-attributes
Query: 없음

Response (`404`, 루트 폴더 대상):
```json
{
  "message": "폴더를 찾을 수 없습니다.",
  "code": "NOT_FOUND"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | message | string | 필수 | 없음 | 자유 텍스트 | 에러 메시지 | |
| 2 | code | string (enum) | 필수 | 없음 | 관측값: `NOT_FOUND` | 에러 코드 | |

비고: 200 응답 스키마(정상 폴더 속성)는 못 잡음 — 일반 문서 폴더 대상으로 재확인 필요.

### GET /api/v1/documents
Query:
```json
{
  "boxId": "favorites",
  "gubun": "(관측됨, 값 미확인)",
  "page": "1",
  "size": "100"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | boxId | string | 필수 | 없음 | `fld_...`/`root_...` 폴더 ID, 특수값 `favorites` 관측 | 조회 대상 문서함/폴더 ID | |
| 2 | gubun | string | 필수 여부 미확인 | 없음 | 호출은 됐으나 값이 로그에서 비어있어 미확인 | 폴더 구분 필터로 추정 | |
| 3 | page | integer(문자열 전달) | 필수 | 없음 | `1`부터 시작(1-base 추정) | 페이지 번호 | |
| 4 | size | integer(문자열 전달) | 필수 | 없음 | 관측값 `100` | 페이지당 건수 | |

Response:
```json
{
  "items": [],
  "page": 1,
  "size": 100,
  "totalCount": 0,
  "totalPages": 0,
  "hasNext": false
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | items | array | 필수 | `[]` | **내부 필드 구조 미확인** | 문서 목록 | 항상 빈 배열만 관측 — 문서 있는 폴더로 재호출 필요 |
| 2 | page | integer | 필수 | 없음 | 요청한 page 값 반영 | 현재 페이지 번호 | |
| 3 | size | integer | 필수 | 없음 | 요청한 size 값 반영 | 페이지당 건수 | |
| 4 | totalCount | integer | 필수 | 없음 | 0 이상 정수 | 전체 문서 수 | |
| 5 | totalPages | integer | 필수 | 없음 | 0 이상 정수 | 전체 페이지 수 | |
| 6 | hasNext | boolean | 필수 | 없음 | `true`/`false` | 다음 페이지 존재 여부 | |

### GET /api/v1/documents/recent
Query: 없음

Response:
```json
[
  {
    "author": "최승호",
    "contentCategory": "GENERALDOC",
    "contentCategoryName": null,
    "contentCode": "C0000000000000002370",
    "contentTitle": "이름 수정.rtf",
    "contentVersion": "0.1",
    "createDate": "2026-07-31 09:28",
    "fileExe": "rtf",
    "fileSize": "40 kB",
    "folderPath": "QnA > seungho.choi의 폴더",
    "lockUser": null,
    "lockUserName": null,
    "modifyDate": "2026-07-31 09:28",
    "revisionCode": "R0000000000000002506",
    "userUniqCode": "USER_00000000000058"
  }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | author | string | 필수 | 없음 | 자유 텍스트 | 작성자 표시 이름 | |
| 2 | contentCategory | string (enum) | 필수 | 없음 | 관측값: `GENERALDOC` | 문서 카테고리 | 이미지/동영상 등 다른 카테고리 존재 가능(추정) |
| 3 | contentCategoryName | string \| null | 선택 | `null` | 관측값 `null` | 카테고리 표시명 | contentCategory가 특수값일 때만 채워질 것으로 추정 |
| 4 | contentCode | string | 필수 | 없음 | `C` + 19자리 숫자 | 문서(콘텐츠) 고유 ID | |
| 5 | contentTitle | string | 필수 | 없음 | 자유 텍스트(확장자 포함) | 파일명 | |
| 6 | contentVersion | string | 필수 | 없음 | `"0.1"` 형식(소수점 포함) | 문서 버전 | |
| 7 | createDate | string | 필수 | 없음 | `"YYYY-MM-DD HH:mm"` | 생성일시 | ISO 8601 아님, 초 단위 없음 |
| 8 | fileExe | string | 필수 | 없음 | 점 없는 확장자, 관측값: `rtf`, `xlsx` | 파일 확장자 | |
| 9 | fileSize | string | 필수 | 없음 | `"40 kB"`처럼 단위 포함 텍스트 | 파일 크기 | 숫자가 아니라 텍스트 — 정렬/계산 시 파싱 필요 |
| 10 | folderPath | string | 필수 | 없음 | `" > "` 구분자 경로 텍스트 | 문서가 속한 폴더 경로 | |
| 11 | lockUser | string \| null | 선택 | `null` | 관측값 `null`(잠금 없음) | 잠금 사용자 ID | 잠긴 문서면 사용자 ID 추정 |
| 12 | lockUserName | string \| null | 선택 | `null` | 관측값 `null` | 잠금 사용자 표시명 | |
| 13 | modifyDate | string | 필수 | 없음 | createDate와 동일 형식 | 최종 수정일시 | |
| 14 | revisionCode | string | 필수 | 없음 | `R` + 19자리 숫자 | 리비전 코드 | |
| 15 | userUniqCode | string | 필수 | 없음 | `USER_` + 14자리 숫자 | 작성자 사용자 코드 | |

---

## 4. 대시보드 (DASHBOARD)

### GET /api/v1/dashboard/layout
Query: 없음

Response:
```json
{
  "version": 1,
  "fromDefault": false,
  "widgets": [
    { "id": "w-default-1", "type": "APPROVAL_PENDING", "title": "결재 대기", "x": 0, "y": 0, "w": 6, "h": 4, "config": { "limit": 10 } },
    { "id": "w-default-2", "type": "RECENT_WORKED", "title": "최근 작업 문서", "x": 6, "y": 0, "w": 6, "h": 4, "config": { "limit": 10 } }
  ]
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | version | integer | 필수 | 없음 | 관측값 `1` | 레이아웃 스키마 버전 | 추정 |
| 2 | fromDefault | boolean | 필수 | 없음 | 관측값 `false` | 기본 레이아웃 사용 여부 | 사용자 커스텀 레이아웃인지 여부 추정 |
| 3 | widgets[].id | string | 필수 | 없음 | `w-default-N` 형식 | 위젯 인스턴스 ID | |
| 4 | widgets[].type | string (enum) | 필수 | 없음 | 관측값: `APPROVAL_PENDING`, `RECENT_WORKED` | 위젯 종류 | `/dashboard/widgets` 카탈로그의 `widgetType`과 동일 값 집합 |
| 5 | widgets[].title | string | 필수 | 없음 | 자유 텍스트 | 위젯 제목 | |
| 6 | widgets[].x | integer | 필수 | 없음 | 0 이상 정수(그리드 좌표) | 위젯 가로 위치 | |
| 7 | widgets[].y | integer | 필수 | 없음 | 0 이상 정수(그리드 좌표) | 위젯 세로 위치 | |
| 8 | widgets[].w | integer | 필수 | 없음 | 칸 수 | 위젯 가로 크기 | |
| 9 | widgets[].h | integer | 필수 | 없음 | 칸 수 | 위젯 세로 크기 | |
| 10 | widgets[].config.limit | integer | 선택 | 없음 | 관측값 `10` | 목록형 위젯의 표시 개수 | 위젯 타입별로 config 구조 다를 수 있음(추정) |

비고: `widgets`는 실제 5건, 위는 샘플 2건만.

### GET /api/v1/dashboard/widgets
Query: 없음

Response:
```json
[
  { "widgetType": "APPROVAL_PENDING", "title": "결재 대기", "description": "내가 처리할 대기 결재", "defaultWidth": 6, "defaultHeight": 4, "minWidth": 4, "minHeight": 3, "maxWidth": null, "maxHeight": null },
  { "widgetType": "MY_WORKBOXES", "title": "내 업무함", "description": "내가 속한 개인·부서·프로젝트 업무함 목록", "defaultWidth": 4, "defaultHeight": 5, "minWidth": 3, "minHeight": 3, "maxWidth": null, "maxHeight": null }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | widgetType | string (enum) | 필수 | 없음 | 관측값: `APPROVAL_PENDING`, `MY_WORKBOXES`(총 13종 중 2건만 샘플) | 위젯 종류 코드 | |
| 2 | title | string | 필수 | 없음 | 자유 텍스트 | 위젯 제목 | |
| 3 | description | string | 필수 | 없음 | 자유 텍스트 | 위젯 설명 | |
| 4 | defaultWidth | integer | 필수 | 없음 | 칸 수 | 기본 가로 크기 | |
| 5 | defaultHeight | integer | 필수 | 없음 | 칸 수 | 기본 세로 크기 | |
| 6 | minWidth | integer | 필수 | 없음 | 칸 수 | 최소 가로 크기 | |
| 7 | minHeight | integer | 필수 | 없음 | 칸 수 | 최소 세로 크기 | |
| 8 | maxWidth | integer \| null | 선택 | `null` | 관측값 `null`(제한 없음) | 최대 가로 크기 | 제한 있는 위젯 타입 존재 가능(추정) |
| 9 | maxHeight | integer \| null | 선택 | `null` | 관측값 `null`(제한 없음) | 최대 세로 크기 | 제한 있는 위젯 타입 존재 가능(추정) |

---

## 5. 권한 (PERMISSION)

### GET /api/v1/approvals
Query:
```json
{
  "scope": "sent",
  "approvalState": "PQ"
}
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | scope | string (enum) | 필수(추정) | 없음 | 관측값: `sent`(`received` 등 존재 추정) | 조회 범위(보낸/받은 요청) | "보낸 요청" 탭에서 `sent` 확인, "받은 요청" 탭 값은 미확인 |
| 2 | approvalState | string (enum) | 필수 여부 미확인 | 없음 | 관측값: `PQ`("진행중" 추정) | 승인 상태 필터 코드 | 전체/승인/반려 탭 클릭 시 다른 값 전달 추정 |

Response:
```json
[
  {
    "approvalCode": "APPROVAL_000000000000405",
    "approvalTitle": "문서 열람 권한 요청",
    "approvalFileCount": 1,
    "approvalState": "PQ",
    "approvalWantUser": "user_1",
    "approvalAuthUser": "",
    "approvalReqDate": "2026-07-28T09:46:26.272254",
    "approvalType": "READ",
    "approvalEndDate": null
  }
]
```

| No | 파라미터명 | 타입 | 필수여부 | 기본값 | 허용값 / 형식 | 설명 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | approvalCode | string | 필수 | 없음 | `APPROVAL_` + 18자리 숫자 | 승인 요청 고유 코드 | |
| 2 | approvalTitle | string | 필수 | 없음 | 자유 텍스트 | 요청 제목 | |
| 3 | approvalFileCount | integer | 필수 | 없음 | 0 이상 정수 | 대상 파일 수 | |
| 4 | approvalState | string (enum) | 필수 | 없음 | 관측값: `PQ` | 승인 상태 코드 | query의 approvalState와 동일 값 집합으로 추정 |
| 5 | approvalWantUser | string | 필수 | 없음 | 자유 텍스트(사용자 ID) | 요청자 사용자 ID | |
| 6 | approvalAuthUser | string | 선택 | `""` | 관측값 `""` | 승인자 ID | 미승인 시 빈 문자열 |
| 7 | approvalReqDate | string | 필수 | 없음 | ISO 8601, 마이크로초 포함(`YYYY-MM-DDTHH:mm:ss.ffffff`) | 요청 일시 | |
| 8 | approvalType | string (enum) | 필수 | 없음 | 관측값: `READ` | 요청 유형 | `WRITE`/`DOWNLOAD` 등 존재 가능(추정) |
| 9 | approvalEndDate | string \| null | 선택 | `null` | 관측값 `null`(미종료) | 종료 일시 | 종료 시 ISO 8601 형식 추정 |

---

## 제외됨
- `POST /cdn-cgi/rum` (Cloudflare RUM 비콘, 앱 API 아님, 10회) — Request Body에 `siteToken` 포함되어 있었으나 마스킹 처리됨.

## 아직 못 잡은 것 (문서 단위 기능 스캔에서 확인 필요)
- `GET /api/v1/documents`의 `items[]` 내부 필드 구조 (이번엔 빈 폴더라 못 잡음 — 문서 있는 폴더 대상 재호출 필요)
- 문서 업로드 실제 제출 API (모달만 열어봤고 실제 업로드는 안 함)
- 문서 다운로드 / 삭제 / 이름변경 / 즐겨찾기 API
- 문서 상세보기(속성) API — `document-attributes`를 일반 문서 폴더 대상으로 재확인
- 휴지통 관련 API (복원/영구삭제)
- 전사관리자 하위 API — `enterpriseAdmin: false`로 확인되어 new1 계정으론 접근 불가(권한 있는 계정 필요)
- 업무함 관리자 하위 API — `workboxAdmin: true`인데도 메뉴가 안 열리는 원인 확인 필요
- 각 enum 필드의 관측되지 않은 나머지 값(예: `gubun`의 다른 값, `approvalState`의 다른 상태 코드 등) — 여러 계정/시나리오로 추가 호출 필요
- 각 필드의 필수여부/기본값 — 현재는 "매 호출에 값이 있었는지"로 추정한 것이라, 실제 옵션 파라미터 생략 테스트로 교차 검증 필요
