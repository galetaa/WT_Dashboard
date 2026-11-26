import asyncio
import sys
import time
import logging
import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response

import analysis
import db
import history
import vehicle_images
from rewards import RewardImporter
from poller import TelemetryPoller

poller = TelemetryPoller()
reward_importer = RewardImporter()
enrichment_lock = threading.Lock()
enrichment_status = {"running": False, "last_sync": None, "error": None}


def sync_history():
    with enrichment_lock:
        enrichment_status.update(running=True, error=None)
        try:
            reward_importer.sync()
            history.refresh_metrics()
            enrichment_status["last_sync"] = time.time()
        except Exception:
            enrichment_status["error"] = "History refresh failed. See the service log."
            logging.getLogger(__name__).exception("History update failed")
        finally:
            enrichment_status["running"] = False


async def enrich_history():
    while True:
        await asyncio.to_thread(sync_history)
        await asyncio.sleep(10)

# Frozen (PyInstaller) builds extract bundled data next to sys._MEIPASS, not
# next to this file - the build script adds frontend/ there under the same
# "frontend" name, so this resolves the same relative layout either way.
if getattr(sys, "frozen", False):
    FRONTEND_DIR = Path(sys._MEIPASS) / "frontend"
else:
    FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Some browsers will silently reuse a cached app.js/style.css from before a
# restart even with Cache-Control: no-store, if the original entry was cached
# without one (heuristic freshness never expires without a network check).
# A version query string on the asset URLs sidesteps this entirely - each
# restart gets URLs the browser has never cached before.
ASSET_VERSION = str(int(time.time()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(poller.run())
    enrichment_task = asyncio.create_task(enrich_history())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        enrichment_task.cancel()
        with suppress(asyncio.CancelledError):
            await enrichment_task
        await asyncio.to_thread(sync_history)


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("/static/app.js", f"/static/app.js?v={ASSET_VERSION}")
    html = html.replace("/static/style.css", f"/static/style.css?v={ASSET_VERSION}")
    html = html.replace("/static/history.js", f"/static/history.js?v={ASSET_VERSION}")
    html = html.replace("/static/history-inspector.js", f"/static/history-inspector.js?v={ASSET_VERSION}")
    html = html.replace("/static/history.css", f"/static/history.css?v={ASSET_VERSION}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.middleware("http")
async def no_cache_static(request, call_next):
    # This is an actively-edited local dashboard, not a deployed site - always
    # serve the current file/data from disk rather than letting the browser
    # cache things indefinitely. Originally just index.html/app.js/style.css
    # (StaticFiles sets no explicit Cache-Control by default, so browsers were
    # free to skip revalidation entirely and keep executing stale JS after an
    # edit + reload) - extended to /api/ too after the session dropdown was
    # confirmed to get stuck showing a stale (e.g. empty, pre-first-session)
    # response indefinitely, the same no-explicit-header symptom as the
    # earlier JS/CSS bug, just on a fetch() response instead of a script.
    response = await call_next(request)
    if (
        request.url.path.startswith("/static/")
        or request.url.path.startswith("/api/")
        or request.url.path == "/"
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/live")
async def get_live():
    return poller.latest


@app.get("/api/map-image")
async def get_map_image():
    if poller.map_image is None:
        return JSONResponse({"error": "no map image yet"}, status_code=404)
    return Response(
        content=poller.map_image,
        media_type=poller.map_image_type,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/stats/sessions")
async def get_sessions():
    # A recorded battle still has useful telemetry even if the kill feed
    # never provided enough information to resolve the player's identity.
    return db.list_sessions()


@app.get("/api/history")
def get_history(hours: float | None = Query(None, gt=0, le=87600), today: bool = False,
                limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    result = history.list_history(hours=hours, today=today, limit=limit, offset=offset)
    result["import_status"] = {**enrichment_status, "logs": dict(reward_importer.status)}
    return result


@app.post("/api/history/sync")
async def sync_history_now():
    await asyncio.to_thread(sync_history)
    return {**enrichment_status, "logs": dict(reward_importer.status)}


@app.get("/api/history/{session_id}")
def get_history_detail(session_id: int):
    result = history.analyze_session(session_id)
    return result if result is not None else JSONResponse({"error": "Battle not found"}, status_code=404)


@app.get("/api/history/{session_id}/samples/{sample_id}")
def get_history_sample(session_id: int, sample_id: int):
    result = history.get_sample(session_id, sample_id)
    return result if result is not None else JSONResponse({"error":"Sample not found in this battle"},status_code=404)


@app.get("/api/vehicle-images/{unit_id}")
def get_vehicle_image(unit_id: str):
    try:
        image = vehicle_images.get_image(unit_id)
    except ValueError:
        return JSONResponse({"error":"Invalid vehicle ID"},status_code=400)
    return (Response(image,media_type="image/png") if image else
            JSONResponse({"error":"Vehicle image unavailable"},status_code=404))


@app.get("/api/stats/sessions/{session_id}")
async def get_session(session_id: int):
    result = db.get_session(session_id)
    if result is None:
        return {"error": "not found"}
    return result


@app.get("/api/stats/sessions/{session_id}/telemetry")
async def get_session_telemetry(session_id: int):
    return db.get_session_telemetry(session_id)


@app.get("/api/stats/sessions/{session_id}/map-image")
async def get_session_map_image(session_id: int):
    image, image_type = db.get_session_map_image(session_id)
    if image is None:
        return JSONResponse({"error": "no map image for this session"}, status_code=404)
    return Response(content=image, media_type=image_type or "image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/stats/sessions/{session_id}/kill-locations")
async def get_session_kill_locations(session_id: int):
    return analysis.compute_kill_locations(session_id)


@app.get("/api/stats/sessions/{session_id}/roster")
async def get_session_roster(session_id: int):
    return analysis.build_player_roster(session_id)


@app.get("/api/stats/sessions/{session_id}/export")
async def export_session(session_id: int):
    result = db.get_session_export(session_id)
    if result is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    conn = db.get_conn()
    try:
        result["rewards"] = history.reward_details(conn, session_id)
    finally:
        conn.close()
    headers = {"Content-Disposition": f"attachment; filename=wt-session-{session_id}.json"}
    return JSONResponse(result, headers=headers)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    queue = poller.subscribe()
    try:
        while True:
            data = await queue.get()
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        poller.unsubscribe(queue)


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    port = 8765

    # Only auto-open a browser for the packaged build - running from source
    # during development already has a browser tab open/managed manually,
    # and popping a new one on every restart would get old fast.
    if getattr(sys, "frozen", False):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    uvicorn.run(app, host="127.0.0.1", port=port)
