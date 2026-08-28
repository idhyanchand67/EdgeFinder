"""NBA: stats scraped from ESPN's public (unofficial) boxscore JSON - see espn_common.

stats.nba.com's own API blocks a lot of non-browser/datacenter traffic and
balldontlie.io now requires a signup key, so ESPN's endpoint is the one free,
no-key source that reliably answered from this environment during testing.
It's undocumented and could change without notice.
"""
import pandas as pd

from . import espn_common
from .base import SportConfig

LEAGUE_PATH = "basketball/nba"
DAYS_BACK = 45

MARKET_MAP = {
    "player_points": ["pts"],
    "player_rebounds": ["reb"],
    "player_assists": ["ast"],
    "player_threes": ["fg3m"],
    "player_points_rebounds_assists": ["pts", "reb", "ast"],
    "player_points_rebounds": ["pts", "reb"],
}

MARKET_LABELS = {
    "player_points": "Points", "player_rebounds": "Rebounds", "player_assists": "Assists",
    "player_threes": "3-Pointers Made",
    "player_points_rebounds_assists": "Pts+Reb+Ast", "player_points_rebounds": "Pts+Reb",
}


def _split_made(value: str) -> int:
    try:
        return int(str(value).split("-")[0])
    except (ValueError, IndexError):
        return 0


def _extract(team_block: dict, header: dict, game_date: str) -> list[dict]:
    team_abbr = team_block.get("team", {}).get("abbreviation")
    rows = []
    for group in team_block.get("statistics", []):
        keys = group.get("keys") or []
        for ath in group.get("athletes", []):
            if ath.get("didNotPlay") or not ath.get("stats"):
                continue
            stat = dict(zip(keys, ath["stats"]))
            athlete = ath.get("athlete", {})
            rows.append({
                "player_id": athlete.get("id"),
                "player_display_name": athlete.get("displayName"),
                "team": team_abbr,
                "position": (athlete.get("position") or {}).get("abbreviation"),
                "game_date": game_date,
                "pts": float(stat.get("points", 0) or 0),
                "reb": float(stat.get("rebounds", 0) or 0),
                "ast": float(stat.get("assists", 0) or 0),
                "stl": float(stat.get("steals", 0) or 0),
                "blk": float(stat.get("blocks", 0) or 0),
                "tov": float(stat.get("turnovers", 0) or 0),
                "fgm": _split_made(stat.get("fieldGoalsMade-fieldGoalsAttempted", "0-0")),
                "fg3m": _split_made(stat.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "0-0")),
                "ftm": _split_made(stat.get("freeThrowsMade-freeThrowsAttempted", "0-0")),
            })
    return rows


def fetch_stats(force: bool = False) -> pd.DataFrame:
    return espn_common.backfill("nba", LEAGUE_PATH, _extract, DAYS_BACK, force)


SPORT = SportConfig(
    key="nba",
    display_name="NBA",
    odds_sport_key="basketball_nba",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
)
