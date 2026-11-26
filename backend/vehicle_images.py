"""Cache official Wiki unit illustrations; never send battle data upstream."""

import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from runtime_paths import image_cache_dir


IMAGE_HOST = "https://static.encyclopedia.warthunder.com/images"
CACHE_DIR = image_cache_dir()
_lock = threading.Lock()
_unit_locks = {}
_retry_after = {}


def unit_id(raw):
    value = raw.split("/")[-1].lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,119}", value):
        raise ValueError("Invalid vehicle ID")
    return value


def get_image(raw, cache_dir=None):
    name = unit_id(raw)
    folder = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    path = folder / f"{name}.png"
    if path.is_file():
        return path.read_bytes()
    with _lock:
        lock = _unit_locks.setdefault(name, threading.Lock())
    with lock:
        if path.is_file():
            return path.read_bytes()
        if _retry_after.get(name, 0) > time.monotonic():
            return None
        try:
            request = urllib.request.Request(f"{IMAGE_HOST}/{name}.png", headers={"User-Agent":"WT-Dashboard/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                image = response.read(4*1024*1024+1)
            if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image)>4*1024*1024:
                raise ValueError("Not a supported image")
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder,delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(image)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return image
        except (OSError, ValueError, urllib.error.URLError):
            _retry_after[name] = time.monotonic()+300
            return None
