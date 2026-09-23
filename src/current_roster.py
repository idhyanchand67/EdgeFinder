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
    """normalized player name -> nflverse-style team abbreviation. Empty dict on failure.

    A name that shows up on more than one roster is a real name collision, not
    a hypothetical one - confirmed in production against Jacoby Brissett, whose
    team got silently set to whichever roster happened to be scanned last. A
    collided name is left out of the map entirely rather than guessing: an
    unmatched player already falls back to their stale-but-real stats-derived
    team in apply_current_teams, which is the safe behavior for "can't tell
    which one" too, not just "not found at all"."""
    teams_by_name: dict[str, set[str]] = {}
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
                    teams_by_name.setdefault(normalize_name(name), set()).add(nflverse_abbr)

    collisions = {name: teams for name, teams in teams_by_name.items() if len(teams) > 1}
    if collisions:
        sample = ", ".join(f"{name} ({'/'.join(sorted(teams))})" for name, teams in list(collisions.items())[:5])
        print(f"  [nfl] {len(collisions)} name(s) matched more than one roster, left uncorrected: {sample}"
              + (" ..." if len(collisions) > 5 else ""))
    return {name: next(iter(teams)) for name, teams in teams_by_name.items() if len(teams) == 1}


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
