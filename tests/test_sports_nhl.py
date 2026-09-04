import pandas as pd

from src.sports import nhl


def _matchup_stats_df():
    # Each row is a skater's game - "team" is the scoring player's own team,
    # "opponent_team" is the defense their points count against. IRON/LEAKY/MID
    # are the defenses under test, so they belong in opponent_team, not team.
    rows = []
    for g in range(4):
        event = f"game{g}"
        rows.append({"team": "OPP1", "event_id": event, "opponent_team": "IRON", "position": "F",
                      "goals": 0, "assists": 0, "shots_on_goal": 10})
        rows.append({"team": "OPP2", "event_id": event, "opponent_team": "LEAKY", "position": "F",
                      "goals": 2, "assists": 2, "shots_on_goal": 8})
        rows.append({"team": "OPP3", "event_id": event, "opponent_team": "MID", "position": "F",
                      "goals": 1, "assists": 1, "shots_on_goal": 6})
        # shot volume for the goalie signal - HIGHVOL generates lots of shots,
        # LOWVOL generates few, regardless of what happened above.
        rows.append({"team": "HIGHVOL", "event_id": event + "s", "opponent_team": None, "position": "F",
                      "goals": 0, "assists": 0, "shots_on_goal": 40})
        rows.append({"team": "LOWVOL", "event_id": event + "s", "opponent_team": None, "position": "F",
                      "goals": 0, "assists": 0, "shots_on_goal": 5})
        rows.append({"team": "MIDVOL", "event_id": event + "s", "opponent_team": None, "position": "F",
                      "goals": 0, "assists": 0, "shots_on_goal": 20})
    return pd.DataFrame(rows)


def test_skater_matchup_direction_stingy_defense_is_tough():
    tiers = nhl.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("IRON", "F")] == "Tough"
    assert tiers[("LEAKY", "F")] == "Favorable"


def test_goalie_matchup_direction_low_shot_volume_is_tough():
    """Regression test for a real bug: fewer shots against means fewer save
    opportunities, which suppresses a goalie's save count - so a LOW-shot-volume
    opponent should be Tough for a goalie prop, not a high-shot-volume one.
    (The first implementation had this backwards.)"""
    tiers = nhl.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("LOWVOL", "G")] == "Tough"
    assert tiers[("HIGHVOL", "G")] == "Favorable"


def test_attach_matchups_goalie_saves_market_uses_g_position_regardless_of_player_position():
    stats_df = _matchup_stats_df()
    results = [
        {"player": "Test Goalie", "team": "SOME", "position": "G", "market": "player_goalie_saves",
         "home_team": "X", "away_team": "Y"},
    ]
    # Should not raise even with no resolvable opponent (TEAM_ABBR won't match "X"/"Y").
    nhl.attach_matchups(results, stats_df)
    assert results[0]["matchup"] is None
