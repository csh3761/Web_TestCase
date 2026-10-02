$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build\Sys_Trash"
$ReleaseRoot = Join-Path $ProjectRoot "release\Sys_Trash"
$PlaywrightSource = Join-Path $env:LOCALAPPDATA "ms-playwright"
$PlaywrightTarget = Join-Path $ReleaseRoot "ms-playwright"

if (!(Test-Path $Python)) {
    throw "Python virtual environment was not found: $Python"
}

if (!(Test-Path $PlaywrightSource)) {
    & $Python -m playwright install chromium
}

if (Test-Path $ReleaseRoot) {
    Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null

& $Python -m PyInstaller `
    --onefile `
    --console `
    --name Sys_Trash `
    --distpath $ReleaseRoot `
    --workpath (Join-Path $BuildRoot "work") `
    --specpath $BuildRoot `
    --paths (Join-Path $ProjectRoot "src") `
    --paths (Join-Path $ProjectRoot "tools") `
    --paths (Join-Path $RepoRoot "common") `
    --hidden-import explorer_path_test `
    --hidden-import login_session_check `
    --hidden-import window_layout `
    (Join-Path $ProjectRoot "tools\sys_trash.py")

Copy-Item -LiteralPath $PlaywrightSource -Destination $PlaywrightTarget -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config") -Destination (Join-Path $ReleaseRoot "config") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "data") -Destination (Join-Path $ReleaseRoot "data") -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $ReleaseRoot "reports") -Force | Out-Null

Write-Host "sys_trash.py release created:"
Write-Host $ReleaseRoot
