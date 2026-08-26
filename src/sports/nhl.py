"""NHL: stats scraped from ESPN's public (unofficial) boxscore JSON - see espn_common."""
import pandas as pd

from . import espn_common
from .base import SportConfig

LEAGUE_PATH = "hockey/nhl"
DAYS_BACK = 45

MARKET_MAP = {
    "player_goals": ["goals"],
    "player_assists": ["assists"],
    "player_points": ["goals", "assists"],
    "player_shots_on_goal": ["shots_on_goal"],
    "player_blocked_shots": ["blocked_shots"],
    "player_goalie_saves": ["saves"],
}

MARKET_LABELS = {
    "player_goals": "Goals", "player_assists": "Assists", "player_points": "Points",
    "player_shots_on_goal": "Shots on Goal", "player_blocked_shots": "Blocked Shots",
    "player_goalie_saves": "Goalie Saves",
}

_GROUP_POSITION = {"forwards": "F", "defenses": "D", "goalies": "G"}


def _extract(team_block: dict, header: dict, game_date: str) -> list[dict]:
    team_abbr = team_block.get("team", {}).get("abbreviation")
    rows = []
    for group in team_block.get("statistics", []):
        group_name = group.get("name")
        position = _GROUP_POSITION.get(group_name)
        if position is None:
            continue  # e.g. the empty duplicate "skaters" summary group
        keys = group.get("keys") or []
        for ath in group.get("athletes", []):
            if not ath.get("stats"):
                continue
            stat = dict(zip(keys, ath["stats"]))
            athlete = ath.get("athlete", {})
            rows.append({
                "player_id": athlete.get("id"),
                "player_display_name": athlete.get("displayName"),
                "team": team_abbr,
                "position": position,
                "game_date": game_date,
                "goals": float(stat.get("goals", 0) or 0),
                "assists": float(stat.get("assists", 0) or 0),
                "shots_on_goal": float(stat.get("shotsTotal", 0) or 0),
                "blocked_shots": float(stat.get("blockedShots", 0) or 0),
                "saves": float(stat.get("saves", 0) or 0),
            })
    return rows


def fetch_stats(force: bool = False) -> pd.DataFrame:
    return espn_common.backfill("nhl", LEAGUE_PATH, _extract, DAYS_BACK, force)


SPORT = SportConfig(
    key="nhl",
    display_name="NHL",
    odds_sport_key="icehockey_nhl",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
)
