# Web_TestCase

OTCS 웹 시스템의 반복 업무(휴지통 정리, 로그인/세션 점검, 문서 업로드)를 Playwright 기반으로
자동화하는 테스트 스크립트 모음입니다.

## 핵심 도구

| 도구 | 위치 | 역할 |
|---|---|---|
| **Sys_Trash** | `hynix_interface/sys_trash.py` | 관리자(전사) 휴지통 문서 전량 정리. sysadmin 고정 계정 사용 |
| **User_Trash** | `HYNIX/user_trash.py` | 로그인한 개인 계정의 내 업무함 / 부서 업무함 / 프로젝트 업무함 휴지통 정리 |

두 도구 모두 삭제 완료 알림창(SweetAlert2)을 감지하면 OK/확인 버튼까지 자동으로 클릭해서
닫으며, 실행 시 로그 콘솔은 화면 왼쪽·브라우저 창은 화면 오른쪽으로 자동 배치됩니다
(`HYNIX/window_layout.py` 공통 헬퍼).

## 폴더 구조

```
HYNIX/            개인 계정 기준 자동화 (User_Trash, 로그인/업로드 테스트 등)
hynix_interface/  관리자 계정 기준 자동화 (Sys_Trash 등)
config/           로그인/계정 설정 — 실 파일은 git 제외, *.example.json 템플릿만 추적
scripts/          PyInstaller 빌드 스크립트, 유틸 스크립트
md/, reference/   설계·기능 목록 문서
reports/          실행 로그/리포트 (git 제외, 재생성됨)
build/, release/  EXE 빌드 산출물 (git 제외, 재생성됨)
```

## 실행

```powershell
.venv\Scripts\python.exe hynix_interface\sys_trash.py --mode document --select-only
.venv\Scripts\python.exe HYNIX\user_trash.py --username <ID> --password <PW> --select-only
```

`--select-only`는 체크박스 선택까지만 하고 실제 삭제는 하지 않는 리허설 옵션입니다.

## 설정

`config/*.example.json` 파일을 복사해 같은 이름에서 `.example`을 뗀 실제 파일
(`config/login_config.json`, `config/trash_credentials.json` 등)을 만들어 사용합니다.
실제 계정정보가 담긴 파일은 `.gitignore`로 제외되어 있습니다.

## EXE 빌드

```powershell
scripts\build_sys_trash_onefile.ps1
scripts\build_user_trash_onefile.ps1
```

EXE 컴파일은 사용자가 명시적으로 요청할 때만 수행합니다 (`CLAUDE.md` 규칙).

## 주의

otcs.ifns.devel 등 실제 테스트 환경에 직접 접속해 문서를 **영구 삭제**하는 동작을
수행합니다. 처음 확인할 때는 `--select-only`로 먼저 리허설 후 실행하세요.
