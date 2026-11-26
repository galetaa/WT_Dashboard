"""Import whitelisted battle-result fields from the user's local CLog files.

CLog is cyclic XOR, as documented by klensy/wt-tools and the public key in
https://github.com/cyberofficial/clog-decrypter/blob/master/clog_decomp.py.
Decoded logs can contain login credentials: never persist or log their text.
Only SessionStats, the local player's display name, and byte cursors survive.
"""

import copy
import datetime as dt
import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

import db
import analysis


KEY = bytes([
    130,135,151,64,141,139,70,11,187,115,148,3,229,179,131,83,
    105,107,131,218,149,175,74,35,135,229,151,172,36,88,175,54,
    78,225,90,249,241,1,75,177,173,182,76,76,250,116,40,105,
    194,139,17,23,213,182,71,206,179,183,205,85,254,249,193,36,
    255,174,144,46,73,108,78,9,146,129,78,103,188,107,156,222,
    177,15,104,186,139,128,68,5,135,94,243,78,254,9,151,50,
    192,173,159,233,187,253,77,6,145,80,137,110,224,232,238,153,
    83,0,60,166,184,34,65,50,177,189,245,40,80,224,114,174,
])
TRANSLATIONS = [bytes(value ^ key for value in range(256)) for key in range(256)]
RESULT = re.compile(r"^\s*([\d.]+).*received SessionStats (\S+) (WP|EXP): (.*)$")
FIELD = re.compile(r"([\w-]+)\[([^\]]*)\]")
PLAYER = re.compile(r"onStateChanged\(\).*? n:'(.*?)' .*?\(l=1\)")
HUD_MESSAGE = re.compile(r"^\s*([\d.]+).*HUD\s+hud_mp_ui_message - text = '(.*)'\s*$")
LOG_NAME = re.compile(r"^(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})__")


def xor_bytes(data, offset=0):
    decoded = bytearray(len(data))
    for index in range(min(len(KEY), len(data))):
        decoded[index::len(KEY)] = data[index::len(KEY)].translate(
            TRANSLATIONS[KEY[(offset + index) % len(KEY)]]
        )
    return bytes(decoded)


def parse_fields(text):
    result = {}
    for key, raw in FIELD.findall(text):
        tokens = raw.split()
        if not tokens:
            continue
        if all(":" in token for token in tokens):
            result[key] = {token.split(":")[0]: int(token.split(":")[1]) for token in tokens}
        else:
            values = [int(token) for token in tokens]
            result[key] = values[0] if len(values) == 1 else values
    return result


def parse_chunk(decoded, cursor, base_time):
    """Consume complete lines; leave a partial line and pending result for the next poll."""
    state = copy.deepcopy(cursor)
    records = []
    length = decoded.rfind(b"\n") + 1
    offset = state.get("offset", 0)
    for raw in decoded[:length].splitlines(keepends=True):
        line = raw.decode("utf-8", errors="replace")
        match = RESULT.match(line)
        if match:
            seconds, unit, currency, fields = match.groups()
            timestamp = base_time + float(seconds)
            if unit == "sum" and (not state.get("pending") or
                                   (currency in state["pending"]["totals"] and timestamp-state["pending"]["ts"] > 0.05)):
                if state.get("pending"):
                    records.append(state["pending"])
                state["pending"] = {
                    "ts": timestamp, "source_offset": offset,
                    "player": state.get("player"), "totals": {}, "vehicles": {},
                }
            pending = state.get("pending")
            if pending:
                target = pending["totals"] if unit == "sum" else pending["vehicles"].setdefault(unit, {})
                target[currency] = parse_fields(fields)
        else:
            hud = HUD_MESSAGE.match(line)
            if hud:
                message = hud[2]
                if "\x1b" in message:
                    prefix, rest = message.split("\x1b", 1)
                    if prefix.startswith("td") and len(prefix) <= 5:
                        message = "\x1b" + rest
                message = re.sub(r"\x1b(?:\d{3})?", "", message).strip()
                parsed = analysis.parse_combat_message(message)
                if parsed:
                    records.append({"combat": True, "ts": base_time+float(hud[1]),
                                    "source_offset": offset, "msg": message, "parsed": parsed})
            seconds = re.match(r"^\s*([\d.]+)\s", line)
            # Other threads can write between the WP/EXP/vehicle lines.
            # Keep the result together until its block is definitely over.
            if state.get("pending") and (
                "stat_get_exp" in line or "clear SessionStats" in line or
                (seconds and base_time + float(seconds[1])-state["pending"]["ts"] > 2)
            ):
                records.append(state.pop("pending"))
            player = PLAYER.search(line)
            if player:
                state["player"] = player[1]
        offset += len(raw)
    state["offset"] = offset
    # Checkpoint a complete total even if the log stops directly after stats.
    # Keep pending so later vehicle lines update the SAME source-offset record.
    if state.get("pending"):
        records.append(copy.deepcopy(state["pending"]))
    return records, state


def log_directories():
    configured = os.environ.get("WT_LOG_DIR")
    if configured:
        return [Path(value).expanduser() for value in configured.split(os.pathsep) if value]
    home = Path.home()
    return [home / ".config/WarThunder/.game_logs",
            Path(os.getenv("LOCALAPPDATA", str(home))) / "WarThunder/.game_logs"]


def attach_records(conn):
    records = conn.execute("SELECT * FROM battle_reward_records WHERE session_id IS NULL ORDER BY ts").fetchall()
    for record in records:
        timestamp = record["ts"]
        candidates = conn.execute(
            """SELECT id, start_ts, end_ts, my_name FROM sessions
               WHERE start_ts<=? AND COALESCE(end_ts, ?)>=?
               ORDER BY ABS(COALESCE(end_ts, ?)-?) LIMIT 2""",
            (timestamp + 15, time.time(), timestamp - 120, time.time(), timestamp),
        ).fetchall()
        if not candidates:
            continue
        session = candidates[0]
        if session["end_ts"] and abs(session["end_ts"] - timestamp) > 120:
            continue
        if len(candidates) > 1:
            distances = [abs((item["end_ts"] or time.time()) - timestamp) for item in candidates]
            if abs(distances[0] - distances[1]) < 5:
                continue
        details = json.loads(record["details_json"])
        player = details.get("player")
        if player and session["my_name"] and not session["my_name"].casefold().endswith(player.casefold()):
            continue
        conn.execute("UPDATE battle_reward_records SET session_id=? WHERE source=? AND source_offset=?",
                     (session["id"], record["source"], record["source_offset"]))
    # Re-apply the newest observation, without summing repeated reports.
    for session in conn.execute("SELECT DISTINCT session_id FROM battle_reward_records WHERE session_id IS NOT NULL").fetchall():
        record = conn.execute(
            "SELECT * FROM battle_reward_records WHERE session_id=? ORDER BY ts DESC, source_offset DESC LIMIT 1",
            (session[0],),
        ).fetchone()
        conn.execute(
            """UPDATE sessions SET xp=?, silver=?, rewards_ts=?, rewards_source=?
               WHERE id=? AND (rewards_ts IS NULL OR rewards_ts<=?)
               AND (rewards_ts IS NOT ? OR xp IS NOT ? OR silver IS NOT ?)""",
            (record["xp"], record["silver"], record["ts"], "clog_session_stats", session[0], record["ts"],
             record["ts"], record["xp"], record["silver"]),
        )
        player = json.loads(record["details_json"]).get("player")
        if player:
            conn.execute("UPDATE sessions SET my_name=? WHERE id=? AND my_name IS NULL", (player, session[0]))
    for event in conn.execute("SELECT * FROM imported_combat_events WHERE session_id IS NULL ORDER BY ts").fetchall():
        candidates = conn.execute(
            """SELECT id,start_ts FROM sessions WHERE start_ts<=? AND COALESCE(end_ts,?)>=?
               ORDER BY CASE WHEN start_ts<=? THEN 0 ELSE 1 END, start_ts DESC LIMIT 1""",
            (event["ts"]+5,time.time(),event["ts"]-3,event["ts"]),
        ).fetchall()
        if not candidates:
            continue
        session = candidates[0]
        existing = conn.execute("""SELECT 1 FROM events WHERE session_id=? AND msg=? AND ABS(ts-?)<=4
                                AND COALESCE(json_extract(raw_json,'$.source'),'')<>'clog' LIMIT 1""",
                                (session["id"],event["msg"],event["ts"])).fetchone()
        if not existing:
            parsed = json.loads(event["parsed_json"])
            conn.execute(
                """INSERT INTO events(session_id,ts,match_time,kind,msg,verb,actor_name,actor_vehicle,
                   target_name,target_vehicle,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (session["id"],event["ts"],max(0,event["ts"]-session["start_ts"]),"damage",event["msg"],
                 parsed["verb"],parsed["actor_name"],parsed["actor_vehicle"],parsed["target_name"],
                 parsed["target_vehicle"],json.dumps({"source":"clog","msg":event["msg"]})),
            )
        conn.execute("UPDATE imported_combat_events SET session_id=? WHERE source=? AND source_offset=?",
                     (session["id"],event["source"],event["source_offset"]))
    # Resolve a plain local nickname to its one observed clan-decorated name.
    for session in conn.execute("SELECT id,my_name FROM sessions WHERE my_name IS NOT NULL").fetchall():
        player = session["my_name"]
        names = {row[0] for row in conn.execute(
            "SELECT actor_name FROM events WHERE session_id=? UNION SELECT target_name FROM events WHERE session_id=?",
            (session["id"],session["id"]),
        ) if row[0] and (row[0].casefold()==player.casefold() or row[0].casefold().endswith(" "+player.casefold()))}
        if len(names) == 1 and player not in names:
            conn.execute("UPDATE sessions SET my_name=? WHERE id=?", (next(iter(names)),session["id"]))


class RewardImporter:
    def __init__(self, directories=None):
        self.directories = directories
        self.lock = threading.Lock()
        self.status = {"running": False, "files": 0, "processed": 0, "errors": 0, "last_sync": None}

    def sync(self):
        with self.lock:
            directories = self.directories if self.directories is not None else log_directories()
            files = sorted({path for directory in directories
                            if directory.is_dir() for path in directory.glob("*.clog")})
            self.status.update(running=True, files=len(files), processed=0, errors=0)
            try:
                for path in files:
                    try:
                        self._import_file(path)
                    except (OSError, ValueError, sqlite3.Error):
                        # Never include a decoded line (or credentials) in errors.
                        self.status["errors"] += 1
                        logging.getLogger(__name__).warning("Could not import battle results from %s", path.name)
                    self.status["processed"] += 1
                with db.get_conn() as conn:
                    attach_records(conn)
                conn.close()
            finally:
                self.status.update(running=False, last_sync=time.time())

    def _import_file(self, path):
        match = LOG_NAME.match(path.name)
        if not match:
            return
        base_time = dt.datetime.strptime(match[1], "%Y_%m_%d_%H_%M_%S").timestamp()
        source = str(path.resolve())
        conn = db.get_conn()
        try:
            row = conn.execute("SELECT cursor_json FROM log_import_state WHERE source=?", (source,)).fetchone()
            cursor = json.loads(row[0]) if row else {"offset": 0}
            if cursor.get("version") != 2:
                cursor = {"offset": 0, "version": 2}
            if cursor["offset"] > path.stat().st_size:
                cursor = {"offset": 0}
            with path.open("rb") as stream:
                stream.seek(cursor["offset"])
                raw = stream.read()
            if not raw:
                return
            records, cursor = parse_chunk(xor_bytes(raw, cursor["offset"]), cursor, base_time)
            with conn:
                for record in records:
                    if record.get("combat"):
                        conn.execute("INSERT OR IGNORE INTO imported_combat_events(source,source_offset,ts,msg,parsed_json) VALUES (?,?,?,?,?)",
                                     (source,record["source_offset"],record["ts"],record["msg"],json.dumps(record["parsed"])))
                        continue
                    xp = record["totals"].get("EXP", {}).get("total")
                    silver = record["totals"].get("WP", {}).get("total")
                    if xp is None and silver is None:
                        continue
                    conn.execute(
                        """INSERT INTO battle_reward_records
                           (source,source_offset,ts,xp,silver,details_json) VALUES (?,?,?,?,?,?)
                           ON CONFLICT(source,source_offset) DO UPDATE SET
                           xp=COALESCE(excluded.xp,battle_reward_records.xp),
                           silver=COALESCE(excluded.silver,battle_reward_records.silver),
                           details_json=excluded.details_json""",
                        (source, record["source_offset"], record["ts"], xp, silver,
                         json.dumps(record, ensure_ascii=False)),
                    )
                conn.execute("INSERT OR REPLACE INTO log_import_state VALUES (?,?)", (source, json.dumps(cursor)))
        finally:
            conn.close()
