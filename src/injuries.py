"""Injury status, from ESPN's public (unofficial) injuries endpoint - one call
per sport covers every team, so this is cheap regardless of how many props
get scored. A hit-rate built from healthy-week history means something
different for a player who's questionable or already ruled out.
"""
import requests

from .name_match import normalize_name

BASE = "https://site.api.espn.com/apis/site/v2/sports"

LEAGUE_PATHS = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
}

# ESPN's free-text status strings, normalized and mapped to two tags:
# OUT (won't play - ruled out, on IL/IR, suspended) and RISK (game-time
# decision - may play a reduced or different role than their history reflects).
_OUT_STATUSES = {
    "out", "doubtful", "ir", "pup", "suspension", "suspended", "na",
    "60-day-il", "15-day-il", "10-day-il", "7-day-il",
}
_RISK_STATUSES = {"questionable", "day-to-day", "dtd", "probable", "game-time decision"}


def _tag_for(status_raw: str) -> str | None:
    status = (status_raw or "").strip().lower()
    if status in _OUT_STATUSES:
        return "OUT"
    if status in _RISK_STATUSES:
        return "RISK"
    return None


def fetch_injury_map(sport_key: str) -> dict[str, str]:
    """normalized player name -> 'OUT' | 'RISK'. Empty dict on any failure - never blocks scoring."""
    league_path = LEAGUE_PATHS.get(sport_key)
    if not league_path:
        return {}
    try:
        resp = requests.get(f"{BASE}/{league_path}/injuries", timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  [{sport_key}] injuries fetch failed ({e}) - continuing without injury flags")
        return {}

    injury_map: dict[str, str] = {}
    for team in data.get("injuries", []):
        for inj in team.get("injuries", []):
            tag = _tag_for(inj.get("status"))
            if not tag:
                continue
            name = (inj.get("athlete") or {}).get("displayName")
            if not name:
                continue
            key = normalize_name(name)
            if key not in injury_map or tag == "OUT":
                injury_map[key] = tag
    return injury_map
