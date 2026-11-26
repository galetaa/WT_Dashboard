"""Exercise a native release bundle, including offline data and UI assets."""
import json
import os
import socket
import shutil
import sqlite3
import sys

import psutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from build_release import target_name


def main():
    repository = Path(__file__).resolve().parent.parent
    binary = "wt-dashboard.exe" if sys.platform=="win32" else "wt-dashboard"
    archive = repository / "dist" / (target_name() + (".zip" if sys.platform=="win32" else ".tar.gz"))
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        shutil.unpack_archive(archive,root / "extracted")
        executable = root / "extracted" / target_name() / binary
        # Detect a free port; run outside the repository to catch asset path bugs.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port = sock.getsockname()[1]
        env = {**os.environ, "WT_DATA_DIR":str(root / "data"), "WT_LOG_DIR":str(root / "empty-logs")}
        env.pop("WT_DB_PATH",None)
        database = root / "data/stats.db"
        database.parent.mkdir()
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE sessions(id INTEGER PRIMARY KEY,start_ts REAL,end_ts REAL,army TEXT,vehicle_type TEXT)")
        unit = "germ_leopard_I_a1"
        connection.execute("INSERT INTO sessions VALUES (1,1000,1100,'tank',?)",("tankModels/"+unit,))
        connection.execute("CREATE TABLE telemetry_samples(id INTEGER PRIMARY KEY,session_id INTEGER,ts REAL,state_json TEXT,indicators_json TEXT,map_obj_json TEXT,mission_json TEXT,map_info_json TEXT)")
        connection.execute("INSERT INTO telemetry_samples VALUES (1,1,1001,'{}',?,'[]','{}','{}')",(json.dumps({"type":"tankModels/"+unit,"speed":30}),))
        connection.commit()
        connection.close()
        process = subprocess.Popen([str(executable),"--no-browser","--port",str(port)],cwd=root,env=env)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path):
            with opener.open(f"http://127.0.0.1:{port}{path}",timeout=2) as response:
                return response.read()
        try:
            for _ in range(90):
                if process.poll() is not None:
                    raise RuntimeError("Packaged dashboard exited before startup")
                try:
                    get("/api/live")
                    break
                except (OSError,urllib.error.URLError):
                    time.sleep(1)
            else:
                raise TimeoutError("Packaged dashboard did not start")
            assert b"History &amp; statistics" in get("/") or b"History & statistics" in get("/")
            for name in ("history.js","history-inspector.js","history.css","vehicle-placeholder.svg"):
                assert get("/static/"+name),name
            assert len(json.loads(get("/static/vehicle_names.json"))) > 3000
            assert json.loads(get("/api/history"))["total"] == 1
            expected = json.loads((repository / "frontend/vehicle_names.json").read_text(encoding="utf-8"))[unit]
            assert json.loads(get("/api/history/1"))["summary"]["vehicles"][0]["name"] == expected
            assert (root / "data/stats.db").is_file()
            print("PASS: packaged server, frontend assets, vehicle names, history and persistent platform data path")
        finally:
            # CI owns this child. Battle shutdown is separately tested via lifespan.
            try:
                parent = psutil.Process(process.pid)
                owned = [*reversed(parent.children(recursive=True)), parent]
                for child in owned:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                _, alive = psutil.wait_procs(owned,timeout=10)
                for child in alive:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                psutil.wait_procs(alive,timeout=5)
            except psutil.NoSuchProcess:
                pass
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
