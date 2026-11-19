@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "REPO_ROOT=%%~fI"
set "BUILD_SCRIPT=%PROJECT_ROOT%\scripts\build_re_user_trash_onefile.ps1"
set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
set "SOURCE_FILE=%PROJECT_ROOT%\tools\re_user_trash.py"
set "DESKTOP_EXE=%USERPROFILE%\Desktop\Enterprise_Trash_Delete.exe"

title Enterprise_Trash_Delete Build

echo ========================================
echo Build re_user_trash.py to Desktop
echo ========================================
echo Project root: %PROJECT_ROOT%
echo Source file : %SOURCE_FILE%
echo Target exe  : %DESKTOP_EXE%
echo.

if not exist "%PROJECT_ROOT%\" (
    echo [FAIL] Project folder not found.
    echo Path: %PROJECT_ROOT%
    goto :fail
)

if not exist "%SOURCE_FILE%" (
    echo [FAIL] Source file not found.
    echo Path: %SOURCE_FILE%
    goto :fail
)

if not exist "%PYTHON_EXE%" (
    echo [FAIL] Python venv not found.
    echo Path: %PYTHON_EXE%
    goto :fail
)

if not exist "%BUILD_SCRIPT%" (
    echo [FAIL] Build script not found.
    echo Path: %BUILD_SCRIPT%
    goto :fail
)

cd /d "%PROJECT_ROOT%"

echo [1/2] Checking Python syntax...
"%PYTHON_EXE%" -m py_compile "%SOURCE_FILE%"
if errorlevel 1 (
    echo [FAIL] Python syntax check failed.
    goto :fail
)

echo.
echo [2/2] Building with PyInstaller...
powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%"
if errorlevel 1 (
    echo [FAIL] Build failed.
    goto :fail
)

echo.
if exist "%DESKTOP_EXE%" (
    echo ========================================
    echo [OK] Build complete.
    echo Output: %DESKTOP_EXE%
    echo ========================================
) else (
    echo [FAIL] Build finished, but target exe was not found.
    goto :fail
)

echo.
pause
exit /b 0

:fail
echo.
echo ========================================
echo Build failed.
echo Check the log above.
echo ========================================
echo.
pause
exit /b 1
