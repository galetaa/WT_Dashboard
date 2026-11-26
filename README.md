# WT Dashboard

A local telemetry dashboard for War Thunder. Polls the game's built-in local
API (`localhost:8111`, enabled automatically whenever a match is running) and
serves a live Friendly/Enemy Roster, vehicle equipment/damage state, and
per-session stats in your browser.

This only works while War Thunder itself is running on the **same machine** -
it has no way to see a match remotely.

## Running it

### Windows / Steam (this branch)

All battle-history features from `feat/battle-history-and-statistics` are
included: English UI, XP/SL import, vehicle illustrations, map playback,
telemetry charts, detailed inspectors and period statistics.

Download `wt-dashboard.exe` from a successful **Windows build and tests** run
under the fork's **Actions** tab (artifact `wt-dashboard-windows`). Extract
it from the artifact ZIP. Double-clicking the executable opens standalone
history/live mode; it stays open after the game closes.

For automatic game-session mode, create a Windows shortcut with this target:

```text
"C:\Tools\WT Dashboard\wt-dashboard.exe" --steam
```

Adjust the executable path. This starts War Thunder through Steam, waits up
to ten minutes for `aces.exe`, then opens the dashboard. When the game closes,
the server finishes saving telemetry/rewards and exits; its dedicated Edge or
Chrome app window also closes. Other browser windows and Steam stay open.
If neither browser is found, the default browser opens instead and its tab
may remain open. `--watch-game` waits for a game started separately, without
launching Steam. This integration runs when using the dashboard shortcut;
launching directly from the Steam Library requires `--watch-game` beforehand.

Windows saves the database in `%LOCALAPPDATA%\WTDashboard\stats.db` for both
source and executable launches. Illustrations are cached in
`%LOCALAPPDATA%\WTDashboard\cache\vehicle-images`. Back up the database before
replacing an older installation. To migrate history from a source checkout,
stop both dashboards and copy its `backend\stats.db` to that data folder.
`WT_DB_PATH` can explicitly select a different database file.

The importer finds `.game_logs` in the running game's install directory,
registered Steam install, or secondary Steam libraries. Set `WT_GAME_DIR`
to the game installation folder if discovery fails, or set `WT_LOG_DIR` to
the actual `.game_logs` folder (multiple Windows paths separated by `;`).
Client logs live in the game installation's `.game_logs` directory, as
[documented by Gaijin](https://support.gaijin.net/hc/en-us/articles/200070121-Bug-reports).

To run from source in PowerShell (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\start.ps1 -Steam
# Standalone history / live view:
.\start.ps1
```

`-NoBrowser` disables browser opening; `-Port 8766` selects another port.
Closing the console with Ctrl+C saves and stops the server. Keep standalone
mode open to browse history after playing. Windows builds and packaged-asset
smoke tests run automatically on pushes to `feat/windows-battle-history`.

### Linux / Steam

The Steam version uses the same local telemetry API; no Steam launch options
or game-directory settings are needed. Run the dashboard on the same computer
as the game.

On this computer, launch **War Thunder** from its applications-menu shortcut.
It launches the game through Steam and starts `wt-dashboard-session.service`.
Once the Steam game process appears, the dashboard starts and opens a dedicated
Thorium app window at `http://127.0.0.1:8765`. Both the dashboard server and its
window stop when the game process exits (normally within one second).

`Connected (hangar)` means it is connected and waiting for a battle; `In Match`
means a battle is being tracked. Returning to the hangar keeps the dashboard
running. Closing the dashboard window does not close the game.

The session waits up to ten minutes for the game to start. Opening the game
directly inside the Steam library does not trigger this shortcut integration.
The **WT Dashboard** shortcut remains available for manual use.

To stop the dashboard session without closing the game:

```sh
systemctl --user stop wt-dashboard-session.service
```

To view its log:

```sh
journalctl --user -u wt-dashboard-session.service -u wt-dashboard.service -n 50
```

The session starts from the War Thunder shortcut; it is not enabled at login.
Match history is saved in `backend/stats.db`. Keep this file when updating.
Recording is automatic during battles: telemetry and combat events are
committed to SQLite as they arrive. Stopping the dashboard finalizes the active
battle. Saved battles remain in the session dropdown even if player identity
could not be resolved; the database retains older battles beyond the 50 most
recent shown in that dropdown.
The managed window uses a separate profile in
`~/.local/share/wt-dashboard/browser-profile`.

Battle titles use the first real vehicle selected, ignoring the spawn-screen
`dummy_plane`. The offline English ID/name snapshot in
`frontend/vehicle_names.json` supports readable titles and player identification
from the combat log across all ten nations. Unknown IDs use nation-prefix and
punctuation normalization; identity remains unresolved when the evidence is
ambiguous, including players in vehicles sharing the same name.

The snapshot comes from the English short (`_1`) labels in
[War-Thunder-Datamine's units.csv](https://github.com/gszabi99/War-Thunder-Datamine/blob/master/lang.vromfs.bin_u/lang/units.csv),
restricted to its vehicle catalog. `frontend/vehicle_names.meta.json` records
the source commit, game version, checksums, coverage, and missing IDs. There
are no external requests for vehicle-name resolution; only the snapshot updater
fetches updated labels.

Refresh the snapshot, or reproduce it using the commit in the metadata:

```sh
python scripts/update_vehicle_names.py
python scripts/update_vehicle_names.py --ref COMMIT_FROM_METADATA
```

For a foreground launch from the source directory after installing the
dependencies into `.venv`, use `./start.sh`.

### Battle history and rewards

Open `http://127.0.0.1:8765/#history` or choose **History & statistics**.
The history works while the game is closed as long as the dashboard server is
running. It lists all recorded battles, with pagination, and aggregates entire
battles by completion time for today, the last N hours, or all time.

Each battle has a vehicle breakdown, observed travel distance, speed and crew
statistics, damage/repair durations, combat events, and a route timeline with
the underlying vehicle parameters. Select a vehicle to isolate its route and
reward breakdown. Different spawns and telemetry gaps are not joined by lines.
Run counts are inferred from telemetry, not treated as confirmed death counts.
The English history panel follows the live dashboard's compact styling. Vehicle
cards show official War Thunder Wiki illustrations, detailed observed statistics
and links to Wiki specifications. Images are downloaded on demand from
`static.encyclopedia.warthunder.com` and cached under
`%LOCALAPPDATA%\WTDashboard\cache\vehicle-images` on Windows, or
`$XDG_CACHE_HOME/wt-dashboard/vehicle-images` on Linux (default `~/.cache`). Only the public
unit ID is sent; if an image is unavailable, a labelled generic illustration is
shown. Cached images remain available offline.

Map playback supports background opacity, a grid, zoom, drag-to-pan, individual
runs, adjustable playback speed and clicking route points. The telemetry chart
shares the playhead with the map. Field inspection includes the exact current
value, sample minimum, maximum and mean for each vehicle. The complete sample
inspector exposes state, indicators, map objects, mission and map metadata as
expandable objects, with a sample JSON download.

Expand the damage/repair episodes, inferred player roster, searchable combat
timeline, mission context and full reward metadata for additional recorded
details. Events can be filtered to the local player, kills, losses or event type;
their time buttons move the playhead. Team assignments are inferred from combat
relationships rather than an official scoreboard. Period totals also include
per-vehicle aggregates across every matching battle, beyond the current page.
All stored telemetry and the imported reward breakdown can be downloaded from
the battle's JSON export link. Missing data cannot be reconstructed by the UI.

XP and SL are imported automatically from `received SessionStats` in the local
War Thunder `.clog` files, alongside combat messages missing from the HTTP API.
Linux defaults to `~/.config/WarThunder/.game_logs`; Windows also discovers
the game installation. Override with `WT_LOG_DIR`
(multiple directories can be separated with the OS path separator). Import is
incremental and idempotent, also scans old logs at startup, and is finalized
on shutdown. Decoded logs are never written to disk: only whitelisted battle
statistics, combat messages and the local nickname are retained.

**XP is the battle's reported EXP total**, which can differ from research
invested into a specific vehicle after modifiers. **SL is the reported WP
total including penalties, before repair/ammunition costs**; it is not a
wallet-balance change. Missing rewards/events stay unknown and coverage is
shown rather than replacing missing information with zero. The first import
and history calculation can take a short while, with progress in the panel.

Recorded map backgrounds are displayed by default when available. Old images
may have been captured before the new mission loaded and are explicitly marked
as unverified; disable **Map image** to use the coordinate grid instead. New
battles save a fresh in-match map image marked as verified.

### Easiest: download the exe

For this branch use the Actions artifact above. Upstream releases may not yet
include these features. Put `wt-dashboard.exe`
anywhere, and double-click it. A console window opens (that's the server;
closing it stops the dashboard) and your browser opens to the dashboard
automatically. No install, no Python required.

Match history is saved to `%LOCALAPPDATA%\WTDashboard\stats.db`.

### From source

Requires Python 3.11+.

```
pip install -r backend/requirements.txt
python -m uvicorn main:app --app-dir backend --port 8765
```

Then open `http://localhost:8765`.

## Building the exe yourself

```
./build.ps1
```

Run on Windows with Python 3.11+; the script uses `.venv` when present and
checks dependency/build failures. It can run from any working directory.
Produces `dist/wt-dashboard.exe` (PyInstaller, one-file bundle including the
frontend). See `build.ps1` for the exact flags if you need to reproduce it
without PowerShell.

## Notes

- `frontend/vehicles.json` is a snapshot of vehicle ids/premium status pulled
  from a third-party War Thunder vehicles API
  ([wtvehiclesapi.duckdns.org](https://wtvehiclesapi.duckdns.org)) for the
  premium-vehicle gold highlight and wiki links in the roster. It'll drift as
  new vehicles release - there's no automated refresh, regenerate it by
  re-pulling `GET /api/vehicles` from that API.
- The Friendly/Enemy Roster is built entirely from the in-game kill feed
  (there's no API for a real player list or map positions in multiplayer) -
  see the comments on `build_player_roster` in `backend/analysis.py` for how
  team/identity is inferred and what its coverage limits are.
