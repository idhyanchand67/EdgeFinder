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
    "player_rush_yds": ["rushing_yards"],
    "player_rush_tds": ["rushing_tds"],
    "player_reception_yds": ["receiving_yards"],
    "player_receptions": ["receptions"],
    "player_reception_tds": ["receiving_tds"],
}

MARKET_LABELS = {
    "player_pass_yds": "Pass Yds", "player_pass_tds": "Pass TDs", "player_rush_yds": "Rush Yds",
    "player_rush_tds": "Rush TDs", "player_reception_yds": "Rec Yds",
    "player_receptions": "Receptions", "player_reception_tds": "Rec TDs",
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


# Odds API spells out full team names; nflverse uses these abbreviations.
TEAM_ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "Seattle Seahawks": "SEA", "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

MATCHUP_POSITIONS = ["QB", "RB", "WR", "TE"]


def compute_matchup_tiers(stats_df: pd.DataFrame) -> dict[tuple, str]:
    """(opponent_team, position) -> 'Tough' | 'Average' | 'Favorable' for that offense,
    based on fantasy points/game each defense has allowed to that position this window -
    the same signal, and the same red/yellow/green framing, as the sibling Draft War Room app."""
    rows = stats_df[stats_df["position"].isin(MATCHUP_POSITIONS)]
    allowed = rows.groupby(["opponent_team", "position"])["fantasy_points_ppr"].mean()

    tiers: dict[tuple, str] = {}
    for position in MATCHUP_POSITIONS:
        if position not in allowed.index.get_level_values("position"):
            continue  # e.g. a sparse-data window with no rows at all for this position
        by_team = allowed.xs(position, level="position").sort_values()
        n = len(by_team)
        if n < 3:
            continue
        for rank, (team, _value) in enumerate(by_team.items()):
            if rank < n / 3:
                tiers[(team, position)] = "Tough"       # allows the fewest points -> hard matchup
            elif rank < 2 * n / 3:
                tiers[(team, position)] = "Average"
            else:
                tiers[(team, position)] = "Favorable"   # allows the most points -> easy matchup
    return tiers


def filter_valid_games(results: list[dict]) -> list[dict]:
    """Drops any prop whose player's team still isn't one of the two teams in its
    attached game, even after current_roster.apply_current_teams() has corrected
    for offseason trades. Most "wrong team" cases turn out to be exactly that - a
    trade nflverse's game-log-only data hasn't caught up to yet - so run this
    *after* the roster correction, not instead of it. What's left here is either
    a genuine odds-feed data issue or a player this run's roster fetch missed."""
    kept, dropped = [], []
    for r in results:
        home = TEAM_ABBR.get(r.get("home_team"))
        away = TEAM_ABBR.get(r.get("away_team"))
        if r.get("team") in (home, away):
            kept.append(r)
        else:
            dropped.append(r)
    if dropped:
        names = sorted({r["player"] for r in dropped})
        print(f"  [nfl] dropped {len(dropped)} prop(s) still on an impossible team/game match "
              f"after roster correction: {names[:10]}" + (" ..." if len(names) > 10 else ""))
    return kept


def attach_matchups(results: list[dict], stats_df: pd.DataFrame) -> None:
    """Mutates each result in place, adding a 'matchup' tier for skill positions with a known opponent."""
    tiers = compute_matchup_tiers(stats_df)
    for r in results:
        r["matchup"] = None
        if r.get("position") not in MATCHUP_POSITIONS:
            continue
        home = TEAM_ABBR.get(r.get("home_team"))
        away = TEAM_ABBR.get(r.get("away_team"))
        team = r.get("team")
        opponent = away if team == home else (home if team == away else None)
        if opponent:
            r["matchup"] = tiers.get((opponent, r["position"]))


def _week_for(commence_time: str) -> tuple[int, int] | None:
    if not commence_time:
        return None
    dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    season_year = dt.year if dt.month >= 3 else dt.year - 1
    week = (dt.date() - _regular_season_start(season_year)).days // 7 + 1
    return season_year, week


def match_game(player_games: pd.DataFrame, commence_time: str):
    """nflverse has no game date, only season+week - convert the pick's commence_time
    to a week number (same rule as the preseason cutoff) and match on that instead."""
    season_week = _week_for(commence_time)
    if season_week is None:
        return None
    season, week = season_week
    matches = player_games[(player_games["season"] == season) & (player_games["week"] == week)]
    return matches.iloc[0] if len(matches) else None


SPORT = SportConfig(
    key="nfl",
    display_name="NFL",
    odds_sport_key="americanfootball_nfl",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["season", "week"],
    fetch_stats=fetch_stats,
    game_filter=_is_regular_season_game,
    match_game=match_game,
)
