"""MLB: stats scraped from ESPN's public (unofficial) boxscore JSON - see espn_common.

Note: ESPN's compact box score line doesn't break out doubles/triples, so
total-bases props aren't computable from this data and are left out of
MARKET_MAP - only markets that map to a stat ESPN actually reports are included.
"""
import pandas as pd

from . import espn_common
from .base import SportConfig

LEAGUE_PATH = "baseball/mlb"
DAYS_BACK = 45

MARKET_MAP = {
    "batter_hits": ["bat_hits"],
    "batter_home_runs": ["bat_hr"],
    "batter_rbis": ["bat_rbi"],
    "batter_strikeouts": ["bat_so"],
    "pitcher_strikeouts": ["p_so"],
    "pitcher_outs": ["p_outs"],
}

MARKET_LABELS = {
    "batter_hits": "Hits", "batter_home_runs": "Home Runs", "batter_rbis": "RBIs",
    "batter_strikeouts": "Batter Ks", "pitcher_strikeouts": "Pitcher Ks", "pitcher_outs": "Outs Recorded",
}

_ZERO_ROW = {"bat_hits": 0.0, "bat_runs": 0.0, "bat_rbi": 0.0, "bat_hr": 0.0, "bat_bb": 0.0, "bat_so": 0.0,
             "p_so": 0.0, "p_h": 0.0, "p_bb": 0.0, "p_er": 0.0, "p_outs": 0.0}


def _outs_from_innings(value) -> float:
    s = str(value)
    whole, _, frac = s.partition(".")
    try:
        return int(whole or 0) * 3 + int(frac or 0)
    except ValueError:
        return 0.0


def _extract(team_block: dict, header: dict, game_date: str) -> list[dict]:
    team_abbr = team_block.get("team", {}).get("abbreviation")
    rows = []
    for group in team_block.get("statistics", []):
        keys = group.get("keys") or []
        is_pitching = "earnedRuns" in keys
        is_batting = "atBats" in keys
        if not (is_pitching or is_batting):
            continue
        for ath in group.get("athletes", []):
            if not ath.get("stats"):
                continue
            stat = dict(zip(keys, ath["stats"]))
            athlete = ath.get("athlete", {})
            row = {
                "player_id": athlete.get("id"),
                "player_display_name": athlete.get("displayName"),
                "team": team_abbr,
                "position": "P" if is_pitching else (athlete.get("position") or {}).get("abbreviation"),
                "game_date": game_date,
                **_ZERO_ROW,
            }
            if is_batting:
                row.update({
                    "bat_hits": float(stat.get("hits", 0) or 0),
                    "bat_runs": float(stat.get("runs", 0) or 0),
                    "bat_rbi": float(stat.get("RBIs", 0) or 0),
                    "bat_hr": float(stat.get("homeRuns", 0) or 0),
                    "bat_bb": float(stat.get("walks", 0) or 0),
                    "bat_so": float(stat.get("strikeouts", 0) or 0),
                })
            else:
                row.update({
                    "p_so": float(stat.get("strikeouts", 0) or 0),
                    "p_h": float(stat.get("hits", 0) or 0),
                    "p_bb": float(stat.get("walks", 0) or 0),
                    "p_er": float(stat.get("earnedRuns", 0) or 0),
                    "p_outs": _outs_from_innings(stat.get("fullInnings.partInnings", "0.0")),
                })
            rows.append(row)
    return rows


def fetch_stats(force: bool = False) -> pd.DataFrame:
    return espn_common.backfill("mlb", LEAGUE_PATH, _extract, DAYS_BACK, force)


# Odds API spells out full team names; this project's MLB stats already use
# ESPN's own abbreviations (see _extract above), so match on those directly.
TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI", "Athletics": "ATH", "Oakland Athletics": "ATH",
    "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW", "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE", "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KC", "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM", "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD",
    "San Francisco Giants": "SF", "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB", "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}

# Batting and pitching props need a different opponent difficulty signal each -
# baseball doesn't have a defense-vs-position matchup the way NFL/NHL do, since
# a batter faces one pitcher, not a defensive unit. 'batter' role -> use the
# opponent's pitching quality; 'pitcher' role -> use the opponent's batting quality.
_ROLE_BY_MARKET_PREFIX = {"batter_": "batter", "pitcher_": "pitcher"}


def _role_for_market(market: str) -> str | None:
    for prefix, role in _ROLE_BY_MARKET_PREFIX.items():
        if market.startswith(prefix):
            return role
    return None


def compute_matchup_tiers(stats_df: pd.DataFrame) -> dict[tuple, str]:
    """(team, role) -> 'Tough' | 'Average' | 'Favorable':
    - role 'batter': that team's pitching, by ERA over the cached window (lower
      ERA = tougher for opposing batters) - earned runs and outs summed per
      team per game first, so a bullpen game counts once, not per reliever.
    - role 'pitcher': that team's batting, by runs scored per game (more runs
      = tougher for the opposing pitcher)."""
    tiers: dict[tuple, str] = {}

    pitching_rows = stats_df[stats_df["p_outs"] > 0]
    if len(pitching_rows):
        per_game = pitching_rows.groupby(["team", "event_id"])[["p_er", "p_outs"]].sum()
        totals = per_game.groupby("team").sum()
        outs = totals["p_outs"].replace(0, pd.NA)
        era = ((totals["p_er"] / (outs / 3)) * 9).dropna()
        n = len(era)
        if n >= 3:
            for rank, (team, _) in enumerate(era.sort_values().items()):
                tiers[(team, "batter")] = "Tough" if rank < n / 3 else ("Average" if rank < 2 * n / 3 else "Favorable")

    runs_per_game = stats_df.groupby(["team", "event_id"])["bat_runs"].sum().groupby("team").mean()
    n2 = len(runs_per_game)
    if n2 >= 3:
        for rank, (team, _) in enumerate(runs_per_game.sort_values(ascending=False).items()):
            tiers[(team, "pitcher")] = "Tough" if rank < n2 / 3 else ("Average" if rank < 2 * n2 / 3 else "Favorable")

    return tiers


def attach_matchups(results: list[dict], stats_df: pd.DataFrame) -> None:
    """Mutates each result in place, adding a 'matchup' tier where the opponent is known."""
    tiers = compute_matchup_tiers(stats_df)
    for r in results:
        r["matchup"] = None
        role = _role_for_market(r.get("market", ""))
        if not role:
            continue
        home = TEAM_ABBR.get(r.get("home_team"))
        away = TEAM_ABBR.get(r.get("away_team"))
        team = r.get("team")
        opponent = away if team == home else (home if team == away else None)
        if opponent:
            r["matchup"] = tiers.get((opponent, role))


SPORT = SportConfig(
    key="mlb",
    display_name="MLB",
    odds_sport_key="baseball_mlb",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
    team_abbr=TEAM_ABBR,
)
