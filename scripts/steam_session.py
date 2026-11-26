"""Keep the dashboard and its dedicated window alive for one Steam game run."""

import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


START_TIMEOUT = 600
POLL_INTERVAL = 1
GAME_APP_ID = b"SteamAppId=236390"


def game_running(proc_root: Path = Path("/proc")) -> bool:
    for process in proc_root.iterdir():
        if not process.name.isdigit():
            continue
        try:
            # Steam's own command line also contains the app ID, even after
            # the game exits. Only a real game process counts.
            if (process / "comm").read_text().strip().lower() not in {"aces", "aces.exe"}:
                continue
            environment = (process / "environ").read_bytes().split(b"\0")
            if GAME_APP_ID in environment:
                return True
        except (OSError, UnicodeError):
            # Processes can disappear while /proc is being read.
            continue
    return False


def systemctl(*arguments: str):
    subprocess.run(["systemctl", "--user", *arguments], check=True)


def run_session():
    print("Waiting for War Thunder (Steam app 236390)...", flush=True)
    deadline = time.monotonic() + START_TIMEOUT
    while not game_running():
        if time.monotonic() >= deadline:
            print("Game did not start within 10 minutes; ending session.", flush=True)
            return
        time.sleep(POLL_INTERVAL)

    print("War Thunder started; starting dashboard.", flush=True)
    systemctl("start", "wt-dashboard.service")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(30):
        if not game_running():
            return
        try:
            with opener.open("http://127.0.0.1:8765/api/live", timeout=1) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("Dashboard did not become ready")

    systemctl("start", "wt-dashboard-window.service")
    while game_running():
        time.sleep(POLL_INTERVAL)
    print("War Thunder exited; closing dashboard and its window.", flush=True)


if __name__ == "__main__":
    # The session service's ExecStopPost stops the dashboard and its window
    # on normal exit, startup failure, or explicit service stop.
    run_session()
