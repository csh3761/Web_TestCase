$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build\Enterprise_Trash_Delete_OneFile"
$DistRoot = Join-Path $ProjectRoot "release\Enterprise_Trash_Delete_OneFile"
$DesktopTarget = Join-Path $env:USERPROFILE "Desktop\Enterprise_Trash_Delete.exe"
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
    --name Enterprise_Trash_Delete `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "work") `
    --specpath $BuildRoot `
    --add-data "$PlaywrightSource;ms-playwright" `
    --add-data "$(Join-Path $ProjectRoot "config");config" `
    (Join-Path $ProjectRoot "tools\re_user_trash.py")

Copy-Item -LiteralPath (Join-Path $DistRoot "Enterprise_Trash_Delete.exe") -Destination $DesktopTarget -Force

Write-Host "re_user_trash.py one-file exe created:"
Write-Host $DesktopTarget
