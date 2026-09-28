$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build\User_Trash_OneFile"
$DistRoot = Join-Path $ProjectRoot "release\User_Trash_OneFile"
$DesktopTarget = Join-Path $env:USERPROFILE "Desktop\User_Trash.exe"
$PlaywrightSource = Join-Path $env:LOCALAPPDATA "ms-playwright"

if (!(Test-Path $Python)) {
    throw "Python virtual environment was not found: $Python"
}

if (!(Test-Path $PlaywrightSource)) {
    & $Python -m playwright install chromium
}

if (Test-Path $DistRoot) {
    Remove-Item -LiteralPath $DistRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $DistRoot | Out-Null

& $Python -m PyInstaller `
    --onefile `
    --console `
    --name User_Trash `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "work") `
    --specpath $BuildRoot `
    --paths (Join-Path $ProjectRoot "HYNIX") `
    --paths (Join-Path $ProjectRoot "hynix_interface") `
    --hidden-import explorer_path_test `
    --hidden-import login_session_check `
    --hidden-import sys_trash `
    --hidden-import window_layout `
    --add-data "$PlaywrightSource;ms-playwright" `
    --add-data "$(Join-Path $ProjectRoot "config");config" `
    (Join-Path $ProjectRoot "HYNIX\user_trash.py")

Copy-Item -LiteralPath (Join-Path $DistRoot "User_Trash.exe") -Destination $DesktopTarget -Force

Write-Host "user_trash.py one-file exe created:"
Write-Host $DesktopTarget
