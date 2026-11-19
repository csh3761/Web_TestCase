# skmr API 카탈로그 (명세 기반 자동 수집)

GET 은 실제로 호출한 응답을 기록했습니다 (서버 데이터 변경 없음).
POST/PUT/PATCH/DELETE 는 호출하지 않고 명세의 태그/요약/스키마만 기록했습니다.

- 계정: 테스트 계정(new1) / 생성 시각 기준

## Agent (28)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/agent/documents/{revisionCode}/favorite` | 단일 문서 즐겨찾기 해제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/agent/documents` | 문서 조회 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/access` | 내 문서 권한 조회 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/history` | 문서 이력 보기 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/permissions` | 권한 정보 조회 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/properties` | 문서 속성 보기 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/shares` | 공유 정보 조회 | 401 |
| GET | `/api/v1/agent/documents/{revisionCode}/versions` | 버전 이력 보기 | 401 |
| GET | `/api/v1/agent/folders/{folderId}/access` | 내 폴더 권한 조회 | 401 |
| GET | `/api/v1/agent/folders/{folderId}/children` | 하위 폴더 목록 | 401 |
| GET | `/api/v1/agent/me` | Agent 내 정보 조회 | 401 |
| GET | `/api/v1/agent/root-menus` | ROOT 메뉴 조회 | 401 |
| PATCH | `/api/v1/agent/documents/owner` | 소유권 이전 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/agent/documents/{revisionCode}/permissions` | 권한 저장 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/agent/documents/{revisionCode}/properties` | 문서 속성 변경 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/agent/documents/{revisionCode}/shares` | 공유 저장 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/document-copies` | 문서 복사 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/document-moves` | 문서 이동 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/documents/favorites` | 즐겨찾기 해제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/documents/locks` | 문서 체크아웃 취소 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/documents/upload` | Agent 일반 문서 업로드 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/documents/{revisionCode}/share-links` | 문서 URL 복사 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/login` | Agent 로그인 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/logout` | Agent 로그아웃 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/agent/permission-requests` | 권한 요청 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/agent/documents/favorites` | 즐겨찾기 추가 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/agent/documents/locks` | 문서 체크아웃 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/agent/documents/{revisionCode}/favorite` | 단일 문서 즐겨찾기 추가 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Approval (6)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/approvals` | 결재 목록 조회 | 200 |
| GET | `/api/v1/approvals/{approvalId}` | 결재 상세 조회 | 200 |
| GET | `/api/v1/approvals/{approvalId}/documents` | 결재 문서 목록 조회 | 200 |
| PATCH | `/api/v1/approvals/{approvalId}` | 결재 처리 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/approvals/{approvalId}/cancel` | 결재 요청 취소 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/approvals` | 결재 요청 생성 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Auth (5)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/auth/login/challenge` | 로그인 암호화 Challenge 발급 | 200 |
| GET | `/api/v1/auth/me` | Web/Agent 통합 내 정보 조회 | 200 |
| POST | `/api/v1/auth/login` | Web/Agent 통합 로그인 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/auth/logout` | Web/Agent 통합 로그아웃 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/auth/refresh` | 인증 쿠키 갱신 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Common (2)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/common/doc-types` | 문서 검색 옵션 조회 | 200 |
| GET | `/api/v1/common/sdms-manager` | 전사문서관리자 조회 | 200 |

## Dashboard (6)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/dashboard/widgets/{widgetId}` | 위젯 삭제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/dashboard/layout` | 레이아웃 조회 | 200 |
| GET | `/api/v1/dashboard/widgets` | 위젯 카탈로그 조회 | 200 |
| PATCH | `/api/v1/dashboard/widgets/{widgetId}` | 위젯 설정 변경 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/dashboard/widgets` | 위젯 추가 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/dashboard/layout` | 레이아웃 저장 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Document chunk uploads (5)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/document-uploads/{uploadId}` | 청크 업로드 취소 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/document-uploads/{uploadId}` | 청크 업로드 진행 상태 조회 | 호출 안 함 (업로드 세션 생성(쓰기)이 선행되어야 함. 별도 업로드 테스트에서 확인함) |
| POST | `/api/v1/document-uploads` | 청크 업로드 세션 생성 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/document-uploads/{uploadId}/complete` | 청크 조립 및 문서 등록 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/document-uploads/{uploadId}/chunks/{chunkIndex}` | 청크 업로드 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Documents (33)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/documents` | 문서 삭제(휴지통) | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/documents/favorites` | 즐겨찾기 해제(일괄) | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/documents/locks` | 문서 잠금 해제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/documents/permanent` | 문서 영구 삭제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/documents/{revisionCode}/favorite` | 즐겨찾기 해제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/document-moves/owner-candidates` | 문서 이동 owner 후보 | 200 |
| GET | `/api/v1/documents` | 문서 목록 조회 | 200 |
| GET | `/api/v1/documents/context-menu-items` | 문서 컨텍스트 메뉴 | 200 |
| GET | `/api/v1/documents/download-jobs/{token}/chunks/{chunkIndex}` | 청크 문서 다운로드 | 호출 안 함 (다운로드 작업 생성이 선행되어야 함) |
| GET | `/api/v1/documents/download-jobs/{token}/content` | Range 문서 다운로드 | 호출 안 함 (다운로드 작업 생성(쓰기성 흐름)이 선행되어야 함) |
| GET | `/api/v1/documents/recent` | 최근 작업 문서 | 200 |
| GET | `/api/v1/documents/{boxType}/latest` | 최신 문서 | 200 |
| GET | `/api/v1/documents/{revisionCode}/copy-options` | 복사 대화상자 옵션 | 200 |
| GET | `/api/v1/documents/{revisionCode}/history` | 문서 이력 조회 | 200 |
| GET | `/api/v1/documents/{revisionCode}/move-options` | 이동 대화상자 옵션 | 403 |
| GET | `/api/v1/documents/{revisionCode}/permissions` | 문서 권한 조회 | 403 |
| GET | `/api/v1/documents/{revisionCode}/properties` | 문서 속성 조회 | 200 |
| GET | `/api/v1/documents/{revisionCode}/shares` | 문서 공유 목록 조회 | 403 |
| GET | `/api/v1/documents/{revisionCode}/versions` | 문서 버전 목록 | 200 |
| GET | `/api/v1/share-links/{linkCode}` | 문서 공유 링크 조회 | 호출 안 함 (필요한 값 확보 못함: linkCode) |
| PATCH | `/api/v1/documents` | 문서 일괄 수정 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/documents/{revisionCode}/permissions` | 문서 권한 수정 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/documents/{revisionCode}/properties` | 문서 속성 수정 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PATCH | `/api/v1/documents/{revisionCode}/shares` | 문서 공유 수정 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/document-copies` | 문서 복사 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/document-moves` | 문서 이동 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/documents/download` | 문서 다운로드 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/documents/download-jobs` | 재개 가능한 다운로드 준비 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/documents/upload` | Web 일반 문서 업로드 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/documents/{revisionCode}/share-links` | 문서 공유 링크 발급 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/documents/favorites` | 즐겨찾기 추가(일괄) | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/documents/locks` | 문서 편집 잠금 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/documents/{revisionCode}/favorite` | 즐겨찾기 추가 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Eapproval (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| POST | `/api/v1/eapprovals` | 전자결재 상신 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Folder Favorites (6)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/folder-favorites` | 폴더 즐겨찾기 해제(폴더) | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/folder-favorites/{favoritesCode}` | 폴더 즐겨찾기 해제(코드) | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/folder-favorites` | 폴더 즐겨찾기 목록 | 200 |
| GET | `/api/v1/folder-favorites/candidates` | 폴더 즐겨찾기 후보 | 200 |
| PATCH | `/api/v1/folder-favorites/order` | 폴더 즐겨찾기 순서 변경 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/v1/folder-favorites` | 폴더 즐겨찾기 추가 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Folders (11)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/folder-share-links/{linkCode}` | 폴더 공유 링크 비활성화 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/folders/{folderId}` | 폴더 삭제 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/v1/folders/{folderId}/trash-items` | 휴지통 비우기 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/folder-share-links/{linkCode}` | 폴더 공유 링크 조회 | 호출 안 함 (필요한 값 확보 못함: linkCode) |
| GET | `/api/v1/folders/roots` | 폴더 루트 목록 | 200 |
| GET | `/api/v1/folders/{folderId}/capabilities` | 폴더 권한·기능 조회 | 200 |
| GET | `/api/v1/folders/{folderId}/children` | 하위 폴더 목록 | 200 |
| GET | `/api/v1/folders/{folderId}/document-attributes` | 폴더 문서 속성 조회 | 200 |
| PATCH | `/api/v1/folders/{folderId}` | 폴더 수정 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/folders` | 폴더 생성 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/v1/folders/{folderId}/share-links` | 폴더 공유 링크 발급 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## Log (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/logs/api` | API 접근 로그 조회 (Grafana) | 200 |

## Menus (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/menus/top` | 활성 상단 메뉴 | 200 |

## User (2)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/departments` | 부서 목록 조회 | 200 |
| GET | `/api/v1/users` | 사용자·부서·그룹 검색 | 200 |

## agent-handoff-controller (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| POST | `/api/v1/agent/handoff` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## agent-login-controller (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/v1/auth/agent-login` |  | 호출 안 함 (인증 코드(code)가 필요하고, 임의 값으로 시도하면 인증 시도 기록이 남을 수 있어 호출하지 않음) |

## alias-controller (5)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/aliases/{aliasName}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/aliases` |  | 200 |
| GET | `/api/aliases/indices/names` |  | 200 |
| POST | `/api/aliases` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/aliases/{aliasName}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## cluster-controller (2)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/clusters` |  | 200 |
| GET | `/api/clusters/{clusterId}/health` |  | 200 |

## cluster-node-controller (2)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/cluster/nodes` |  | 200 |
| GET | `/api/cluster/nodes/{nodeId}` |  | 500 |

## document-indexing-controller (6)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/document-indexing/{documentId}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/document-indexing/targets` |  | 200 |
| POST | `/api/document-indexing/bulk-index` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/document-indexing/index/{documentId}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/document-indexing/queue` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/document-indexing/sync-users` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## index-controller (15)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/indices` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/indices/{name}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/indices` |  | 200 |
| GET | `/api/indices/suggest` |  | 200 |
| GET | `/api/indices/{indexName}` |  | 200 |
| GET | `/api/indices/{indexName}/mapping` |  | 200 |
| GET | `/api/indices/{indexName}/metrics` |  | 200 |
| GET | `/api/indices/{indexName}/settings` |  | 200 |
| GET | `/api/indices/{indexName}/shards` |  | 200 |
| GET | `/api/indices/{indexName}/stats` |  | 200 |
| POST | `/api/indices` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/indices/close` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/indices/open` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/indices/{name}/close` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/indices/{name}/open` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## index-template-controller (7)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/index-templates/{name}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/index-templates` |  | 200 |
| GET | `/api/index-templates/validate-pattern` |  | 200 |
| GET | `/api/index-templates/{name}` |  | 200 |
| POST | `/api/index-templates` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/index-templates/{templateId}/create-index` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/index-templates/{name}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## ism-controller (10)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/ism/policies/{policyId}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/ism/applyable-indices` |  | 200 |
| GET | `/api/ism/explain/{indexName}` |  | 200 |
| GET | `/api/ism/index-policy-status` |  | 200 |
| GET | `/api/ism/policies` |  | 200 |
| GET | `/api/ism/policies/{policyId}` |  | 200 |
| POST | `/api/ism/policies/apply` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/ism/policies/detach` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/ism/policies/{policyId}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/ism/policies/{policyId}/detach-and-delete` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## overview-controller (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/overview` |  | 200 |

## repository-controller (4)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/repositories/{name}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/repositories` |  | 200 |
| POST | `/api/repositories` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| PUT | `/api/repositories/{name}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## search-controller (8)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/v1/search/form` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/v1/search` |  | 200 |
| GET | `/api/v1/search/attr` |  | 200 |
| GET | `/api/v1/search/author` |  | 500 |
| GET | `/api/v1/search/facet` |  | 200 |
| GET | `/api/v1/search/form` |  | 500 |
| GET | `/api/v1/search/suggest` |  | 200 |
| POST | `/api/v1/search/form` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## search-result-controller (4)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| GET | `/api/search/analyze` |  | 200 |
| GET | `/api/search/analyzers` |  | 200 |
| GET | `/api/search/fields` |  | 200 |
| GET | `/api/search/results` |  | 200 |

## secure-disk-controller (1)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| POST | `/api/cfa/nodes/{fileId}/secure-key/` | IFNS-S SecureDisk 파일 키 요청 | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## snapshot-controller (11)

| 메서드 | 경로 | 요약 | 결과 |
|---|---|---|---|
| DELETE | `/api/snapshot/delete` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| DELETE | `/api/snapshot/{repo}/{snapshot}` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| GET | `/api/snapshot` |  | 500 |
| GET | `/api/snapshot/list/repository` |  | 200 |
| GET | `/api/snapshot/list/{repoName}` |  | 500 |
| GET | `/api/snapshot/{repository}/{snapshotName}/detail` |  | 호출 안 함 (필요한 값 확보 못함: snapshotName) |
| POST | `/api/snapshot` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/snapshot/create` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/snapshot/repository` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/snapshot/restore` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |
| POST | `/api/snapshot/{repo}/{snapshot}/restore` |  | 호출 안 함 (쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)) |

## GET 실제 응답 샘플

### GET `/api/v1/folder-favorites`
- 상태: 200
```json
{"items": []}
```

### GET `/api/v1/dashboard/layout`
- 상태: 200
```json
{"version": 1, "fromDefault": false, "widgets": [{"id": "w-default-1", "type": "APPROVAL_PENDING", "title": "결재 대기", "x": 0, "y": 0, "w": 6, "h": 4, "config": {"limit": 10}}, {"id": "w-default-2", "type": "RECENT_WORKED", "title": "최근 작업 문서", "x": 6, "y": 0, "w": 6, "h": 4, "config": {"limit": 10}}, {"id": "w-default-3", "type": "FAVORITES", "title": "즐겨찾기", "x": 0, "y": 4, "w": 6, "h": 4, "config": {"limit": 10}}, {"id": "w-default-4", "type": "FOLDER_ROOTS", "title": "FOLDER_ROOTS", "x": 6, "y": 4, "w": 6, "h": 6, "config": {"expandDepth": 1}}, {"id": "w-1d38dfa8-5330-464f-81de-69e8fc61a879"...(생략)
```

### GET `/api/index-templates/123`
- 상태: 200
```json
{"template": {"settings": {}, "mappings": {}}, "name": "123"}
```

### GET `/api/v1/search/form`
- 상태: 500
```json
{"message": "요청 처리 중 오류가 발생했습니다.", "code": "INTERNAL_SERVER_ERROR"}
```

### GET `/api/v1/dashboard/widgets`
- 상태: 200
```json
[{"widgetType": "APPROVAL_PENDING", "title": "결재 대기", "description": "내가 처리할 대기 결재", "defaultWidth": 6, "defaultHeight": 4, "minWidth": 4, "minHeight": 3, "maxWidth": null, "maxHeight": null}, {"widgetType": "MY_WORKBOXES", "title": "내 업무함", "description": "내가 속한 개인·부서·프로젝트 업무함 목록", "defaultWidth": 4, "defaultHeight": 5, "minWidth": 3, "minHeight": 3, "maxWidth": null, "maxHeight": null}, {"widgetType": "APPROVAL_SENT_PENDING", "title": "내 요청 결재(대기)", "description": "내가 요청한 대기 결재", "defaultWidth": 6, "defaultHeight": 4, "minWidth": 4, "minHeight": 3, "maxWidth": null, "maxHeight": null}, {"wid...(생략)
```

### GET `/api/v1/approvals`
- 상태: 200
```json
[{"approvalCode": "APPROVAL_000000000000415", "approvalTitle": "문서 열람 권한 요청", "approvalFileCount": 1, "approvalState": "PJ", "approvalWantUser": "user_1", "approvalAuthUser": "", "approvalReqDate": "2026-07-29T14:47:13.45816", "approvalType": "READ", "approvalEndDate": "2026-07-31T09:32:14.441654"}, {"approvalCode": "APPROVAL_000000000000414", "approvalTitle": "문서 열람 권한 요청", "approvalFileCount": 1, "approvalState": "PA", "approvalWantUser": "user_1", "approvalAuthUser": "", "approvalReqDate": "2026-07-29T14:47:11.47452", "approvalType": "READ", "approvalEndDate": "2026-07-31T09:32:17.277453"},...(생략)
```

### GET `/api/snapshot`
- 상태: 500
```json
{"message": "요청 처리 중 오류가 발생했습니다.", "code": "INTERNAL_SERVER_ERROR"}
```

### GET `/api/repositories`
- 상태: 200
```json
[{"id": "ecm-backup", "name": "ecm-backup", "type": "fs", "location": "snapshots/ecm-backup", "compress": "true", "readonly": "false", "lastUpdated": "2026-10-08 10:06:16"}, {"id": "production-backups", "name": "production-backups", "type": "fs", "location": "snapshots/production-backups", "compress": "true", "readonly": "false", "lastUpdated": "2026-10-08 10:06:16"}]
```

### GET `/api/ism/policies/policy-001`
- 상태: 200
```json
{"data": {"policyId": "policy-001", "description": "converted from ILM (hot/warm/delete)", "defaultState": "hot", "priority": null, "schemaVersion": 24, "lastUpdatedTime": "-", "states": ["hot", "warm", "delete"], "indexPatterns": [], "appliedIndices": [], "raw": {"_id": "policy-001", "_version": 1, "_seq_no": 0, "_primary_term": 1, "policy": {"policy_id": "policy-001", "description": "converted from ILM (hot/warm/delete)", "last_updated_time": 1774833855650, "schema_version": 24, "error_notification": null, "default_state": "hot", "states": [{"name": "hot", "actions": [], "transitions": [{"st...(생략)
```

### GET `/api/indices`
- 상태: 200
```json
{"data": {"items": [{"id": "top_queries-2026.10.08-59467", "name": "top_queries-2026.10.08-59467", "status": "OPEN", "health": "GREEN", "docsCount": 42, "storageSize": "248.1kb", "primarySize": "248.1kb", "shards": 1, "replicas": 0, "createdDate": "2026-10-08"}, {"id": "top_queries-2026.10.07-59466", "name": "top_queries-2026.10.07-59466", "status": "OPEN", "health": "GREEN", "docsCount": 861, "storageSize": "390.3kb", "primarySize": "390.3kb", "shards": 1, "replicas": 0, "createdDate": "2026-10-07"}, {"id": "top_queries-2026.10.06-59465", "name": "top_queries-2026.10.06-59465", "status": "OPE...(생략)
```

### GET `/api/index-templates`
- 상태: 200
```json
[{"id": "123", "templateName": "123", "indexPattern": "12", "priority": 0, "version": 1, "lastModified": "\"2026-05-13 10:38:44\""}, {"id": "tenant_template", "templateName": "tenant_template", "indexPattern": ".kibana_-*_*", "priority": 2147483647, "version": 1, "lastModified": "2026-10-08 10:06:16"}, {"id": "query_insights_top_queries_template", "templateName": "query_insights_top_queries_template", "indexPattern": "top_queries-*", "priority": 1847, "version": 1, "lastModified": "2026-10-08 10:06:16"}]
```

### GET `/api/aliases`
- 상태: 200
```json
[{"id": ".kibana", "aliasName": ".kibana", "mappedIndices": [".kibana_1"], "writeIndex": null, "lastUpdated": null, "created": null, "routing": null, "filter": null}, {"id": ".kibana_92668751_admin", "aliasName": ".kibana_92668751_admin", "mappedIndices": [".kibana_92668751_admin_1"], "writeIndex": null, "lastUpdated": null, "created": null, "routing": null, "filter": null}, {"id": ".opendistro-ism-managed-index-history-write", "aliasName": ".opendistro-ism-managed-index-history-write", "mappedIndices": [".opendistro-ism-managed-index-history-2026.10.07-000192"], "writeIndex": null, "lastUpdat...(생략)
```

### GET `/api/v1/documents`
- 상태: 200
```json
{"items": [], "page": 1, "size": 30, "totalCount": 0, "totalPages": 0, "hasNext": false}
```

### GET `/api/v1/documents/R0000000000000002506/shares`
- 상태: 403
```json
{"message": "권한이 없습니다.", "code": "FORBIDDEN"}
```

### GET `/api/v1/documents/R0000000000000002506/properties`
- 상태: 200
```json
{"contentCode": "C0000000000000002370", "revisionCode": "R0000000000000002506", "contentTitle": "이름 수정.rtf", "location": "QnA / seungho.choi의 폴더", "contentCategory": "GENERALDOC", "categoryName": "일반문서", "fileSize": 40478, "fileExe": "rtf", "securityLevelCode": "H1", "securityLevelName": "대내비", "documentBoxType": "SECRET", "contentVersion": "0.1", "retentionTypeCode": "5-DOC", "retentionTypeName": "5Y", "retentionEndDate": "2031-07-29", "contentOwnUser": "USER_00000000000058", "ownerName": "최승호"}
```

### GET `/api/v1/documents/R0000000000000002506/permissions`
- 상태: 403
```json
{"message": "권한이 없습니다.", "code": "FORBIDDEN"}
```

### GET `/api/v1/approvals/APPROVAL_000000000000415`
- 상태: 200
```json
{"approvalCode": "APPROVAL_000000000000415", "approvalTitle": "문서 열람 권한 요청", "approvalFileCount": 1, "approvalState": "PJ", "approvalWantUser": "user_1", "approvalReqDate": "2026-07-29T14:47:13.45816", "gubunCd": "REQ_PUB", "approvalReqtypeCd": "REQ", "approvalType": "READ", "approvalEndDate": "2026-07-31T09:32:14.441654", "authorities": [], "files": []}
```

### GET `/api/v1/agent/documents/R0000000000000002506/shares`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents/R0000000000000002506/properties`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents/R0000000000000002506/permissions`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/users`
- 상태: 200
```json
[{"code": "DEPT_000000000000030", "name": "A 부서", "type": "DEPT"}, {"code": "DEPT_00000000000035", "name": "QnA", "type": "DEPT"}, {"code": "GROUP_00000000000047", "name": "A TFT", "type": "GROUP"}, {"code": "GROUP_00000000000058", "name": "A 프로젝트", "type": "GROUP"}, {"code": "GROUP_00000000000051", "name": "Part1", "type": "GROUP"}, {"code": "GROUP_00000000000054", "name": "QnA TFT", "type": "GROUP"}, {"code": "USER_00000000000065", "name": "docadm (docadm)", "type": "USER"}, {"code": "USER_000000000000050", "name": "감감사 (audit01)", "type": "USER"}, {"code": "USER_000000000000051", "name": "감...(생략)
```

### GET `/api/v1/search`
- 상태: 200
```json
{"data": {"pagination": {"page": 1, "totalCount": 0}, "contents": []}, "searchAfter": null}
```

### GET `/api/v1/search/suggest`
- 상태: 200
```json
{"query": "a", "didYouMean": [], "autocomplete": [], "recommend": [], "trending": []}
```

### GET `/api/v1/search/facet`
- 상태: 200
```json
{"success": true, "lang": "en", "radioSearchCondition": "and", "sections": ["today", "week", "month", "year", "etc"], "createdSums": {"today": 0, "week": 0, "month": 0, "year": 0, "etc": 0}, "aggrByCreatedDateList": [{"today": {}, "week": {}, "month": {}, "year": {}, "etc": {}}], "aggrBySpace": {}, "aggrBySpaceLabel": {}, "aggrByOwner": {}, "aggrByOwnerLabel": {}, "aggrBySecurity": {}, "aggrBySecurityLabel": {}, "aggrByFormat": {}, "categoryDateSum": {"today": {}, "week": {}, "month": {}, "year": {}, "etc": {}}, "categoryTotalSum": {"today": 0, "week": 0, "month": 0, "year": 0, "etc": 0}, "dat...(생략)
```

### GET `/api/v1/search/author`
- 상태: 500
```json
{"message": "요청 처리 중 오류가 발생했습니다.", "code": "INTERNAL_SERVER_ERROR"}
```

### GET `/api/v1/search/attr`
- 상태: 200
```json
[]
```

### GET `/api/v1/menus/top`
- 상태: 200
```json
[{"menuCode": "MENU_000000000000020", "workboxId": "dept", "menuName": "부서문서함|TEAM WORK", "displayName": "부서문서함", "menuUrl": "-", "menuIcon": "", "menuSort": 2}, {"menuCode": "MENU_000000000000120", "workboxId": "project", "menuName": "그룹문서함|PROJECT WORK", "displayName": "그룹문서함", "menuUrl": "-", "menuIcon": "", "menuSort": 3}]
```

### GET `/api/v1/logs/api`
- 상태: 200
```json
{"content": [{"Request Time": "2026-10-08 01:06:18", "Method": "GET", "API URL": "/api/v1/menus/top", "Code": 200, "User": "user_1 (new1)", "Request Params": null, "Log ID": 836614}, {"Request Time": "2026-10-08 01:06:18", "Method": "GET", "API URL": "/api/v1/search/attr", "Code": 200, "User": "user_1 (new1)", "Request Params": null, "Log ID": 836613}, {"Request Time": "2026-10-08 01:06:18", "Method": "GET", "API URL": "/api/v1/search/author", "Code": 500, "User": "user_1 (new1)", "Request Params": null, "Log ID": 836612}, {"Request Time": "2026-10-08 01:06:18", "Method": "GET", "API URL": "/a...(생략)
```

### GET `/api/v1/folders/DOCBOXM_000000000000706/document-attributes`
- 상태: 200
```json
{"contentCategory": "GENERALDOC", "securityLevelCode": "H4", "retentionTypeCode": "5-DOC"}
```

### GET `/api/v1/folders/DOCBOXM_000000000000706/children`
- 상태: 200
```json
[{"id": "DOCBOXM_000000000000708", "folderId": "DOCBOXM_000000000000708", "name": "02. 이미지", "parentFolderId": "DOCBOXM_000000000000706", "gubun": "D", "hasChildren": false, "userUniqCode": null, "departmentCode": "DEPT_00000000000035", "groupCode": null, "root_encryption_policy": "IFNS_S"}, {"id": "DOCBOXM_000000000000732", "folderId": "DOCBOXM_000000000000732", "name": "03. 업로드", "parentFolderId": "DOCBOXM_000000000000706", "gubun": "D", "hasChildren": false, "userUniqCode": null, "departmentCode": "DEPT_00000000000035", "groupCode": null, "root_encryption_policy": "IFNS_S"}, {"id": "DOCBOXM...(생략)
```

### GET `/api/v1/folders/DOCBOXM_000000000000706/capabilities`
- 상태: 200
```json
{"folderId": "DOCBOXM_000000000000706", "context": "regular", "capabilities": {"createSubfolder": true, "rename": false, "move": false, "delete": false, "emptyTrash": false}, "hasChildren": true}
```

### GET `/api/v1/folders/roots`
- 상태: 200
```json
[{"id": "DOCBOXM_000000000005", "folderId": "DOCBOXM_000000000005", "name": "바로가기", "parentFolderId": null, "gubun": "Q", "encryption_policy": "IFNS_S"}, {"id": "DOCBOXM_000000000001", "folderId": "DOCBOXM_000000000001", "name": "부서문서함", "parentFolderId": null, "gubun": "D", "encryption_policy": "IFNS_S"}, {"id": "DOCBOXM_000000000002", "folderId": "DOCBOXM_000000000002", "name": "그룹문서함", "parentFolderId": null, "gubun": "G", "encryption_policy": "IFNS_S"}]
```

### GET `/api/v1/folder-favorites/candidates`
- 상태: 200
```json
[{"gubun": "U", "scopeCode": "USER_00000000000059", "scopeKey": "MY_WORK_USER:USER_00000000000059", "folderId": "DOCBOXM_000000000000715", "scopeName": "user_1", "displayPath": "user_1", "favorited": false}, {"gubun": "D", "scopeCode": "DEPT_00000000000035", "scopeKey": "DEPT_WORK:DEPT_00000000000035", "folderId": "DOCBOXM_000000000000706", "scopeName": "QnA", "displayPath": "QnA", "favorited": false}, {"gubun": "G", "scopeCode": "GROUP_00000000000046", "scopeKey": "PROJECT_WORK:GROUP_00000000000046", "folderId": "DOCBOXM_000000000000663", "scopeName": "IDS TFT", "displayPath": "IDS TFT", "fav...(생략)
```

### GET `/api/v1/documents/R0000000000000002506/versions`
- 상태: 200
```json
{"items": [{"revisionCode": "R0000000000000002506", "contentVersion": "0.1", "contentTitle": "이름 수정.rtf", "contentState": "CR", "modifierName": "최승호", "modifiedAt": "2026-07-31 09:28:26", "fileExe": "rtf", "fileSize": 40478, "current": true}], "page": 1, "size": 30, "totalCount": 1, "totalPages": 1, "hasNext": false}
```

### GET `/api/v1/documents/R0000000000000002506/move-options`
- 상태: 403
```json
{"message": "권한이 없습니다.", "code": "FORBIDDEN"}
```

### GET `/api/v1/documents/R0000000000000002506/history`
- 상태: 200
```json
{"items": [{"contentLogCode": "L_c0c7223e714249209bfeb1", "revisionCode": "R0000000000000002506", "logGubun": "COPY", "logGubuNm": "COPY", "logContent": "원본 문서(R0000000000000002486)에서 복사", "logUserCode": "USER_00000000000058", "userNm": "최승호", "logDate": "2026-07-31 09:28:26"}], "page": 1, "size": 30, "totalCount": 1, "totalPages": 1, "hasNext": false}
```

### GET `/api/v1/documents/R0000000000000002506/copy-options`
- 상태: 200
```json
{"revisionCode": "R0000000000000002506", "defaultTab": "user", "sourceProperties": {"contentCode": "C0000000000000002370", "revisionCode": "R0000000000000002506", "contentTitle": "이름 수정.rtf", "location": "QnA / seungho.choi의 폴더", "contentCategory": "GENERALDOC", "categoryName": "일반문서", "fileSize": 40478, "fileExe": "rtf", "securityLevelCode": "H1", "securityLevelName": "대내비", "documentBoxType": "SECRET", "contentVersion": "0.1", "retentionTypeCode": "5-DOC", "retentionTypeName": "5Y", "retentionEndDate": "2031-07-29", "contentOwnUser": "USER_00000000000058", "ownerName": "최승호"}, "propertyOptio...(생략)
```

### GET `/api/v1/documents/MY_DOC/latest`
- 상태: 200
```json
[]
```

### GET `/api/v1/documents/recent`
- 상태: 200
```json
[{"author": "최승호", "contentCategory": "GENERALDOC", "contentCategoryName": null, "contentCode": "C0000000000000002370", "contentTitle": "이름 수정.rtf", "contentVersion": "0.1", "createDate": "2026-07-31 09:28", "encryption_algorithm": null, "encryption_format": null, "encryption_key_id": null, "encryption_state": null, "fileExe": "rtf", "fileSize": "40 kB", "folderPath": "QnA > seungho.choi의 폴더", "lockUser": null, "lockUserName": null, "modifyDate": "2026-07-31 09:28", "revisionCode": "R0000000000000002506", "root_encryption_policy": null, "storage_mode": null, "userUniqCode": "USER_0000000000005...(생략)
```

### GET `/api/v1/documents/context-menu-items`
- 상태: 200
```json
[{"menuCd": "VIEW", "menuNm": "보기", "menuIcon": "eye", "securityLevel": "secret", "menuCode": "VIEW", "parentMenuCode": null, "actionCode": "VIEW", "children": []}, {"menuCd": "EDIT", "menuNm": "편집", "menuIcon": "pencil", "securityLevel": "secret", "menuCode": "EDIT", "parentMenuCode": null, "actionCode": "EDIT", "children": []}, {"menuCd": "COPY", "menuNm": "복사", "menuIcon": "copy", "securityLevel": "secret", "menuCode": "COPY", "parentMenuCode": null, "actionCode": "COPY", "children": []}, {"menuCd": "DUPLICATE_LIST", "menuNm": "중복문서조회", "menuIcon": "files", "securityLevel": "secret", "menuC...(생략)
```

### GET `/api/v1/document-moves/owner-candidates`
- 상태: 200
```json
[{"userUniqCode": "USER_00000000000062", "userId": "New_ID", "userNm": "User01", "departmentNm": "QnA"}, {"userUniqCode": "USER_00000000000063", "userId": "New_Id2", "userNm": "user119", "departmentNm": "QnA"}, {"userUniqCode": "USER_00000000000059", "userId": "new1", "userNm": "user_1", "departmentNm": "QnA"}, {"userUniqCode": "USER_00000000000060", "userId": "new2", "userNm": "user_2", "departmentNm": "QnA"}, {"userUniqCode": "USER_00000000000061", "userId": "new3", "userNm": "user_3", "departmentNm": "QnA"}, {"userUniqCode": "USER_00000000000058", "userId": "seungho.choi", "userNm": "최승호", ...(생략)
```

### GET `/api/v1/departments`
- 상태: 200
```json
[{"departmentCode": "DEPT_00000000000037", "departmentNm": "IT 부서", "parentDepartmentCode": null, "sortNo": 0}, {"departmentCode": "DEPT_000000000000029", "departmentNm": "MR", "parentDepartmentCode": null, "sortNo": 0}, {"departmentCode": "DEPT_00000000000035", "departmentNm": "QnA", "parentDepartmentCode": null, "sortNo": 0}, {"departmentCode": "DEPT_00000000000177", "departmentNm": "Test Dept.", "parentDepartmentCode": null, "sortNo": 0}, {"departmentCode": "DEPT_00000000000105", "departmentNm": "인피니솔루션", "parentDepartmentCode": null, "sortNo": 1}, {"departmentCode": "DEPT_00000000000106", ...(생략)
```

### GET `/api/v1/common/sdms-manager`
- 상태: 200
```json
{"userUniqCode": "USER_000000000000045", "userNm": "김지훈"}
```

### GET `/api/v1/common/doc-types`
- 상태: 200
```json
{"documentTypes": [{"commoncodeId": "SECRET_DOC", "commoncodeNm": "비밀문서"}], "securityLevels": [{"commoncodeId": "H2", "commoncodeNm": "Confidential"}, {"commoncodeId": "H4", "commoncodeNm": "Secret"}, {"commoncodeId": "H5", "commoncodeNm": "Top Secret"}], "retentionYears": [{"commoncodeId": "1-DOC", "commoncodeNm": "1Y"}, {"commoncodeId": "3-DOC", "commoncodeNm": "3Y"}, {"commoncodeId": "5-DOC", "commoncodeNm": "5Y"}, {"commoncodeId": "10-DOC", "commoncodeNm": "10Y"}, {"commoncodeId": "15-DOC", "commoncodeNm": "15Y"}, {"commoncodeId": "20-DOC", "commoncodeNm": "20Y"}, {"commoncodeId": "LIMITLE...(생략)
```

### GET `/api/v1/auth/me`
- 상태: 200
```json
{"username": "new1", "loginChannel": "WEB", "userNm": "user_1", "departmentNames": "QnA", "enterpriseAdmin": false, "workboxAdmin": true}
```

### GET `/api/v1/auth/login/challenge`
- 상태: 200
```json
{"challengeId": "7a59dfc5-71d7-4556-8002-ddbb47183eb5", "nonce": "5pcuY_phaNIPwIcTMZmz4kuz1H2xHwDE6lFdBxPa5k8", "keyId": "YUBTk8--E6bA3Aee", "publicKey": "-----BEGIN PUBLIC KEY-----\nMIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEArsqiK8JzZj7kipxM3Rpz\nb6KSdc5K0oQqY754rvm3oMMukVeryjcz/HU0aSdKvZkQV5j/OGAzLuwOnzSdgn1w\nzpowN+Cvkv0K2P2j2gooYLUOvd3MtItqZTaS3WRsP+ty2Uu04sq7XlEGLiAUhL7U\nsSV+nLbc9PmL6S5gtH680weGwOKg3gGulkiLUaIupDpzo96kjwYNlj/UhSlfwqnk\nnk70x+hbRXs/czmDm383n/sOWmwB9DGAlB/6UupiEEqGyOX15G5lgj7wr5yLGwtj\nWPgNkn4WbnhFzQr9hL6KX3VJ6a6eFVY2LKcnFdE8UOt26T9c788RqWW/Q6yN6ktd\nalGbj/8Uge+MdMa0FWcap...(생략)
```

### GET `/api/v1/approvals/APPROVAL_000000000000415/documents`
- 상태: 200
```json
[]
```

### GET `/api/v1/agent/root-menus`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/me`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/folders/DOCBOXM_000000000000706/children`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/folders/DOCBOXM_000000000000706/access`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents/R0000000000000002506/versions`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents/R0000000000000002506/history`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/v1/agent/documents/R0000000000000002506/access`
- 상태: 401
```json
{"message": "로그인 채널이 일치하지 않습니다.", "code": "LOGIN_CHANNEL_MISMATCH"}
```

### GET `/api/snapshot/list/ecm-backup`
- 상태: 500
```json
{"message": "요청 처리 중 오류가 발생했습니다.", "code": "INTERNAL_SERVER_ERROR"}
```

### GET `/api/snapshot/list/repository`
- 상태: 200
```json
{"data": [{"settings": {"compress": true, "location": "snapshots/ecm-backup", "read_only": false}, "name": "ecm-backup", "type": "fs"}, {"settings": {"compress": true, "location": "snapshots/production-backups", "read_only": false}, "name": "production-backups", "type": "fs"}], "message": "Repository created successfully", "resultCode": "I200", "success": true}
```

### GET `/api/search/results`
- 상태: 200
```json
{"success": true, "message": "OK", "index": "docs-*", "query": "", "analyzer": "all", "fields": [], "page": 1, "pageSize": 10, "totalItems": 0, "totalPages": 0, "results": [], "searchAfter": null}
```

### GET `/api/search/fields`
- 상태: 200
```json
{"success": true, "message": "OK", "index": "top_queries-2026.10.08-59467", "fields": [{"name": "wlm_group_id", "type": "text", "searchable": true}, {"name": "source.highlight.pre_tags", "type": "text", "searchable": true}, {"name": "source.highlight.highlight_query.multi_match.query", "type": "text", "searchable": true}, {"name": "source.highlight.highlight_query.multi_match.zero_terms_query", "type": "text", "searchable": true}, {"name": "source.highlight.highlight_query.multi_match.fields", "type": "text", "searchable": true}, {"name": "source.highlight.highlight_query.multi_match.type", "t...(생략)
```

### GET `/api/search/analyzers`
- 상태: 200
```json
[]
```

### GET `/api/search/analyze`
- 상태: 200
```json
{"success": true, "message": "OK", "index": null, "analyzer": "standard", "text": "a", "tokens": [{"token": "a", "startOffset": 0, "endOffset": 1, "position": 0, "type": "<ALPHANUM>"}]}
```

### GET `/api/overview`
- 상태: 200
```json
{"cluster": {"health": "YELLOW", "numberOfNodes": 1, "totalShards": 161, "pendingTasks": 0}, "nodes": [{"node": "os-standard-61", "cpu": 2, "memory": 53, "disk": 35}], "recentActivity": [{"time": "2026-05-13T01:38:33.579051800Z", "event": "Index [search_log-2026.05.11] opened"}, {"time": "2026-05-13T01:38:33.442687800Z", "event": "Index [search_log-2026.05.12] opened"}, {"time": "2026-05-13T01:38:26.340241100Z", "event": "Index [search_log-2026.05.11] closed"}, {"time": "2026-05-13T01:38:26.171585700Z", "event": "Index [search_log-2026.05.12] closed"}, {"time": "2026-05-13T01:37:08.346612700Z"...(생략)
```

### GET `/api/ism/policies`
- 상태: 200
```json
{"data": {"items": [{"policyId": "policy-001", "description": "converted from ILM (hot/warm/delete)", "defaultState": "hot", "priority": null, "schemaVersion": 24, "lastUpdatedTime": "-", "states": ["hot", "warm", "delete"], "indexPatterns": [], "appliedIndices": [], "raw": {"_id": "policy-001", "_seq_no": 0, "_primary_term": 1, "policy": {"policy_id": "policy-001", "description": "converted from ILM (hot/warm/delete)", "last_updated_time": 1774833855650, "schema_version": 24, "error_notification": null, "default_state": "hot", "states": [{"name": "hot", "actions": [], "transitions": [{"state_...(생략)
```

### GET `/api/ism/index-policy-status`
- 상태: 200
```json
{"data": {"indices": [{"index": ".kibana_1", "status": "open", "docs": "2", "store": "10kb", "managed": false, "policy_id": null, "state": null, "has_error": false}, {"index": ".kibana_92668751_admin_1", "status": "open", "docs": "2", "store": "10kb", "managed": false, "policy_id": null, "state": null, "has_error": false}, {"index": ".opendistro-job-scheduler-lock", "status": "open", "docs": "1", "store": "15kb", "managed": false, "policy_id": null, "state": null, "has_error": false}, {"index": ".opendistro_security", "status": "open", "docs": "9", "store": "81.3kb", "managed": false, "policy_...(생략)
```

### GET `/api/ism/explain/top_queries-2026.10.08-59467`
- 상태: 200
```json
{"data": {"array": false, "bigDecimal": false, "bigInteger": false, "binary": false, "boolean": false, "containerNode": true, "double": false, "empty": false, "float": false, "floatingPointNumber": false, "int": false, "integralNumber": false, "long": false, "missingNode": false, "nodeType": "OBJECT", "null": false, "number": false, "object": true, "pojo": false, "short": false, "textual": false, "valueNode": false}, "message": "ilm explained successfully", "resultCode": "I200", "success": true}
```

### GET `/api/ism/applyable-indices`
- 상태: 200
```json
{"data": {"indices": ["auto-user-v1", "ecm-document-v7", "os-auto-document", "os-auto-document-v1", "os-ecm-documents-v1", "os-ecm-documents-v10", "os-ecm-documents-v11", "os-ecm-documents-v14", "os-ecm-documents-v15", "os-ecm-documents-v2", "os-ecm-documents-v3", "os-ecm-documents-v4", "os-ecm-documents-v9", "os-query-dict", "os-query-dict-v2", "query_dict_v1", "query_dict_v2-restored", "query_dict_v2-restored1", "search-activity-log", "search_log-2026.09.08", "search_log-2026.09.09", "search_log-2026.09.10", "search_log-2026.09.11", "search_log-2026.09.12", "search_log-2026.09.13", "search_l...(생략)
```

### GET `/api/indices/top_queries-2026.10.08-59467`
- 상태: 200
```json
{"id": "top_queries-2026.10.08-59467", "name": "top_queries-2026.10.08-59467", "status": "OPEN", "health": "GREEN", "docsCount": 42, "deletedDocs": 12, "storageSize": "248.2 KB", "primarySize": "248.2 KB", "replicaSize": "0.0 B", "avgDocSize": "5.9 KB", "shards": 1, "replicas": 0, "createdDate": "2026-10-08"}
```

### GET `/api/indices/top_queries-2026.10.08-59467/stats`
- 상태: 200
```json
{"indexingRate": 0.36, "totalIndexed": 156, "indexTimeMs": 9893, "searchRate": 0.0, "totalQueries": 0, "avgQueryTimeMs": 0.0, "queryLatencyP50Ms": null, "queryLatencyP95Ms": null, "queryLatencyP99Ms": null, "segmentCount": 7, "segmentMemoryBytes": 0, "lastMerge": null}
```

### GET `/api/indices/top_queries-2026.10.08-59467/shards`
- 상태: 200
```json
[{"id": 0, "node": "os-standard-61", "state": "STARTED", "docs": 42, "storeSize": "248.1kb", "primary": true}]
```

### GET `/api/indices/top_queries-2026.10.08-59467/settings`
- 상태: 200
```json
[{"key": "index.number_of_shards", "value": "1"}, {"key": "index.number_of_replicas", "value": "0"}, {"key": "index.creation_date", "value": "1791417602501"}]
```

### GET `/api/indices/top_queries-2026.10.08-59467/metrics`
- 상태: 200
```json
{"indexingRate": 0.0, "totalIndexed": 156, "indexTimeMs": 9893, "searchRate": 0.0, "totalQueries": 0, "avgQueryTimeMs": 0.0, "queryLatencyP50Ms": null, "queryLatencyP95Ms": null, "queryLatencyP99Ms": null, "segmentCount": 7, "segmentMemoryBytes": 0, "lastMerge": null}
```

### GET `/api/indices/top_queries-2026.10.08-59467/mapping`
- 상태: 200
```json
{"top_queries-2026.10.08-59467": {"mappings": {"dynamic": "true", "_meta": {"schema_version": 1, "query_insights_feature_space": "top_n_queries"}, "properties": {"group_by": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}}, "id": {"type": "keyword"}, "indices": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}}, "labels": {"type": "object"}, "measurements": {"properties": {"cpu": {"properties": {"aggregationType": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}}, "count": {"type": "long"}, "number"...(생략)
```

### GET `/api/indices/suggest`
- 상태: 200
```json
[{"id": null, "name": "search_log-2026.09.21", "status": "open", "health": "yellow", "docsCount": 0, "storageSize": "208b", "primarySize": null, "shards": null, "replicas": null, "createdDate": null}, {"id": null, "name": "search_log-2026.09.23", "status": "open", "health": "yellow", "docsCount": 0, "storageSize": "208b", "primarySize": null, "shards": null, "replicas": null, "createdDate": null}, {"id": null, "name": ".ql-datasources", "status": "open", "health": "green", "docsCount": 0, "storageSize": "208b", "primarySize": null, "shards": null, "replicas": null, "createdDate": null}, {"id":...(생략)
```

### GET `/api/index-templates/validate-pattern`
- 상태: 200
```json
{"data": true, "message": "available", "resultCode": "I200", "success": true}
```

### GET `/api/document-indexing/targets`
- 상태: 200
```json
[{"authCode": "DEPT_00000000000035,USER_00000000000059", "authorId": null, "bid": null, "byteFileSize": null, "chkRequestDw": null, "chkRequestLev": null, "chkRequestOut": null, "contentCategory": "GENERALDOC", "contentCategoryNm": "일반문서", "contentCode": "Cf3eb3130a7ad482cbde350b4dc58ca26", "contentDelDate": null, "contentLockDate": null, "contentLockUser": " ", "contentLockUserNm": null, "contentOwnUser": "USER_00000000000059", "contentOwnUserNm": "user_1", "contentReadCnt": 0, "contentRegDate": "2026-10-07", "contentRegId": "USER_00000000000059", "contentRegNm": "user_1", "contentSecurityLev...(생략)
```

### GET `/api/clusters`
- 상태: 200
```json
[{"name": "cluster-1", "baseUrl": "https://srch.ifns.devel:9909", "id": "cluster-1"}]
```

### GET `/api/clusters/cluster-1/health`
- 상태: 200
```json
{"status": "YELLOW", "clusterId": "cluster-1"}
```

### GET `/api/cluster/nodes`
- 상태: 200
```json
{"overview": {"clusterName": "opensearch", "status": "YELLOW", "nodes": 1, "activeShards": 88, "indices": 88, "totalDocuments": 8989, "totalSize": "195.9 MB", "version": "OpenSearch 3.3.2"}, "nodes": [{"id": "K4silGQ8Ry6BubZ1pVoO4A", "name": "os-standard-61", "ip": "127.0.0.1:9900", "role": "cluster_manager,data,ingest", "cpu": 1, "memory": 43, "disk": 35, "heapUsed": "602.5 MB", "heapMax": "1.0 GB"}], "shardAllocation": {"primaryShards": 88, "replicaShards": 0, "unassignedShards": 73}}
```

### GET `/api/cluster/nodes/os-standard-61`
- 상태: 500
```json
{"message": "요청 처리 중 오류가 발생했습니다.", "code": "INTERNAL_SERVER_ERROR"}
```

### GET `/api/aliases/indices/names`
- 상태: 200
```json
["auto-user-v1", "ecm-document-v7", "os-auto-document", "os-auto-document-v1", "os-ecm-documents-v1", "os-ecm-documents-v10", "os-ecm-documents-v11", "os-ecm-documents-v14", "os-ecm-documents-v15", "os-ecm-documents-v2", "os-ecm-documents-v3", "os-ecm-documents-v4", "os-ecm-documents-v9", "os-query-dict", "os-query-dict-v2", "query_dict_v1", "query_dict_v2-restored", "query_dict_v2-restored1", "search-activity-log", "search_log-2026.09.08", "search_log-2026.09.09", "search_log-2026.09.10", "search_log-2026.09.11", "search_log-2026.09.12", "search_log-2026.09.13", "search_log-2026.09.14", "sear...(생략)
```
