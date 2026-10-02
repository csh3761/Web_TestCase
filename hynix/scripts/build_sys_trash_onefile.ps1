$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build\Sys_Trash_OneFile"
$DistRoot = Join-Path $ProjectRoot "release\Sys_Trash_OneFile"
$DesktopTarget = Join-Path $env:USERPROFILE "Desktop\Sys_Trash.exe"
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
    --name Sys_Trash `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "work") `
    --specpath $BuildRoot `
    --paths (Join-Path $ProjectRoot "src") `
    --paths (Join-Path $ProjectRoot "tools") `
    --paths (Join-Path $RepoRoot "common") `
    --hidden-import explorer_path_test `
    --hidden-import login_session_check `
    --hidden-import window_layout `
    --add-data "$PlaywrightSource;ms-playwright" `
    --add-data "$(Join-Path $ProjectRoot "config");config" `
    (Join-Path $ProjectRoot "tools\sys_trash.py")

Copy-Item -LiteralPath (Join-Path $DistRoot "Sys_Trash.exe") -Destination $DesktopTarget -Force

Write-Host "sys_trash.py one-file exe created:"
Write-Host $DesktopTarget
