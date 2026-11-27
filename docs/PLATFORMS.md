# Installation and platform guide

Download archives from [the fork's Releases page](https://github.com/galetaa/WT_Dashboard/releases).
Each archive contains the executable and this guide. No Python installation is
needed for release binaries. Run the dashboard on the same computer as War
Thunder; the UI opens at <http://127.0.0.1:8765/#history>.

## Choose your download

| Computer | Release asset | Build/test host |
| --- | --- | --- |
| Windows x64 | `wt-dashboard-windows-x86_64.zip` | Windows GitHub runner |
| Linux x86-64 | `wt-dashboard-linux-x86_64.tar.gz` | Ubuntu 22.04, glibc 2.35 |
| Mac with Apple Silicon (M1 or newer) | `wt-dashboard-macos-arm64.tar.gz` | macOS 15, ARM64 |
| Mac with Intel processor | `wt-dashboard-macos-x86_64.tar.gz` | macOS 15, Intel |

On Mac, **Apple menu → About This Mac** shows the chip/processor. The Linux
binary requires glibc 2.35 or later; Alpine/musl and Linux ARM are not covered by
these binaries. Mac releases are tested on macOS 15; older macOS versions have
not been validated. Building from source is an alternative on other systems.

## Windows

Extract the ZIP and double-click `wt-dashboard.exe`. This opens standalone mode,
which stays open for browsing history after the game exits.

For a Steam game session, create a shortcut with a target such as:

```text
"C:\Tools\WT Dashboard\wt-dashboard.exe" --steam
```

Adjust the executable location. The game starts through Steam; the dashboard
starts after the game process appears and exits after the game closes.

## Linux

Extract the archive in a folder where you keep applications:

```sh
tar -xzf wt-dashboard-linux-x86_64.tar.gz
cd wt-dashboard-linux-x86_64
./wt-dashboard
# Launch through Steam and follow the game's lifetime:
./wt-dashboard --steam
```

If the executable bit was lost when copying, run `chmod +x wt-dashboard`.
Steam must be installed and `xdg-open` must be available for `--steam`. Flatpak
Steam libraries are included in log discovery. A `.desktop` shortcut can use an
absolute path, for example:

```ini
[Desktop Entry]
Type=Application
Name=War Thunder with Dashboard
Exec=/home/YOUR_USER/Applications/wt-dashboard-linux-x86_64/wt-dashboard --steam
Terminal=true
Categories=Game;
```

Save as `~/.local/share/applications/war-thunder-dashboard.desktop` and adjust
`Exec` to your own location. The existing systemd-based integration in
`scripts/steam_session.py` remains available for Linux source installations;
use one session launcher at a time.

## macOS

Extract the archive for your chip in Finder, or use Terminal:

```sh
# Apple Silicon; replace arm64 with x86_64 for Intel:
tar -xzf wt-dashboard-macos-arm64.tar.gz
cd wt-dashboard-macos-arm64
./wt-dashboard
# Launch War Thunder through Steam and follow its lifetime:
./wt-dashboard --steam
```

These releases are command-line executables, not `.app` or `.dmg` installers.
Keep the Terminal window open while using the dashboard. If copying removed
execution permission, use `chmod +x wt-dashboard`.

The builds use ad-hoc signing and are not notarized with an Apple Developer ID.
If macOS blocks the first launch, review **System Settings → Privacy & Security**
and use **Open Anyway** for this executable if you trust this release. See
[Apple's instructions](https://support.apple.com/en-us/102445). System-wide
Gatekeeper settings do not need to be changed.

## Shared launch options

| Option | Behavior |
| --- | --- |
| No options | Open history/live mode; remains running after the game closes |
| `--steam` | Launch Steam app 236390, wait for `aces` / `aces.exe`, then follow its lifetime |
| `--watch-game` | Wait for a game started separately, then follow its lifetime |
| `--no-browser` | Record/serve without opening a browser |
| `--open-browser` | Open the UI explicitly, including source mode |
| `--port 8766` | Use another local HTTP port |
| `--start-timeout 900` | Wait up to 900 seconds for the game (default 600) |

In session mode the server saves telemetry and rewards before exiting. A
separate Edge/Chrome/Chromium/Thorium app window is opened where available and
closed afterward. If none is found, your default browser is used; that tab may
remain open. Other browser windows, Steam and the game are not closed.
Launching a game directly from the Steam Library does not automatically start
the dashboard; use `--watch-game` beforehand or the `--steam` shortcut.
Use Ctrl+C in the console/Terminal to stop standalone mode cleanly.

## Map zoom and kill review

In a battle's **Route playback** panel, scroll the mouse wheel over the map,
pinch with two fingers, double-click, or use **+ / −** to zoom (up to 16×).
Wheel/pinch zoom keeps its focal point; drag to pan and **Reset view** to fit the
whole map again. Route lines and numbered kill markers follow the playhead and
selected vehicle/run. A blue/green/red `Player` marker can describe a viewed
vehicle after your death, while indicators still describe your destroyed tank.
These spectator samples are excluded from your routes, observed vehicle time
and kill origins, and split consecutive runs. Raw samples are retained. **Battle
context, mission & recording coverage** shows how many spectator samples were
excluded. Existing histories are recalculated automatically after an update.

Enable **Kill positions** to show your vehicle's recorded positions near kill
notifications. Click a marker, a **Kills in this battle** card, or **Review kill
on map** in the event timeline. The **Kill review** panel shows both players and
vehicles, event time/source, sample offset, position, speed/gear, crew/ammo,
related combat messages and the original event. Use the selector or arrow
buttons to move between kills; **Inspect kill sample** opens the complete raw
telemetry record. Closely overlapping numbered labels are offset, with small
dots/connectors pointing to their recorded positions.

These are **notification-time positions, not confirmed firing locations**. Only
preceding samples within 3 seconds are used; missing/stale samples or a different
credited vehicle remain unassigned. HTTP message time is its reception time and
can be delayed. Game-log events use the recorded log timestamp.

**Estimated connections** draws a dashed 2D line only when a compatible target
marker can be matched by a recorded player name, or one compatible enemy marker
uniquely disappears across nearby continuous samples without simultaneous
kills. A disappearing marker may have left visibility, so that case is labelled
an estimate. Capture zones, incompatible unit classes and ambiguous candidates
are excluded. Distances are approximate map-plane separation, not projectile
range. The feed does not provide the firing instant or ballistic trajectory;
when the target is not identifiable, no line or target distance is invented.

## Saved data and migration

| Platform | Database for release binaries | Vehicle image cache |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\WTDashboard\stats.db` | `%LOCALAPPDATA%\WTDashboard\cache\vehicle-images` |
| Linux | `~/.local/share/wt-dashboard/stats.db` | `~/.cache/wt-dashboard/vehicle-images` |
| macOS | `~/Library/Application Support/WTDashboard/stats.db` | `~/Library/Caches/WTDashboard/vehicle-images` |

Linux respects `XDG_DATA_HOME` and `XDG_CACHE_HOME`. Linux source checkouts keep
using `backend/stats.db` for compatibility with existing recordings. Windows
and macOS source launches use the same per-user data directory as their binary.

Before moving history, stop the old dashboard cleanly. Back up its `stats.db`
and copy it into the destination listed above before the first launch. Do not
overwrite a destination database containing other battles: migration copies a
database, it does not merge databases. Do not copy a database while a dashboard
is writing to it. Updates preserve the per-user database.

## XP / SL and game logs

XP and SL import uses the game's `.clog` files. The dashboard discovers the
running game's location and Steam installations, including additional libraries.
Native Linux also checks `~/.config/WarThunder/.game_logs`; macOS checks
`~/Library/Application Support/WarThunder/.game_logs` and installed game folders.

If discovery fails, set `WT_GAME_DIR` to the installation folder, or `WT_LOG_DIR`
to the actual `.game_logs` directory:

```powershell
# Windows PowerShell:
$env:WT_LOG_DIR = 'D:\SteamLibrary\steamapps\common\War Thunder\.game_logs'
.\wt-dashboard.exe --steam
```

```sh
# Linux/macOS:
WT_LOG_DIR="/path/to/War Thunder/.game_logs" ./wt-dashboard --steam
```

Multiple log directories use `;` on Windows, `:` on Linux/macOS. `WT_DB_PATH`
selects a database file; `WT_DATA_DIR` selects the app's writable data directory.
These overrides also work with source launches. A dash in the UI means missing
data. Battle XP may differ from research RP; SL is before repair/ammunition
expenses. Old map backgrounds are labelled unverified.

## Run or build from source

Python 3.11+ is required:

```powershell
# Windows:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\start.ps1 -Steam
# Build the executable and release ZIP:
.\build.ps1
```

```sh
# Linux/macOS:
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/main.py --open-browser
# Or launch together with the game:
.venv/bin/python backend/main.py --steam
# Build a native executable and release archive:
./build.sh
```

Build on the target OS/architecture; PyInstaller is not a cross-compiler.
Build output is in `dist/`. Native release CI runs the unit suite and starts each
packaged executable from outside the repository to verify its assets, offline
vehicle-name lookup, history API and persistent database location. A real game
session is not exercised on the CI hosts.
