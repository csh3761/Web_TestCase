# 업로드 자동화 프로젝트

## 요약

이 프로젝트는 `C:\workSpace\Web_TestCase\csv\업로드목록.csv`를 기준으로 사용자별 문서와 이미지를 웹 API에 업로드하기 위한 자동화 구성이다.

현재 기본 방향은 **CSV 기준 실행 + API chunk upload + 쿠키 세션 재사용**이다.
Playwright는 로그인 자동화나 브라우저 세션 확보가 필요할 때만 추가한다.

## 폴더 구조

```text
C:\workSpace\Web_TestCase
├─ archive
├─ config
├─ csv
├─ data
├─ md
├─ reference
├─ reports
├─ scripts
├─ HYNIX
└─ 인피니 솔루션
```

## 주요 파일

| 경로 | 역할 |
|---|---|
| `csv\업로드목록.csv` | 실행 기준 CSV |
| `HYNIX\login_session_check.py` | 메인 로직 파일. 로그인, 부서업무함, 하위 문서함 이동, 로그아웃 성공 로직을 누적 |
| `HYNIX\user_upload_test.py` | 사용자 1명 기준 업로드 전 테스트 파일. 하위 문서함 이동 후 업로드 구현 예정 |
| `HYNIX\explorer_path_test.py` | CSV 부서 경로 기준 Windows Explorer 이동 및 파일 선택 테스트 |
| `scripts\inspect_app_runtime.py` | Playwright Network/DOM 자동 수집 도구 |
| `scripts\convert_upload_xlsx_to_csv.py` | XLSX에서 실행용 CSV 생성 |
| `config\login_config.json` | 로그인 화면 URL, selector, 세션 검증 folderId 설정 |
| `config\cookies.example.json` | 쿠키 설정 템플릿 |
| `archive\upload_documents_legacy.py` | 초기 업로드 초안 보관본. 현재 실행 대상 아님 |
| `md\임시 기능목록.md` | 기능 목록 및 구현 로직 문서 |
| `md\테스트_하네스_기능_케이스.md` | 테스트 하네스 구조 및 항목별(로그인/세션/내비게이션/업로드/휴지통 등) 기능 테스트 케이스 목록 |

## 실행 예시

프로젝트 Python 실행은 `.venv`를 기준으로 한다.

```powershell
C:\workSpace\Web_TestCase\.venv\Scripts\python.exe -m playwright --version
```

사용자 1명 업로드 전 위치 검증:

```powershell
& 'C:\workSpace\Web_TestCase\.venv\Scripts\python.exe' `
  'C:\workSpace\Web_TestCase\HYNIX\user_upload_test.py' `
  --user-id INF93284
```

Network/DOM 자동 수집:

```powershell
& 'C:\workSpace\Web_TestCase\.venv\Scripts\python.exe' `
  'C:\workSpace\Web_TestCase\scripts\inspect_app_runtime.py' `
  --limit 1
```

Windows Explorer 경로 이동 및 파일 선택:

```powershell
& 'C:\workSpace\Web_TestCase\.venv\Scripts\python.exe' `
  'C:\workSpace\Web_TestCase\HYNIX\explorer_path_test.py' `
  --user-id INF93284 `
  --max-select 0
```

## 설치 판단

| 구성 | 필요 여부 |
|---|---|
| Python | 필수 |
| openpyxl | XLSX -> CSV 변환 시 필요 |
| Playwright | 브라우저 로그인 자동화가 필요할 때만 필요 |
| pywin32 | Windows Explorer COM 자동화 시 필요 |
| requests | 현재 스크립트는 표준 라이브러리 `urllib` 기반이라 불필요 |

## 로그인 세션 검증 초안

앞으로 자동화 문맥에서 "문서"는 `csv\업로드목록.csv`를 의미한다.
모든 사용자 비밀번호는 공통값으로 가정하고, 비밀번호는 코드에 저장하지 않는다.

터미널 입력이 불가능한 환경을 고려해 공통 비밀번호는 환경변수 또는 파일로 제공한다.

환경변수 방식:

```powershell
$env:DOCSPHERE_PASSWORD = 'Dnflskfk123@'
& 'C:\workSpace\Web_TestCase\.venv\Scripts\python.exe' `
  'C:\workSpace\Web_TestCase\HYNIX\login_session_check.py' `
  --csv 'C:\workSpace\Web_TestCase\csv\업로드목록.csv' `
  --config 'C:\workSpace\Web_TestCase\config\login_config.json' `
  --limit 2
```

파일 방식:

```powershell
& 'C:\workSpace\Web_TestCase\.venv\Scripts\python.exe' `
  'C:\workSpace\Web_TestCase\HYNIX\login_session_check.py' `
  --csv 'C:\workSpace\Web_TestCase\csv\업로드목록.csv' `
  --config 'C:\workSpace\Web_TestCase\config\login_config.json' `
  --password-file 'C:\workSpace\Web_TestCase\config\password.txt' `
  --limit 2
```

`password.example.txt`는 템플릿이다. 실제 실행 파일명은 아래처럼 `password.txt`여야 한다.

```text
C:\workSpace\Web_TestCase\config\password.txt
```

Playwright가 없는 환경에서는 먼저 설치가 필요하다. 현재 프로젝트는 `.venv`에 설치되어 있다.

```powershell
C:\workSpace\Web_TestCase\.venv\Scripts\python.exe -m pip install playwright
C:\workSpace\Web_TestCase\.venv\Scripts\python.exe -m playwright install chromium
```
