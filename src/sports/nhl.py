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
    "player_goalie_saves": ["saves"],
}

MARKET_LABELS = {
    "player_goals": "Goals", "player_assists": "Assists", "player_points": "Points",
    "player_shots_on_goal": "Shots on Goal", "player_goalie_saves": "Goalie Saves",
}

_GROUP_POSITION = {"forwards": "F", "defenses": "D", "goalies": "G"}


def _extract(team_block: dict, header: dict, game_date: str) -> list[dict]:
    team_abbr = team_block.get("team", {}).get("abbreviation")
    opponent = espn_common.opponent_abbr(team_abbr, header)
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
                "opponent_team": opponent,
                "position": position,
                "game_date": game_date,
                "goals": float(stat.get("goals", 0) or 0),
                "assists": float(stat.get("assists", 0) or 0),
                "shots_on_goal": float(stat.get("shotsTotal", 0) or 0),
                "blocked_shots": float(stat.get("blockedShots", 0) or 0),
                "saves": float(stat.get("saves", 0) or 0),
                "goals_against": float(stat.get("goalsAgainst", 0) or 0),
            })
    return rows


def fetch_stats(force: bool = False) -> pd.DataFrame:
    return espn_common.backfill("nhl", LEAGUE_PATH, _extract, DAYS_BACK, force)


# Odds API spells out full team names; this project's NHL stats already use
# ESPN's own abbreviations (see _extract above), so match on those directly.
TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR", "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL", "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM", "Florida Panthers": "FLA",
    "Los Angeles Kings": "LA", "Minnesota Wild": "MIN", "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH", "New Jersey Devils": "NJ", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJ", "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL", "St Louis Blues": "STL", "Tampa Bay Lightning": "TB",
    "Toronto Maple Leafs": "TOR", "Utah Mammoth": "UTAH", "Arizona Coyotes": "UTAH",
    "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def compute_matchup_tiers(stats_df: pd.DataFrame) -> dict[tuple, str]:
    """(team, position) -> 'Tough' | 'Average' | 'Favorable':
    - F/D (skater props - goals/assists/points/shots/blocks): that opponent's
      points (goals+assists) allowed per game to that position, same shape as
      NFL's fantasy-points-allowed model, using the opponent_team now tracked
      per row.
    - G (goalie saves): that team's own shots-on-goal generated per game
      (self-contained - a goalie's saves track the *opponent's* shot volume,
      so this is looked up by attach_matchups against the goalie's opponent,
      not the goalie's own team)."""
    tiers: dict[tuple, str] = {}

    skater_rows = stats_df[stats_df["position"].isin(["F", "D"])].dropna(subset=["opponent_team"]).copy()
    if len(skater_rows):
        skater_rows["pts"] = skater_rows["goals"] + skater_rows["assists"]
        allowed = skater_rows.groupby(["opponent_team", "position"])["pts"].mean()
        for position in ["F", "D"]:
            if position not in allowed.index.get_level_values("position"):
                continue
            by_team = allowed.xs(position, level="position").sort_values()
            n = len(by_team)
            if n < 3:
                continue
            for rank, (team, _value) in enumerate(by_team.items()):
                tiers[(team, position)] = "Tough" if rank < n / 3 else ("Average" if rank < 2 * n / 3 else "Favorable")

    # Fewer shots against means fewer save opportunities, which suppresses a
    # goalie's save count - so, same "Tough = suppresses this player's own
    # stat" rule as everywhere else, the *lowest*-shot-volume opponents are
    # "Tough" for a goalie's Over, not the highest.
    shots_per_game = stats_df.groupby(["team", "event_id"])["shots_on_goal"].sum().groupby("team").mean()
    n2 = len(shots_per_game)
    if n2 >= 3:
        for rank, (team, _value) in enumerate(shots_per_game.sort_values().items()):
            tiers[(team, "G")] = "Tough" if rank < n2 / 3 else ("Average" if rank < 2 * n2 / 3 else "Favorable")

    return tiers


def attach_matchups(results: list[dict], stats_df: pd.DataFrame) -> None:
    """Mutates each result in place, adding a 'matchup' tier where the opponent is known."""
    tiers = compute_matchup_tiers(stats_df)
    for r in results:
        r["matchup"] = None
        lookup_position = "G" if r.get("market") == "player_goalie_saves" else r.get("position")
        if lookup_position not in ("F", "D", "G"):
            continue
        home = TEAM_ABBR.get(r.get("home_team"))
        away = TEAM_ABBR.get(r.get("away_team"))
        team = r.get("team")
        opponent = away if team == home else (home if team == away else None)
        if opponent:
            r["matchup"] = tiers.get((opponent, lookup_position))


SPORT = SportConfig(
    key="nhl",
    display_name="NHL",
    odds_sport_key="icehockey_nhl",
    market_map=MARKET_MAP,
    market_labels=MARKET_LABELS,
    order_by=["game_date"],
    fetch_stats=fetch_stats,
)
