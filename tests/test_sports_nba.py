import pandas as pd

from src.sports import nba


def test_split_made_parses_made_attempted_string():
    assert nba._split_made("6-16") == 6
    assert nba._split_made("0-0") == 0


def test_split_made_handles_bad_input():
    assert nba._split_made("") == 0
    assert nba._split_made(None) == 0


def _matchup_stats_df():
    rows = []
    for g in range(3):
        rows.append({"opponent_team": "STINGY", "position": "G", "pts": 12.0})
        rows.append({"opponent_team": "AVERAGE", "position": "G", "pts": 20.0})
        rows.append({"opponent_team": "LEAKY", "position": "G", "pts": 32.0})
    return pd.DataFrame(rows)


def test_matchup_direction_low_points_allowed_is_tough():
    tiers = nba.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("STINGY", "G")] == "Tough"
    assert tiers[("LEAKY", "G")] == "Favorable"


def test_matchup_tiers_empty_when_opponent_team_missing():
    df = pd.DataFrame([{"opponent_team": None, "position": "G", "pts": 20.0}])
    assert nba.compute_matchup_tiers(df) == {}
