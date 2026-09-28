$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
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
    (Join-Path $ProjectRoot "hynix_interface\Main_Report.py")

Copy-Item -LiteralPath $PlaywrightSource -Destination $PlaywrightTarget -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config") -Destination (Join-Path $ReleaseRoot "config") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "csv") -Destination (Join-Path $ReleaseRoot "csv") -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $ReleaseRoot "reports") -Force | Out-Null

Write-Host "Main_Report release created:"
Write-Host $ReleaseRoot
