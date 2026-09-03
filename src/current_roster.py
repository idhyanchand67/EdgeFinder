"""Current team assignment from ESPN's live rosters - not historical game logs.

nflverse's "team" is whatever team a player's last logged *game* was for, which
during the offseason can be a full season stale: a trade doesn't show up there
until the player has actually played a game for their new team. ESPN's roster
pages update on the trade itself, so this is what actually catches it.
"""
import requests

from .name_match import normalize_name

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"

# ESPN's team abbreviation differs from nflverse's for these two.
ESPN_TO_NFLVERSE_ABBR = {"LAR": "LA", "WSH": "WAS"}

NFLVERSE_ABBRS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
    "HOU", "IND", "JAX", "KC", "LV", "LAC", "LA", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]
_NFLVERSE_TO_ESPN_SLUG = {v: k for k, v in ESPN_TO_NFLVERSE_ABBR.items()} | {
    a: a for a in NFLVERSE_ABBRS if a not in ESPN_TO_NFLVERSE_ABBR.values()
}


def fetch_current_teams() -> dict[str, str]:
    """normalized player name -> nflverse-style team abbreviation. Empty dict on failure."""
    roster_map: dict[str, str] = {}
    for nflverse_abbr in NFLVERSE_ABBRS:
        espn_slug = _NFLVERSE_TO_ESPN_SLUG[nflverse_abbr].lower()
        try:
            resp = requests.get(f"{BASE}/{espn_slug}/roster", timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  [nfl] roster fetch failed for {nflverse_abbr} ({e}) - current-team lookup incomplete")
            continue
        for group in data.get("athletes", []):
            for item in group.get("items", []):
                name = item.get("displayName")
                if name:
                    roster_map[normalize_name(name)] = nflverse_abbr
    return roster_map


def apply_current_teams(results: list[dict], roster_map: dict[str, str]) -> None:
    """Overwrites each result's stale stats-derived team with the current one,
    where the player is found on a live roster. Leaves it alone otherwise -
    better a possibly-stale team than an incorrectly blanked one."""
    corrected = 0
    for r in results:
        current = roster_map.get(normalize_name(r["player"]))
        if current and current != r.get("team"):
            r["team"] = current
            corrected += 1
    if corrected:
        print(f"  [nfl] corrected {corrected} player(s) to their current team (traded since last logged game)")
