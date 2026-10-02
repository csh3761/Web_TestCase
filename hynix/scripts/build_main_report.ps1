$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildRoot = Join-Path $ProjectRoot "build\Main_Report"
$ReleaseRoot = Join-Path $ProjectRoot "release\Main_Report"
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
    --name Main_Report `
    --distpath $ReleaseRoot `
    --workpath (Join-Path $BuildRoot "work") `
    --specpath $BuildRoot `
    --paths (Join-Path $ProjectRoot "src") `
    --paths (Join-Path $ProjectRoot "tools") `
    --paths (Join-Path $RepoRoot "common") `
    --hidden-import explorer_path_test `
    --hidden-import login_session_check `
    --hidden-import window_layout `
    (Join-Path $ProjectRoot "tools\Main_Report.py")

Copy-Item -LiteralPath $PlaywrightSource -Destination $PlaywrightTarget -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config") -Destination (Join-Path $ReleaseRoot "config") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "data") -Destination (Join-Path $ReleaseRoot "data") -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $ReleaseRoot "reports") -Force | Out-Null

Write-Host "Main_Report release created:"
Write-Host $ReleaseRoot
