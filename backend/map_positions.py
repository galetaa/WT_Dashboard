"""Distinguish the driven vehicle from the game's post-death spectator marker.

War Thunder also uses icon=Player on a blue allied vehicle while spectating,
although /indicators can still describe the vehicle that was destroyed.
Recognize the observed yellow/blue/green/red palette; keep colourless legacy
samples usable rather than treating icon=Player as unconditional ownership.
"""
import math


def marker_role(obj):
    if obj.get("icon") != "Player":
        return "not_player"
    rgb = obj.get("color[]")
    if not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
        color = obj.get("color")
        if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
            try:
                rgb = [int(color[offset:offset+2], 16) for offset in (1, 3, 5)]
            except ValueError:
                rgb = None
    if (not isinstance(rgb, (list, tuple)) or len(rgb) < 3
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) and 0 <= v <= 255 for v in rgb[:3])):
        return "unknown"
    r, g, b = rgb[:3]
    if r >= 180 and g >= 100 and b < 100 and r >= g:
        return "own"
    if (b > r + 40 and b > g + 40 or g > r + 40 and g > b + 40
            or r > 180 and g < 100 and b < 100):
        return "other"
    return "unknown"


def valid_position(obj):
    return all(isinstance(obj.get(key), (int, float)) and not isinstance(obj[key], bool)
               and math.isfinite(obj[key]) and 0 <= obj[key] <= 1 for key in ("x", "y"))


def own_player_position(objects):
    candidates = [obj for obj in objects if obj.get("icon") == "Player" and valid_position(obj)]
    confirmed = [obj for obj in candidates if marker_role(obj) == "own"]
    if confirmed:
        return confirmed[0] if len(confirmed) == 1 else None
    legacy = [obj for obj in candidates if marker_role(obj) == "unknown"]
    return legacy[0] if len(legacy) == 1 else None


def spectator_view(objects):
    players = [obj for obj in objects if obj.get("icon") == "Player"]
    return bool(players) and all(marker_role(obj) == "other" for obj in players)
