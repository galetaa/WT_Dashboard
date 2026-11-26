# Build on Windows: dist\wt-dashboard.exe includes Python, backend and frontend.
param([switch]$SkipInstall)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    $Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) { $Python = "python" }
    if (-not $SkipInstall) {
        & $Python -m pip install -r backend/requirements.txt pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }
    & $Python scripts/build_release.py
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }
    Write-Output "Built: $PSScriptRoot\dist\wt-dashboard.exe"
} finally {
    Pop-Location
}
