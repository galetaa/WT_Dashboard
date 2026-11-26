import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
from rewards import RewardImporter, parse_chunk, xor_bytes


class RewardImportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        patcher = patch("db.DB_PATH", self.folder / "stats.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db()
        self.base = dt.datetime(2026, 11, 24, 20).timestamp()
        conn = db.get_conn()
        with conn:
            conn.execute("INSERT INTO sessions(start_ts,end_ts) VALUES (?,?)", (self.base+10,self.base+75))
        conn.close()
        self.log = self.folder / "2026_11_24_20_00_00__1.clog"

    def test_xor_preserves_arbitrary_chunk_offsets(self):
        raw = bytes(range(256)) * 4
        encrypted = xor_bytes(raw)
        self.assertEqual(xor_bytes(encrypted), raw)
        self.assertEqual(xor_bytes(encrypted[137:783], 137), raw[137:783])

    def test_interleaved_lines_and_partial_tail_keep_one_complete_result(self):
        text = (b" 70.00 [D] received SessionStats sum WP: penalty[a:-300 g:0] total[-12]\n"
                b" 70.00 [D] unrelated renderer diagnostic\n"
                b" 70.00 [D] received SessionStats sum EXP: kill-g[166] total[2404]\n"
                b" 70.00 [D] received SessionStats germ_jaguar_2 EXP: kill-g[166] mis[100]\n"
                b" 70.00 [D] incomplete")
        records, cursor = parse_chunk(text, {"offset":0}, self.base)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["totals"]["WP"]["total"], -12)
        self.assertEqual(records[0]["totals"]["EXP"]["total"], 2404)
        self.assertEqual(records[0]["vehicles"]["germ_jaguar_2"]["EXP"]["kill-g"], 166)
        self.assertEqual(cursor["offset"], text.rfind(b"\n")+1)

    def test_repeat_import_does_not_double_count_and_keeps_no_credentials(self):
        text = (" 12.00 onStateChanged() MULP pid:1 n:'Local Player' IN_FLIGHT t=2 f=2203(l=1)\n"
                " 13.00 login token=SECRET_MUST_NOT_PERSIST\n"
                " 70.00 [D] received SessionStats sum WP: kill-g[500] penalty[a:-100] total[400]\n"
                " 70.00 [D] received SessionStats sum EXP: kill-g[100] total[100]\n"
                " 70.00 [D] received SessionStats germ_jaguar_2 EXP: kill-g[100]\n"
                " 75.00 [D] result finished\n")
        self.log.write_bytes(xor_bytes(text.encode()))
        importer = RewardImporter([self.folder])
        importer.sync()
        importer.sync()
        session = db.get_session(1)["session"]
        self.assertEqual((session["xp"],session["silver"],session["my_name"]), (100,400,"Local Player"))
        conn = db.get_conn()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM battle_reward_records").fetchone()[0], 1)
        serialized = "".join(row[0] for row in conn.execute("SELECT details_json FROM battle_reward_records"))
        serialized += "".join(row[0] for row in conn.execute("SELECT cursor_json FROM log_import_state"))
        self.assertNotIn("SECRET_MUST_NOT_PERSIST", serialized)
        conn.close()

    def test_unknown_and_ambiguous_results_are_not_assigned(self):
        # Equally close overlapping captures do not justify attributing money.
        conn = db.get_conn()
        with conn:
            conn.execute("INSERT INTO sessions(start_ts,end_ts) VALUES (?,?)", (self.base+12,self.base+76))
        conn.close()
        text = " 70.00 received SessionStats sum EXP: total[100]\n 75.00 finished\n"
        self.log.write_bytes(xor_bytes(text.encode()))
        RewardImporter([self.folder]).sync()
        self.assertIsNone(db.get_session(1)["session"]["xp"])
        self.assertIsNone(db.get_session(2)["session"]["xp"])

    def test_colored_combat_messages_are_recovered_and_deduplicated(self):
        text = (" 12.00 onStateChanged() MULP pid:1 n:'Local Player' IN_FLIGHT t=2 f=2203(l=1)\n"
                " 60.00 HUD  hud_mp_ui_message - text = 'tds\x1b012=SQ= Local Player (Jaguar 2)\x1b \x1b019destroyed\x1b \x1b009Enemy (T-55A)\x1b'\n"
                " 70.00 received SessionStats sum EXP: total[100]\n 75.00 finished\n")
        self.log.write_bytes(xor_bytes(text.encode()))
        importer = RewardImporter([self.folder])
        importer.sync()
        importer.sync()
        session = db.get_session(1)
        self.assertEqual(session["session"]["my_name"],"=SQ= Local Player")
        self.assertEqual(len(session["events"]),1)
        event = session["events"][0]
        self.assertEqual(event["actor_name"],"=SQ= Local Player")
        self.assertEqual(event["verb"],"destroyed")
        self.assertNotIn("\x1b",event["msg"])
        with patch("db.time.time",return_value=self.base+61):
            db.log_event(1,"damage",{"id":123},msg=event["msg"])
        self.assertEqual(len(db.get_session(1)["events"]),1)

    def test_repeated_real_hits_are_not_collapsed_as_cross_source_duplicates(self):
        message = "tds\x1b012Local (Jaguar 2)\x1b \x1b019critically damaged\x1b \x1b009Enemy (T-55A)\x1b"
        text = f" 60.00 HUD hud_mp_ui_message - text = '{message}'\n 61.00 HUD hud_mp_ui_message - text = '{message}'\n"
        self.log.write_bytes(xor_bytes(text.encode()))
        importer = RewardImporter([self.folder])
        importer.sync()
        importer.sync()
        self.assertEqual(len(db.get_session(1)["events"]),2)


if __name__ == "__main__":
    unittest.main()
