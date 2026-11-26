"""Read bundled assets, but keep writable data outside the executable bundle."""
import os
import sys
from pathlib import Path


def frontend_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).resolve().parent.parent / "frontend"


def data_dir():
    if os.environ.get("WT_DATA_DIR"):
        return Path(os.environ["WT_DATA_DIR"]).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()
        return base / "WTDashboard"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/WTDashboard"
    base = Path(os.environ["XDG_DATA_HOME"]) if os.environ.get("XDG_DATA_HOME") else Path.home() / ".local/share"
    return base / "wt-dashboard"


def database_path():
    configured = os.environ.get("WT_DB_PATH")
    if configured:
        path = Path(configured).expanduser().resolve()
    elif sys.platform in {"win32", "darwin"} or getattr(sys, "frozen", False):
        path = data_dir() / "stats.db"
    else:
        # Preserve existing Linux source checkouts and their recorded battles.
        path = Path(__file__).resolve().parent / "stats.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def image_cache_dir():
    if sys.platform == "win32":
        return data_dir() / "cache/vehicle-images"
    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/WTDashboard/vehicle-images"
    return Path(os.getenv("XDG_CACHE_HOME", str(Path.home()/".cache"))) / "wt-dashboard/vehicle-images"
