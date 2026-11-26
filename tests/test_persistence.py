import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

import httpx

import db
import main
import poller


class BattlePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "stats.db"
        self.phase = "battle"
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))
        self.addAsyncCleanup(self.client.aclose)
        self.tracker = poller.TelemetryPoller()
        for target, value in (
            ("main.sync_history", lambda: None),
            ("db.DB_PATH", self.db_path),
            ("main.poller", self.tracker),
            ("poller.STATE_INTERVAL", 0.005),
            ("poller.MAP_INTERVAL", 0.01),
            ("poller.HUDMSG_INTERVAL", 0.01),
            ("poller.MATCH_END_DEBOUNCE", 0.05),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("poller.httpx.AsyncClient", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def respond(self, request):
        if self.phase == "disconnected":
            raise httpx.ConnectError("Game closed", request=request)
        data = {
            "/state": {"valid": True, "speed": 42},
            "/indicators": {"valid": True, "army": "tank", "type": "test_tank"},
            "/map_info.json": {"valid": self.phase == "battle"},
            "/map_obj.json": [],
            "/mission.json": {"status": "running"},
            "/hudmsg": {
                "events": [{"id": 1, "time": 1, "msg": "Test battle event"}]
                if self.tracker._session_id is not None
                and int(request.url.params.get("lastEvt", 0)) < 1 else [],
                "damage": [],
            },
        }
        if request.url.path == "/map.img":
            return httpx.Response(200, content=b"test-map", headers={"content-type": "image/jpeg"})
        return httpx.Response(200, json=data[request.url.path])

    async def wait_for(self, predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(0.005)
        await asyncio.wait_for(wait(), timeout=3)

    def recorded(self):
        sessions = db.list_sessions()
        return bool(sessions and db.get_session_telemetry(sessions[0]["id"])
                    and db.get_session(sessions[0]["id"])["events"])

    async def test_shutdown_saves_battle_and_history_without_roster(self):
        async with main.lifespan(main.app):
            await self.wait_for(self.recorded)
            sessions = await main.get_sessions()
            self.assertEqual(len(sessions), 1)
            session_id = sessions[0]["id"]
            self.assertIsNone(sessions[0]["my_name"])

        # Reopen the file independently, as after a server restart.
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIsNotNone(connection.execute("SELECT end_ts FROM sessions").fetchone()[0])
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM telemetry_samples").fetchone()[0], 0)
        db.init_db()
        export = json.loads((await main.export_session(session_id)).body)
        self.assertTrue(export["events"])
        self.assertTrue(export["telemetry"])
        self.assertIsNotNone(export["session"]["end_ts"])
        self.assertEqual(len(await main.get_sessions()), 1)

    async def test_disconnect_closes_battle_but_brief_outage_does_not_split_it(self):
        async with main.lifespan(main.app):
            await self.wait_for(self.recorded)
            session_id = self.tracker._session_id
            self.phase = "disconnected"
            await self.wait_for(lambda: not self.tracker.latest["connected"])
            self.phase = "battle"
            await self.wait_for(lambda: self.tracker.latest["connected"])
            self.assertEqual(self.tracker._session_id, session_id)
            self.assertEqual(len(db.list_sessions()), 1)
            self.phase = "disconnected"
            await self.wait_for(lambda: db.list_sessions()[0]["end_ts"] is not None)
            self.assertIsNone(self.tracker._session_id)
            self.assertEqual(len(db.list_sessions()), 1)

    async def test_hangar_return_closes_battle_and_keeps_its_records(self):
        async with main.lifespan(main.app):
            await self.wait_for(self.recorded)
            self.phase = "hangar"
            await self.wait_for(lambda: db.list_sessions()[0]["end_ts"] is not None)
            self.assertTrue(self.tracker.latest["connected"])
            self.assertFalse(self.tracker.latest["in_match"])
            self.assertTrue(self.recorded())


if __name__ == "__main__":
    unittest.main()
