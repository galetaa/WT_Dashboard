"""Read bundled assets, but keep writable data outside the executable bundle."""
import os
import sys
from pathlib import Path


def frontend_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).resolve().parent.parent / "frontend"


def data_dir():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WTDashboard"


def database_path():
    configured = os.environ.get("WT_DB_PATH")
    if configured:
        path = Path(configured).expanduser().resolve()
    elif sys.platform == "win32" or getattr(sys, "frozen", False):
        path = data_dir() / "stats.db"
    else:
        path = Path(__file__).resolve().parent / "stats.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def image_cache_dir():
    if sys.platform == "win32":
        return data_dir() / "cache" / "vehicle-images"
    return Path(os.getenv("XDG_CACHE_HOME", str(Path.home()/".cache"))) / "wt-dashboard/vehicle-images"
