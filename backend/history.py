"""Battle history, observed vehicle runs, and time-window aggregates."""

import datetime as dt
import hashlib
import json
import math
import time
from collections import Counter

import analysis
import db
import kill_review


def vehicle_label(raw):
    key = (raw or "").split("/")[-1]
    return analysis.VEHICLE_NAMES.get(key, key.replace("_", " "))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def amount(fields):
    if "total" in fields:
        return fields["total"]
    def total(value):
        if isinstance(value, dict):
            return sum(total(item) for item in value.values())
        if isinstance(value, list):
            return sum(total(item) for item in value)
        return value if number(value) else 0
    return sum(total(value) for key, value in fields.items() if key not in {"free", "total"})


def reward_details(conn, session_id):
    row = conn.execute(
        "SELECT details_json FROM battle_reward_records WHERE session_id=? ORDER BY ts DESC,source_offset DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def own_name(name, player):
    return bool(name and player and (name.casefold() == player.casefold()
                                    or name.casefold().endswith(" " + player.casefold())))


def reward_revision(rewards):
    return hashlib.sha256(json.dumps(rewards, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def get_sample(session_id, sample_id):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM telemetry_samples WHERE session_id=? AND id=?",(session_id,sample_id)).fetchone()
        if row is None:
            return None
        return {key[:-5] if key.endswith("_json") else key:
                json.loads(value) if key.endswith("_json") and value is not None else value
                for key,value in dict(row).items()}
    finally:
        conn.close()


def parameter_summary(target, namespace, values):
    for key, value in values.items():
        if key in {"valid","army","type"}:
            continue
        path = f"{namespace}.{key}"
        entry = target.setdefault(path, {"count":0,"numeric_count":0,"min":None,"max":None,"sum":0,"last":None})
        entry["count"] += 1
        entry["last"] = value
        if number(value):
            entry["numeric_count"] += 1
            entry["min"] = value if entry["min"] is None else min(entry["min"],value)
            entry["max"] = value if entry["max"] is None else max(entry["max"],value)
            entry["sum"] += value


def analyze_session(session_id, include_routes=True):
    data = db.get_session(session_id)
    if data is None:
        return None
    session, events = data["session"], data["events"]
    conn = db.get_conn()
    try:
        rewards = reward_details(conn, session_id)
        vehicles, runs, active, previous = {}, [], None, None
        outcome, sample_id, sample_count, last_time = None, 0, 0, session["start_ts"]
        fields = set()
        latest_map, latest_mission = {}, {}
        valid_position_count = 0
        review_frames = []

        def get_vehicle(raw):
            if raw not in vehicles:
                vehicles[raw] = {
                    "type": raw, "name": vehicle_label(raw), "samples": 0,
                    "duration_s": 0, "moving_s": 0, "distance_m": 0,
                    "max_speed_kmh": 0, "minimum_crew": None, "runs": 0,
                    "condition_seconds": {}, "xp": None, "silver": None,
                    "condition_episodes": {}, "speed_sum":0, "speed_samples":0,
                    "position_samples":0,
                }
                if include_routes:
                    vehicles[raw]["parameters"] = {}
            return vehicles[raw]

        for row in conn.execute("SELECT * FROM telemetry_samples WHERE session_id=? ORDER BY id", (session_id,)):
            sample_id, timestamp = row["id"], row["ts"]
            sample_count += 1
            last_time = timestamp
            indicators = json.loads(row["indicators_json"] or "{}")
            mission = json.loads(row["mission_json"] or "{}")
            map_info = json.loads(row["map_info_json"] or "{}")
            objects = json.loads(row["map_obj_json"] or "[]")
            if include_routes:
                review_frames.append({"sample_id":row["id"],"ts":timestamp,"indicators":indicators,
                    "state":json.loads(row["state_json"] or "{}"),"objects":objects,"map_info":map_info})
            if mission.get("status"):
                outcome = mission["status"]
            if mission:
                latest_mission = mission
            if map_info.get("valid"):
                latest_map = map_info
            raw = indicators.get("type")
            if not analysis.is_real_vehicle(raw) or map_info.get("valid") is False:
                active, previous = None, None
                continue
            vehicle = get_vehicle(raw)
            vehicle["samples"] += 1
            fields.update(indicators)
            speed = abs(indicators.get("speed", 0)) if number(indicators.get("speed")) else None
            if speed is None:
                state = json.loads(row["state_json"] or "{}")
                speed = abs(state.get("TAS, km/h", 0))
            vehicle["max_speed_kmh"] = max(vehicle["max_speed_kmh"], speed)
            vehicle["speed_sum"] += speed
            vehicle["speed_samples"] += 1
            if include_routes:
                parameter_summary(vehicle["parameters"],"indicators",indicators)
                parameter_summary(vehicle["parameters"],"state",json.loads(row["state_json"] or "{}"))
            crew = indicators.get("crew_current")
            if number(crew):
                vehicle["minimum_crew"] = crew if vehicle["minimum_crew"] is None else min(crew, vehicle["minimum_crew"])
            gap = timestamp - previous["ts"] if previous else 0
            if not active or active["vehicle"] != raw or gap > 15 or gap < 0:
                vehicle["runs"] += 1
                active = {"id": len(runs) + 1, "vehicle": raw, "name": vehicle["name"],
                          "spawn": vehicle["runs"], "start_s": timestamp - session["start_ts"], "points": [],
                          "end_s": timestamp-session["start_ts"],"distance_m":0,"samples":0,"duration_s":0}
                runs.append(active)
                previous = None
                gap = 0
            own = next((obj for obj in objects if obj.get("icon") == "Player"
                        and number(obj.get("x")) and number(obj.get("y"))
                        and 0 <= obj["x"] <= 1 and 0 <= obj["y"] <= 1), None)
            point = None
            if own:
                valid_position_count += 1
                vehicle["position_samples"] += 1
                point = {"t": round(timestamp - session["start_ts"], 3), "x": own["x"], "y": own["y"],
                         "speed": speed, "crew": crew}
                if previous and previous.get("point") and gap > 0:
                    bounds_min, bounds_max = map_info.get("map_min"), map_info.get("map_max")
                    if bounds_min and bounds_max:
                        old = previous["point"]
                        distance = math.hypot((point["x"]-old["x"])*(bounds_max[0]-bounds_min[0]),
                                              (point["y"]-old["y"])*(bounds_max[1]-bounds_min[1]))
                        limit = 1500 if indicators.get("army") == "air" else 100
                        if distance / gap <= limit:
                            vehicle["distance_m"] += distance
                            active["distance_m"] += distance
                        else:
                            # Respawn/teleport in the same model: never draw a line across the map.
                            vehicle["runs"] += 1
                            active = {"id": len(runs)+1, "vehicle": raw, "name": vehicle["name"],
                                      "spawn": vehicle["runs"], "start_s": point["t"], "points": [],
                                      "end_s":point["t"],"distance_m":0,"samples":0,"duration_s":0}
                            runs.append(active)
                            previous = None
                            gap = 0
            if previous and 0 <= gap <= 15:
                vehicle["duration_s"] += gap
                if speed > 1:
                    vehicle["moving_s"] += gap
            for key, value in indicators.items():
                if value and (key.endswith(("_broken", "_dead", "_damaged"))
                              or key in {"burns", "is_repairing", "is_repairing_auto"}):
                    vehicle["condition_seconds"][key] = vehicle["condition_seconds"].get(key, 0) + gap
                    if not previous or not previous["indicators"].get(key):
                        vehicle["condition_episodes"][key] = vehicle["condition_episodes"].get(key, 0)+1
            active["samples"] += 1
            active["end_s"] = timestamp-session["start_ts"]
            active["duration_s"] += gap
            if include_routes:
                observation = point or {"t": round(timestamp-session["start_ts"], 3),
                                        "x": None, "y": None, "speed": speed, "crew": crew}
                observation["indicators"] = indicators
                observation["state"] = json.loads(row["state_json"] or "{}")
                observation["sample_id"] = row["id"]
                active["points"].append(observation)
            previous = {"ts": timestamp, "point": point, "indicators":indicators}

        if rewards:
            for unit, values in rewards.get("vehicles", {}).items():
                existing = next((key for key in vehicles if key.split("/")[-1] == unit), None)
                vehicle = get_vehicle(existing or unit)
                vehicle["xp"] = amount(values["EXP"]) if "EXP" in values else None
                vehicle["silver"] = amount(values["WP"]) if "WP" in values else None
                if include_routes:
                    vehicle["rewards"] = values
        player = session["my_name"] or session["provisional_my_name"]
        kills = deaths = None
        if player and events:
            kills = sum(analysis.is_lethal(event["verb"]) and own_name(event["actor_name"], player) for event in events)
            deaths = sum(analysis.is_lethal(event["verb"]) and own_name(event["target_name"], player) for event in events)
        normalized_types = Counter(analysis.normalize_vehicle_id(raw) for raw in vehicles)
        for raw, vehicle in vehicles.items():
            norm = analysis.normalize_vehicle_id(raw)
            vehicle["kills"] = vehicle["deaths"] = None
            if player and events and normalized_types[norm] == 1:
                vehicle["kills"] = sum(analysis.is_lethal(event["verb"]) and own_name(event["actor_name"], player)
                                       and analysis.normalize_vehicle_name(event["actor_vehicle"]) == norm for event in events)
                vehicle["deaths"] = sum(analysis.is_lethal(event["verb"]) and own_name(event["target_name"], player)
                                        and analysis.normalize_vehicle_name(event["target_vehicle"]) == norm for event in events)
            vehicle["average_speed_kmh"] = vehicle.pop("speed_sum")/vehicle.pop("speed_samples") if vehicle["samples"] else None
            vehicle.pop("speed_sum",None)
            vehicle.pop("speed_samples",None)
            vehicle["stationary_s"] = max(0,vehicle["duration_s"]-vehicle["moving_s"])
            if include_routes:
                for parameter in vehicle["parameters"].values():
                    parameter["mean"] = parameter.pop("sum")/parameter["numeric_count"] if parameter["numeric_count"] else None
                    parameter.pop("sum",None)
        end_time = session["end_ts"] or last_time
        summary = {
            "version": 3,
            "player": player, "outcome": outcome,
            "end_ts": session["end_ts"], "reward_revision": reward_revision(rewards),
            "duration_s": max(0, end_time-session["start_ts"]),
            "sample_count": sample_count, "event_count": len(events), "sample_id": sample_id,
            "kills": kills, "deaths": deaths,
            "distance_m": sum(vehicle["distance_m"] for vehicle in vehicles.values()),
            "position_samples": valid_position_count,
            "vehicles": list(vehicles.values()),
        }
        if not include_routes:
            return summary
        return {"session": session, "summary": summary, "rewards": rewards,
                "routes": runs, "events": events, "telemetry_fields": sorted(fields),
                "map_info":latest_map, "mission":latest_mission,
                "roster":analysis.build_player_roster(session_id),
                "kill_reviews":kill_review.build_reviews(session,events,review_frames)}
    finally:
        conn.close()


def ensure_metrics(session_id):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT summary_json,sample_id,event_count FROM session_metrics WHERE session_id=?", (session_id,)).fetchone()
        sample_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM telemetry_samples WHERE session_id=?", (session_id,)).fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM events WHERE session_id=?", (session_id,)).fetchone()[0]
        player_row = conn.execute("SELECT COALESCE(my_name,provisional_my_name),end_ts FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row and row[1] == sample_id and row[2] == event_count:
            cached = json.loads(row[0])
            if (cached.get("version") == 3 and cached.get("player") == player_row[0] and cached.get("end_ts") == player_row[1]
                    and cached.get("reward_revision") == reward_revision(reward_details(conn, session_id))):
                return
        summary = analyze_session(session_id, include_routes=False)
        if summary is not None:
            with conn:
                conn.execute("INSERT OR REPLACE INTO session_metrics VALUES (?,?,?,?)",
                             (session_id, sample_id, event_count, json.dumps(summary)))
    finally:
        conn.close()


def refresh_metrics():
    conn = db.get_conn()
    sessions = [row[0] for row in conn.execute("SELECT id FROM sessions ORDER BY id DESC")]
    conn.close()
    for session_id in sessions:
        ensure_metrics(session_id)


def list_history(hours=None, today=False, limit=50, offset=0, now=None):
    now = now if now is not None else time.time()
    cutoff = None
    if today:
        cutoff = dt.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elif hours is not None:
        cutoff = now - hours*3600
    conn = db.get_conn()
    try:
        where, params = ("WHERE COALESCE(end_ts,start_ts)>=?", [cutoff]) if cutoff is not None else ("", [])
        rows = conn.execute(f"SELECT {db.SESSION_COLUMNS} FROM sessions {where} ORDER BY COALESCE(end_ts,start_ts) DESC", params).fetchall()
        metrics = {row[0]: json.loads(row[1]) for row in conn.execute("SELECT session_id,summary_json FROM session_metrics")}
    finally:
        conn.close()
    battles = []
    for row in rows:
        battle = dict(row)
        battle["summary"] = metrics.get(row["id"])
        battles.append(battle)
    summaries = [battle["summary"] for battle in battles if battle["summary"]]
    xp_values = [battle["xp"] for battle in battles if battle["xp"] is not None]
    silver_values = [battle["silver"] for battle in battles if battle["silver"] is not None]
    known_events = [summary for summary in summaries if summary["kills"] is not None]
    totals = {
        "battles": len(battles), "xp": sum(xp_values) if xp_values else None,
        "silver": sum(silver_values) if silver_values else None,
        "xp_battles": len(xp_values), "silver_battles": len(silver_values),
        "wins": sum(summary["outcome"] == "success" for summary in summaries),
        "losses": sum(summary["outcome"] == "fail" for summary in summaries),
        "duration_s": sum(max(0, (battle["end_ts"] or now)-battle["start_ts"]) for battle in battles),
        "distance_m": sum(summary["distance_m"] for summary in summaries),
        "kills": sum(summary["kills"] for summary in known_events) if known_events else None,
        "deaths": sum(summary["deaths"] for summary in known_events) if known_events else None,
        "events_battles": len(known_events), "analyzed_battles": len(summaries),
    }
    vehicle_totals = {}
    for battle in battles:
        for vehicle in (battle["summary"] or {}).get("vehicles",[]):
            target = vehicle_totals.setdefault(vehicle["type"],{
                "type":vehicle["type"],"name":vehicle["name"],"battles":0,
                "duration_s":0,"moving_s":0,"distance_m":0,"kills":None,"deaths":None,
                "xp":None,"silver":None,"max_speed_kmh":0,"reward_battles":0,
            })
            target["battles"] += 1
            for key in ("duration_s","moving_s","distance_m"):
                target[key] += vehicle[key]
            for key in ("kills","deaths","xp","silver"):
                if vehicle.get(key) is not None:
                    target[key] = (target[key] or 0)+vehicle[key]
            target["reward_battles"] += vehicle.get("xp") is not None
            target["max_speed_kmh"] = max(target["max_speed_kmh"],vehicle["max_speed_kmh"])
    return {"battles": battles[offset:offset+limit], "total": len(battles), "totals": totals,
            "vehicle_totals":list(vehicle_totals.values()),
            "since": cutoff, "as_of": now, "has_more": offset+limit < len(battles)}
