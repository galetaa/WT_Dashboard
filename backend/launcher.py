"""Standalone and Steam session entry points for Windows, Linux and macOS."""
import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from contextlib import suppress
from pathlib import Path

from game_paths import game_processes
from runtime_paths import data_dir


def browser_executable():
    candidates = []
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "thorium-browser", "chrome"):
        executable = shutil.which(name)
        if executable:
            candidates.append(Path(executable))
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if os.environ.get(variable):
            root = Path(os.environ[variable])
            candidates.extend([root / "Microsoft/Edge/Application/msedge.exe",
                               root / "Google/Chrome/Application/chrome.exe"])
    if sys.platform == "darwin":
        for folder in (Path("/Applications"), Path.home() / "Applications"):
            candidates.extend([folder / "Google Chrome.app/Contents/MacOS/Google Chrome",
                               folder / "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                               folder / "Chromium.app/Contents/MacOS/Chromium"])
    return next((p for p in candidates if p.is_file()), None)


def open_browser(url, managed):
    executable = browser_executable() if managed else None
    if not executable:
        webbrowser.open(url)
        if managed:
            print("Edge/Chrome not found; the default browser tab may remain open after the game exits.", flush=True)
        return None
    import psutil
    folder = data_dir() / "browser-profiles"
    folder.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="session-", dir=folder, ignore_cleanup_errors=True)
    try:
        process = subprocess.Popen([str(executable), f"--app={url}", f"--user-data-dir={profile.name}",
                                    "--no-first-run", "--no-default-browser-check"])
        return psutil.Process(process.pid), profile
    except Exception:
        profile.cleanup()
        raise


def close_browser(browser):
    if browser is None:
        return
    import psutil
    process, profile = browser
    try:
        children = process.children(recursive=True)
        owned = [*reversed(children), process]
        for item in owned:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                item.terminate()
        _, alive = psutil.wait_procs(owned, timeout=5)
        for item in alive:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                item.kill()
        psutil.wait_procs(alive, timeout=3)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    finally:
        profile.cleanup()


async def wait_for_game(timeout):
    deadline = time.monotonic() + timeout
    while not game_processes():
        if time.monotonic() >= deadline:
            raise TimeoutError("War Thunder did not start before the timeout.")
        await asyncio.sleep(1)


async def supervise(server, url, watch_game=False, show_browser=False):
    browser = None
    async def monitor():
        nonlocal browser
        while not server.started:
            if server.should_exit:
                return
            await asyncio.sleep(.1)
        if show_browser:
            # Managed browser creation stays in this task, so cancellation cannot
            # abandon a newly opened window before its handle is retained.
            browser = open_browser(url, managed=watch_game)
        missed = 0
        while not server.should_exit:
            if watch_game:
                missed = 0 if game_processes() else missed + 1
                if missed >= 3:
                    print("War Thunder exited; saving history and closing dashboard.", flush=True)
                    server.should_exit = True
                    return
            await asyncio.sleep(1)
    task = asyncio.create_task(monitor())
    def stop_on_monitor_failure(done):
        if not done.cancelled() and done.exception() is not None:
            server.should_exit = True
    task.add_done_callback(stop_on_monitor_failure)
    try:
        await server.serve()
    finally:
        # Uvicorn's lifespan completes before closing our dedicated browser.
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        close_browser(browser)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="War Thunder dashboard and recorded battle history")
    parser.add_argument("--steam", action="store_true", help="Launch War Thunder through Steam and follow its lifetime")
    parser.add_argument("--watch-game", action="store_true", help="Wait for the game, then close the dashboard when it exits")
    parser.add_argument("--start-timeout", type=float, default=600, help="Seconds to wait for the game (default: 600)")
    parser.add_argument("--port", type=int, default=8765)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--open-browser", dest="browser", action="store_true")
    group.add_argument("--no-browser", dest="browser", action="store_false")
    parser.set_defaults(browser=None)
    args = parser.parse_args(argv)
    if args.start_timeout <= 0 or not 1 <= args.port <= 65535:
        parser.error("Timeout must be positive and port must be between 1 and 65535.")
    return args


def run(app, argv=None):
    import uvicorn
    args = parse_args(argv)
    watch = args.steam or args.watch_game
    if args.steam:
        if sys.platform == "win32":
            os.startfile("steam://rungameid/236390")
        else:
            command = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([command, "steam://rungameid/236390"], check=True)
    async def session():
        if watch:
            print("Waiting for War Thunder (aces / aces.exe)…", flush=True)
            await wait_for_game(args.start_timeout)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, loop="asyncio"))
        show = args.browser if args.browser is not None else watch or getattr(sys, "frozen", False)
        await supervise(server, f"http://127.0.0.1:{args.port}/#history", watch, show)
    try:
        asyncio.run(session())
    except KeyboardInterrupt:
        pass
    except TimeoutError as error:
        raise SystemExit(str(error))
