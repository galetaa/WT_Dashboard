# Start from source. Steam mode opens the game and follows the aces.exe lifetime.
param(
    [switch]$Steam,
    [switch]$WatchGame,
    [switch]$NoBrowser,
    [ValidateRange(1, 65535)][int]$Port = 8765
)
$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Create .venv and install backend/requirements.txt first (see README.md)."
}
$LaunchArguments = @((Join-Path $PSScriptRoot "backend\main.py"), "--port", "$Port")
if ($Steam) { $LaunchArguments += "--steam" }
if ($WatchGame) { $LaunchArguments += "--watch-game" }
if ($NoBrowser) { $LaunchArguments += "--no-browser" }
elseif (-not $Steam -and -not $WatchGame) { $LaunchArguments += "--open-browser" }
& $Python @LaunchArguments
exit $LASTEXITCODE
