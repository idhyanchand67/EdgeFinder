"""NFL: stats from nflverse's free weekly player-stats release (no API key)."""
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from .. import config
from .base import SportConfig

NFLVERSE_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv"
)
SEASONS_BACK = 3

MARKET_MAP = {
    "player_pass_yds": ["passing_yards"],
    "player_pass_tds": ["passing_tds"],
    "player_pass_completions": ["completions"],
    "player_pass_attempts": ["attempts"],
    "player_pass_interceptions": ["interceptions"],
    "player_rush_yds": ["rushing_yards"],
    "player_rush_attempts": ["carries"],
    "player_rush_tds": ["rushing_tds"],
    "player_reception_yds": ["receiving_yards"],
    "player_receptions": ["receptions"],
    "player_reception_tds": ["receiving_tds"],
    "player_rush_reception_yds": ["rushing_yards", "receiving_yards"],
    "player_pass_rush_reception_yds": ["passing_yards", "rushing_yards", "receiving_yards"],
    "player_rush_reception_tds": ["rushing_tds", "receiving_tds"],
    "player_pass_rush_reception_tds": ["passing_tds", "rushing_tds", "receiving_tds"],
}

MARKET_LABELS = {
    "player_pass_yds": "Pass Yds", "player_pass_tds": "Pass TDs", "player_pass_completions": "Completions",
    "player_pass_attempts": "Pass Att", "player_pass_interceptions": "INTs", "player_rush_yds": "Rush Yds",
    "player_rush_attempts": "Carries", "player_rush_tds": "Rush TDs", "player_reception_yds": "Rec Yds",
    "player_receptions": "Receptions", "player_reception_tds": "Rec TDs",
    "player_rush_reception_yds": "Rush+Rec Yds", "player_pass_rush_reception_yds": "Pass+Rush+Rec Yds",
    "player_rush_reception_tds": "Rush+Rec TDs", "player_pass_rush_reception_tds": "Total TDs",
}


def fetch_stats(force: bool = False) -> pd.DataFrame:
    cache = config.stats_cache_path("nfl")
    if cache.exists() and not force:
        age_hours = (time.time() - cache.stat().st_mtime) / 3600
        if age_hours < 12:
            print(f"[nfl] using cached {cache.name} ({age_hours:.1f}h old)")
        else:
            _download(cache)
    else:
        _download(cache)

    df = pd.read_csv(cache, low_memory=False)
    df = df[df["season_type"] == "REG"]
    current_season = int(df["season"].max())
    df = df[df["season"] >= current_season - SEASONS_BACK + 1]
    df = df.rename(columns={"recent_team": "team"})
    df = df.sort_values(["season", "week"])
    return df.reset_index(drop=True)


def _download(cache_path) -> None:
    print(f"[nfl] downloading player stats from {NFLVERSE_STATS_URL} ...")
    resp = requests.get(NFLVERSE_STATS_URL, timeout=120)
    resp.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    print(f"[nfl] saved {len(resp.content) / 1e6:.1f} MB to {cache_path}")


def _regular_season_start(year: int) -> date:
    """NFL Week 1 always kicks off the Thursday after Labor Day (first Monday of September)."""
    sept_first = date(year, 9, 1)
    labor_day = sept_first + timedelta(days=(7 - sept_first.weekday()) % 7)
    return labor_day + timedelta(days=3)


def _is_regular_season_game(prop: dict) -> bool:
    """Excludes preseason games - backups play starter snaps, so recent-history
    hit rates (built from real regular-season usage) don't predict them well."""
    commence = prop.get("commence_time")
    if not commence:
        return True  # can't tell - don't drop it over missing data
    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
    # Jan/Feb games (playoffs, Super Bowl) belong to the September-year before them.
    season_year = dt.year if dt.month >= 3 else dt.year - 1
    return dt.date() >= _regular_season_start(season_year)


SPORT = SportConfig(
    key="nfl",
    display_name="NFL",
    odds_sport_key="americanfootball_nfl",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["season", "week"],
    fetch_stats=fetch_stats,
    game_filter=_is_regular_season_game,
)
