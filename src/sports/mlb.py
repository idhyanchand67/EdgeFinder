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
    "batter_runs_scored": ["bat_runs"],
    "batter_rbis": ["bat_rbi"],
    "batter_home_runs": ["bat_hr"],
    "batter_walks": ["bat_bb"],
    "batter_strikeouts": ["bat_so"],
    "pitcher_strikeouts": ["p_so"],
    "pitcher_hits_allowed": ["p_h"],
    "pitcher_walks": ["p_bb"],
    "pitcher_earned_runs": ["p_er"],
    "pitcher_outs": ["p_outs"],
}

MARKET_LABELS = {
    "batter_hits": "Hits", "batter_runs_scored": "Runs", "batter_rbis": "RBIs",
    "batter_home_runs": "Home Runs", "batter_walks": "Walks", "batter_strikeouts": "Batter Ks",
    "pitcher_strikeouts": "Pitcher Ks", "pitcher_hits_allowed": "Hits Allowed",
    "pitcher_walks": "Pitcher Walks", "pitcher_earned_runs": "Earned Runs", "pitcher_outs": "Outs Recorded",
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


SPORT = SportConfig(
    key="mlb",
    display_name="MLB",
    odds_sport_key="baseball_mlb",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
)
