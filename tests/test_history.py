import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
import history


class HistoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch("db.DB_PATH", Path(directory.name)/"stats.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db()
        conn = db.get_conn()
        with conn:
            conn.execute("INSERT INTO sessions(start_ts,end_ts,my_name) VALUES (1000,1100,'Local')")
            conn.execute("INSERT INTO sessions(start_ts,end_ts,xp,silver) VALUES (200,900,40,-20)")
        conn.close()

    def sample(self, ts, vehicle, x, speed=30):
        conn = db.get_conn()
        with conn:
            conn.execute("""INSERT INTO telemetry_samples(session_id,ts,state_json,indicators_json,map_obj_json,map_info_json,mission_json)
                            VALUES (1,?,'{}',?,?,?,?)""",
                         (ts,json.dumps({"type":vehicle,"army":"tank","speed":speed,"crew_current":3}),
                          json.dumps([{"icon":"Player","x":x,"y":0.3}]),
                          json.dumps({"valid":True,"map_min":[0,0],"map_max":[1000,1000]}),
                          json.dumps({"status":"success"})))
        conn.close()

    def test_vehicle_switches_and_respawns_do_not_join_routes(self):
        self.sample(1001,"tankModels/germ_jaguar_2",0.1)
        self.sample(1003,"tankModels/germ_jaguar_2",0.11)
        self.sample(1005,"tankModels/germ_wiesel_1_mk20",0.8)
        self.sample(1007,"tankModels/germ_wiesel_1_mk20",0.81)
        self.sample(1009,"tankModels/germ_wiesel_1_mk20",0.1)  # implausible jump = another run
        data = history.analyze_session(1)
        self.assertEqual(len(data["routes"]),3)
        self.assertAlmostEqual(data["summary"]["distance_m"],20)
        self.assertIsNone(data["summary"]["kills"])  # no event log, not zero kills
        self.assertEqual(len(data["routes"][0]["points"]),2)
        self.assertAlmostEqual(data["routes"][0]["distance_m"],10)
        self.assertEqual(data["routes"][0]["end_s"],3)
        self.assertEqual(data["summary"]["vehicles"][1]["duration_s"],2)
        self.assertEqual(data["routes"][2]["duration_s"],0)

    def test_inspector_ranges_and_complete_sample_belong_to_battle(self):
        self.sample(1001,"tankModels/germ_jaguar_2",0.1,speed=10)
        self.sample(1003,"tankModels/germ_jaguar_2",0.11,speed=40)
        data = history.analyze_session(1)
        vehicle = data["summary"]["vehicles"][0]
        speed = vehicle["parameters"]["indicators.speed"]
        self.assertEqual((speed["min"],speed["max"],speed["mean"],speed["count"]),(10,40,25,2))
        self.assertEqual(vehicle["average_speed_kmh"],25)
        self.assertEqual(vehicle["position_samples"],2)
        sample_id = data["routes"][0]["points"][0]["sample_id"]
        sample = history.get_sample(1,sample_id)
        self.assertEqual(sample["indicators"]["speed"],10)
        self.assertEqual(sample["map_obj"][0]["x"],0.1)
        self.assertEqual(sample["mission"]["status"],"success")
        self.assertIsNone(history.get_sample(2,sample_id))

    def test_period_vehicle_totals_include_battles_outside_page(self):
        self.sample(1001,"tankModels/germ_jaguar_2",0.1)
        history.ensure_metrics(1)
        data = history.list_history(limit=1,offset=1,now=1150)
        self.assertEqual(data["battles"][0]["id"],2)
        self.assertEqual(data["vehicle_totals"][0]["battles"],1)
        self.assertIsNone(data["vehicle_totals"][0]["xp"])
        self.assertIsNone(data["vehicle_totals"][0]["kills"])

    def test_hours_filter_uses_completion_and_unknown_rewards_stay_unknown(self):
        data = history.list_history(hours=100/3600, now=1150)
        self.assertEqual(data["total"],1)
        self.assertEqual(data["battles"][0]["id"],1)
        self.assertIsNone(data["totals"]["xp"])
        self.assertIsNone(data["totals"]["silver"])
        all_time = history.list_history(now=1150)
        self.assertEqual(all_time["totals"]["silver"],-20)
        self.assertEqual(all_time["totals"]["xp_battles"],1)

    def test_metric_cache_refreshes_when_reward_details_change(self):
        self.sample(1001,"tankModels/germ_jaguar_2",0.1)
        history.ensure_metrics(1)
        conn = db.get_conn()
        with conn:
            conn.execute("INSERT INTO battle_reward_records VALUES ('file',0,1099,1,100,400,?)",
                         (json.dumps({"totals":{},"vehicles":{"germ_jaguar_2":{"EXP":{"total":100},"WP":{"total":400}}}}),))
        conn.close()
        history.ensure_metrics(1)
        data = history.list_history(now=1150)
        self.assertEqual(data["battles"][0]["summary"]["vehicles"][0]["xp"],100)


if __name__ == "__main__":
    unittest.main()
