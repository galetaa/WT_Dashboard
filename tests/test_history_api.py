import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import db
import main


class HistoryApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patcher = patch("db.DB_PATH",Path(folder.name)/"stats.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db()
        conn = db.get_conn()
        with conn:
            conn.execute("INSERT INTO sessions(start_ts,end_ts,xp,silver) VALUES (1000,1100,100,-25)")
        conn.close()
        # ASGI transport does not start the real log importer/lifespan.
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_history_pagination_and_reward_export(self):
        response = await self.client.get("/api/history?limit=1")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["totals"]["xp"],100)
        self.assertEqual(response.json()["totals"]["silver"],-25)
        self.assertFalse(response.json()["has_more"])
        self.assertEqual((await self.client.get("/api/history?offset=1")).json()["battles"],[])
        export = await self.client.get("/api/stats/sessions/1/export")
        self.assertEqual(export.json()["session"]["xp"],100)
        self.assertIn("rewards",export.json())

    async def test_invalid_periods_and_unknown_battle_are_explicit_errors(self):
        for query in ("hours=0","hours=-1","limit=0","offset=-1"):
            with self.subTest(query=query):
                self.assertEqual((await self.client.get("/api/history?"+query)).status_code,422)
        self.assertEqual((await self.client.get("/api/history/9999")).status_code,404)


if __name__ == "__main__":
    unittest.main()
