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
    opponent = espn_common.opponent_abbr(team_abbr, header)
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
                "opponent_team": opponent,
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


# Odds API spells out full team names; this project's NBA stats already use
# ESPN's own abbreviations (see _extract above), so match on those directly.
TEAM_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NO", "New York Knicks": "NY",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SA", "Toronto Raptors": "TOR", "Utah Jazz": "UTAH",
    "Washington Wizards": "WSH",
}


def compute_matchup_tiers(stats_df: pd.DataFrame) -> dict[tuple, str]:
    """(opponent_team, position) -> 'Tough' | 'Average' | 'Favorable', by points/game
    allowed to that position - same shape as NFL's fantasy-points-allowed model,
    now that opponent_team is tracked per row (added specifically for this)."""
    rows = stats_df.dropna(subset=["opponent_team", "position"])
    if rows.empty:
        return {}
    allowed = rows.groupby(["opponent_team", "position"])["pts"].mean()

    tiers: dict[tuple, str] = {}
    for position in rows["position"].unique():
        if position not in allowed.index.get_level_values("position"):
            continue
        by_team = allowed.xs(position, level="position").sort_values()
        n = len(by_team)
        if n < 3:
            continue
        for rank, (team, _value) in enumerate(by_team.items()):
            if rank < n / 3:
                tiers[(team, position)] = "Tough"
            elif rank < 2 * n / 3:
                tiers[(team, position)] = "Average"
            else:
                tiers[(team, position)] = "Favorable"
    return tiers


def attach_matchups(results: list[dict], stats_df: pd.DataFrame) -> None:
    """Mutates each result in place, adding a 'matchup' tier where the opponent and position are known."""
    tiers = compute_matchup_tiers(stats_df)
    for r in results:
        r["matchup"] = None
        position = r.get("position")
        if not position:
            continue
        home = TEAM_ABBR.get(r.get("home_team"))
        away = TEAM_ABBR.get(r.get("away_team"))
        team = r.get("team")
        opponent = away if team == home else (home if team == away else None)
        if opponent:
            r["matchup"] = tiers.get((opponent, position))


SPORT = SportConfig(
    key="nba",
    display_name="NBA",
    odds_sport_key="basketball_nba",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
    team_abbr=TEAM_ABBR,
)
