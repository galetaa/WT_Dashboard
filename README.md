# WT Dashboard

Local War Thunder telemetry and battle history for **Windows, Linux and macOS**.
Run it on the same computer as the game. The dashboard uses the game's local
HTTP API (`127.0.0.1:8111`) and opens its UI at <http://127.0.0.1:8765/#history>.

**[Download releases](https://github.com/galetaa/WT_Dashboard/releases)** ·
**[Installation and platform instructions](docs/PLATFORMS.md)**

## Quick start

| Platform | Standalone history / live view | Launch with Steam |
| --- | --- | --- |
| Windows | Extract the ZIP; run `wt-dashboard.exe` | `wt-dashboard.exe --steam` |
| Linux x86-64 | Extract the tar.gz; run `./wt-dashboard` | `./wt-dashboard --steam` |
| Mac Apple Silicon / Intel | Extract the matching tar.gz; run `./wt-dashboard` in Terminal | `./wt-dashboard --steam` |

In standalone mode the dashboard remains available after the game closes. In
Steam session mode it waits for the game to start, saves the recording when it
exits, and closes the dedicated browser window where supported. Use
`--watch-game` to wait for a game launched separately, or `--no-browser` to record
without opening the UI. See the platform guide for shortcuts, macOS first-run
steps, system requirements, paths, migration and source/build commands.

## Install and run

Release archives include the executable and instructions; Python is not needed.

### Windows x64

1. Download [the Windows ZIP](https://github.com/galetaa/WT_Dashboard/releases/latest/download/wt-dashboard-windows-x86_64.zip).
2. Extract it and double-click `wt-dashboard.exe` for standalone history/live mode.
3. To launch together with the game, create a shortcut whose target is:

```text
"C:\Tools\WT Dashboard\wt-dashboard.exe" --steam
```

Replace the executable location with your extracted folder. The dashboard waits
for War Thunder, opens its UI, then saves and exits when the game closes.

### Linux x86-64

Download [the Linux archive](https://github.com/galetaa/WT_Dashboard/releases/latest/download/wt-dashboard-linux-x86_64.tar.gz),
then run:

```sh
tar -xzf wt-dashboard-linux-x86_64.tar.gz
cd wt-dashboard-linux-x86_64
./wt-dashboard
# Launch War Thunder through Steam and follow its lifetime:
./wt-dashboard --steam
```

The binary is built on Ubuntu 22.04 and requires glibc 2.35 or newer. It does not
cover Alpine/musl or Linux ARM. If copying removed execution permissions, use
`chmod +x wt-dashboard`. Steam and `xdg-open` are needed for `--steam`.
For an applications-menu shortcut, see the [.desktop example](docs/PLATFORMS.md#linux).

### macOS: Apple Silicon or Intel

Download the archive matching **Apple menu → About This Mac**:

- [Apple Silicon (M1 or newer)](https://github.com/galetaa/WT_Dashboard/releases/latest/download/wt-dashboard-macos-arm64.tar.gz).
- [Intel](https://github.com/galetaa/WT_Dashboard/releases/latest/download/wt-dashboard-macos-x86_64.tar.gz).

Extract it in Finder or use Terminal. This example uses Apple Silicon; replace
`arm64` with `x86_64` for Intel:

```sh
tar -xzf wt-dashboard-macos-arm64.tar.gz
cd wt-dashboard-macos-arm64
./wt-dashboard
# Launch War Thunder through Steam and follow its lifetime:
./wt-dashboard --steam
```

These are command-line executables, not `.app` installers. Keep Terminal open
while recording; Ctrl+C stops the server cleanly. Both Mac builds were tested
on macOS 15; earlier macOS versions are unverified. The builds are ad-hoc signed
without Apple Developer ID notarization. If macOS blocks the first launch,
review **System Settings → Privacy & Security → Open Anyway** for this executable
if you trust the release. See [Apple's first-launch instructions](https://support.apple.com/en-us/102445).

### Launch options on every platform

| Option | Behavior |
| --- | --- |
| No options | Open standalone history/live mode, staying open after the game exits |
| `--steam` | Launch through Steam, then save and exit after the game closes |
| `--watch-game` | Wait for a game started separately and follow its lifetime |
| `--no-browser` | Record without opening the UI |
| `--open-browser` | Explicitly open the UI, including source mode |
| `--port 8766` | Choose another local HTTP port |
| `--start-timeout 900` | Wait up to 900 seconds for the game (default 600) |

Session mode uses a dedicated Edge/Chrome/Chromium/Thorium app window when one
is available and closes it on exit. With the default-browser fallback, the tab
may remain open. Other browser windows and Steam stay open. Launching directly
from the Steam Library does not start the dashboard by itself: use the shortcut
above or start `--watch-game` beforehand.

## Saved data, updates and missing rewards

| Platform | Release database location |
| --- | --- |
| Windows | `%LOCALAPPDATA%\WTDashboard\stats.db` |
| Linux | `~/.local/share/wt-dashboard/stats.db` (`XDG_DATA_HOME` supported) |
| macOS | `~/Library/Application Support/WTDashboard/stats.db` |

Linux source checkouts keep using `backend/stats.db`; Windows/macOS source
launches use the same per-user locations as their binaries. To move history,
stop the old dashboard cleanly, back up its database and copy it to the intended
destination. Do not overwrite a destination database containing other battles:
copying does not merge them. Updates preserve the per-user database.

The importer checks the running game's installation and Steam libraries for
`.game_logs`. If XP/SL is missing, set `WT_LOG_DIR` to that folder explicitly:

```powershell
# Windows PowerShell:
$env:WT_LOG_DIR = 'D:\SteamLibrary\steamapps\common\War Thunder\.game_logs'
.\wt-dashboard.exe --steam
```

```sh
# Linux / macOS:
WT_LOG_DIR="/path/to/War Thunder/.game_logs" ./wt-dashboard --steam
```

Multiple log folders use `;` on Windows and `:` on Linux/macOS. `WT_GAME_DIR`
selects a game installation, `WT_DB_PATH` selects a database, and `WT_DATA_DIR`
selects the app data directory. The [full platform guide](docs/PLATFORMS.md)
includes image-cache paths and additional migration details.

## Features

- Live friendly/enemy roster inferred from combat messages, vehicle equipment
  and damage state, and aircraft threat warnings.
- English battle history with XP/SL import, daily/last-N-hours/all-time totals,
  per-vehicle aggregates and recording coverage.
- Vehicle illustrations with local caching and links to War Thunder Wiki.
- Map background, individual vehicle/run routes, zoom/pan and timeline playback.
- Telemetry charts, field minimum/maximum/mean, damage/repair episodes,
  searchable events, inferred player rosters and complete sample inspection.
- Battle/sample JSON exports, persistent SQLite storage and automatic reward
  recovery from existing `.clog` files.

XP is the game's reported battle EXP, which can differ from vehicle research
RP. SL includes penalties and is before repair/ammunition costs. Unknown values
remain unknown. Team assignments come from combat relationships, not an official
scoreboard; route run counts are inferred, not confirmed deaths. Older stored map
backgrounds are marked unverified. Decoded logs are never saved wholesale: only
battle statistics, combat events, nickname and import cursors are retained.

## Vehicle data and illustrations

The offline English names in `frontend/vehicle_names.json` cover all ten
nations. `vehicle_names.meta.json` records the pinned datamine commit, game
version, checksums and coverage. Names come from the `_1` combat labels in
[War-Thunder-Datamine's localization](https://github.com/gszabi99/War-Thunder-Datamine/blob/master/lang.vromfs.bin_u/lang/units.csv),
restricted to the vehicle catalog. Refresh with:

```sh
python scripts/update_vehicle_names.py
python scripts/update_vehicle_names.py --ref COMMIT_FROM_METADATA
```

Vehicle illustrations are fetched on demand from
[War Thunder Wiki / Gaijin](https://wiki.warthunder.com/), cached locally, and
replaced with a labelled generic illustration if unavailable. Only the public
vehicle ID is sent to the image host. Recorded battle data stays local.
`frontend/vehicles.json` supplies vehicle type/premium metadata; refresh it using
`scripts/update_vehicles.py` when needed.

## Development and releases

Python 3.11+ is required for source launches and native builds.

```powershell
# Windows PowerShell:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\start.ps1 -Steam
# Build the executable and release ZIP:
.\build.ps1
# Run tests:
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```sh
# Linux / macOS:
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/main.py --steam
# Standalone mode:
.venv/bin/python backend/main.py --open-browser
# Build a native executable and release archive:
./build.sh
# Run tests:
PYTHONPATH=backend .venv/bin/python -m unittest discover -s tests -v
```

Build on the target OS/architecture; PyInstaller is not a cross-compiler. Output
is in `dist/`. The native release workflow runs on `main`, release tags and
manual dispatch, testing/building all four OS/architecture combinations. It also
extracts each archive and starts the packaged executable outside the repository
to check its assets, offline names, history API and database path. CI does not
run an actual War Thunder match. Published releases include `SHA256SUMS`.

For existing Linux source installations, `./start.sh` continues to use `.venv`;
`scripts/steam_session.py` supports the earlier local systemd integration. The
portable `--steam` launcher works without systemd integration; use one session
launcher at a time.
