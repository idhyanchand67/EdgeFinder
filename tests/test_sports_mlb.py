import pandas as pd

from src.sports import mlb


def test_outs_from_innings_whole_number():
    assert mlb._outs_from_innings("5.0") == 15


def test_outs_from_innings_one_third():
    assert mlb._outs_from_innings("5.1") == 16


def test_outs_from_innings_two_thirds():
    assert mlb._outs_from_innings("5.2") == 17


def test_outs_from_innings_zero():
    assert mlb._outs_from_innings("0.0") == 0


def test_outs_from_innings_handles_bad_input():
    assert mlb._outs_from_innings("") == 0
    assert mlb._outs_from_innings(None) == 0


def _matchup_stats_df():
    rows = []
    for g in range(4):
        event = f"game{g}"
        # ACE team: stingy pitching (low ERA) - tough for opposing batters.
        rows.append({"team": "ACE", "event_id": event, "p_outs": 27, "p_er": 1, "bat_runs": 2})
        # SOFT team: bad pitching (high ERA) - favorable for opposing batters.
        rows.append({"team": "SOFT", "event_id": event, "p_outs": 27, "p_er": 8, "bat_runs": 2})
        # MID team: in between.
        rows.append({"team": "MID", "event_id": event, "p_outs": 27, "p_er": 4, "bat_runs": 2})
        # BASH team: strong offense (high runs/game) - tough for opposing pitchers.
        rows.append({"team": "BASH", "event_id": event + "b", "p_outs": 0, "p_er": 0, "bat_runs": 9})
        rows.append({"team": "PUNCH", "event_id": event + "b", "p_outs": 0, "p_er": 0, "bat_runs": 1})
        rows.append({"team": "AVGOFF", "event_id": event + "b", "p_outs": 0, "p_er": 0, "bat_runs": 4})
    return pd.DataFrame(rows)


def test_batter_role_direction_low_era_is_tough():
    """Batters facing a stingy (low-ERA) pitching staff should see Tough,
    not Favorable - the direction that actually matters for the pick."""
    tiers = mlb.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("ACE", "batter")] == "Tough"
    assert tiers[("SOFT", "batter")] == "Favorable"


def test_pitcher_role_direction_high_scoring_offense_is_tough():
    """Pitchers facing a high-scoring lineup should see Tough, not Favorable."""
    tiers = mlb.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("BASH", "pitcher")] == "Tough"
    assert tiers[("PUNCH", "pitcher")] == "Favorable"


def test_role_for_market_splits_batter_and_pitcher():
    assert mlb._role_for_market("batter_hits") == "batter"
    assert mlb._role_for_market("pitcher_strikeouts") == "pitcher"
    assert mlb._role_for_market("something_else") is None
