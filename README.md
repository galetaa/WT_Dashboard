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

Install `backend/requirements.txt` in a virtual environment and run
`python backend/main.py --open-browser`. For Linux source users, `./start.sh`
continues to use `.venv`; `scripts/steam_session.py` supports the earlier local
systemd integration. The new portable `--steam` launcher does not require it.

Run tests from the repository root with `PYTHONPATH=backend python -m unittest
discover -s tests -v` (PowerShell: set `$env:PYTHONPATH = 'backend'` first).
`./build.sh` builds Linux/macOS archives, and `./build.ps1` builds the Windows ZIP.
The native release workflow tests/builds all four OS/architecture combinations.
Release archives contain the executable and platform guide. `SHA256SUMS` in each
published release allows archive integrity checks.
