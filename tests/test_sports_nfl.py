from datetime import date

import pandas as pd

from src.sports import nfl


def test_regular_season_start_is_thursday_after_labor_day():
    # 2026: Sept 1 is a Tuesday, so Labor Day (first Monday) is Sept 7,
    # and Week 1 kicks off Thursday Sept 10.
    assert nfl._regular_season_start(2026) == date(2026, 9, 10)


def test_regular_season_start_varies_correctly_by_year():
    # 2025: Sept 1 is a Monday, so Labor Day is Sept 1 itself, Week 1 -> Sept 4.
    assert nfl._regular_season_start(2025) == date(2025, 9, 4)


def test_preseason_games_are_excluded():
    prop = {"commence_time": "2026-08-20T18:00:00Z"}  # before Sept 10
    assert nfl._is_regular_season_game(prop) is False


def test_regular_season_games_are_included():
    prop = {"commence_time": "2026-09-13T17:00:00Z"}  # after Sept 10
    assert nfl._is_regular_season_game(prop) is True


def test_missing_commence_time_is_not_dropped():
    assert nfl._is_regular_season_game({}) is True


def test_week_for_computes_correct_season_and_week():
    # Week 1 2026 starts 2026-09-10; a game exactly 10 days later is week 2.
    season, week = nfl._week_for("2026-09-20T17:00:00Z")
    assert season == 2026
    assert week == 2


def test_week_for_handles_playoff_games_in_the_following_calendar_year():
    # A January game belongs to the September-year before it.
    season, week = nfl._week_for("2027-01-15T20:00:00Z")
    assert season == 2026


def test_filter_valid_games_drops_impossible_team_matches():
    """Regression test for a real production bug: props attached to a game
    neither of the player's possible teams (even after roster correction) is in."""
    results = [
        {"player": "Real Player", "team": "CIN", "home_team": "Cincinnati Bengals", "away_team": "Cleveland Browns"},
        {"player": "Bad Data Player", "team": "SF", "home_team": "Minnesota Vikings", "away_team": "Green Bay Packers"},
    ]
    kept = nfl.filter_valid_games(results)
    assert [r["player"] for r in kept] == ["Real Player"]


def test_filter_valid_games_keeps_both_home_and_away_teams():
    results = [
        {"player": "Home Player", "team": "MIN", "home_team": "Minnesota Vikings", "away_team": "Green Bay Packers"},
        {"player": "Away Player", "team": "GB", "home_team": "Minnesota Vikings", "away_team": "Green Bay Packers"},
    ]
    kept = nfl.filter_valid_games(results)
    assert len(kept) == 2


def _matchup_stats_df():
    # 3 defenses, 3 games each, so tiers can compute (n>=3 needed).
    rows = []
    for g in range(3):
        rows.append({"opponent_team": "STINGY", "position": "WR", "fantasy_points_ppr": 5.0})
        rows.append({"opponent_team": "AVERAGE", "position": "WR", "fantasy_points_ppr": 12.0})
        rows.append({"opponent_team": "LEAKY", "position": "WR", "fantasy_points_ppr": 25.0})
    return pd.DataFrame(rows)


def test_matchup_tiers_direction_stingy_defense_is_tough():
    """A defense allowing the fewest points is a Tough matchup for the offense,
    not a Favorable one - the direction that matters for every sport's matchup logic."""
    tiers = nfl.compute_matchup_tiers(_matchup_stats_df())
    assert tiers[("STINGY", "WR")] == "Tough"
    assert tiers[("LEAKY", "WR")] == "Favorable"
    assert tiers[("AVERAGE", "WR")] == "Average"


def test_attach_matchups_resolves_opponent_from_home_away():
    stats_df = _matchup_stats_df()
    results = [
        {"player": "Test WR", "team": "MIA", "position": "WR",
         "home_team": "Arizona Cardinals", "away_team": "Miami Dolphins"},
    ]
    # Opponent resolution only needs a team abbreviation match, not a real team -
    # patch TEAM_ABBR-relevant lookup by using real Odds API team names.
    nfl.attach_matchups(results, stats_df)
    # No tier exists for ARI in this synthetic data, so matchup should be None,
    # not raise - confirms attach_matchups degrades gracefully for unknown opponents.
    assert results[0]["matchup"] is None
