from datetime import date

import pandas as pd

from src.sports import nfl


class _FakeResponse:
    def __init__(self, status_code, body=b""):
        self.status_code = status_code
        self.content = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _season_csv_bytes(season):
    df = pd.DataFrame([{"season": season, "week": 1, "season_type": "REG", "team": "AAA",
                         "opponent_team": "BBB", "position": "WR", "player_id": "p1",
                         "player_display_name": "Test Player", "passing_yards": 0}])
    return df.to_csv(index=False).encode()


def test_download_probes_backward_when_current_season_not_yet_published(tmp_path, monkeypatch):
    """Regression test for a real bug: nflverse's old combined player_stats.csv
    release silently stopped updating after the 2024 season, so lookback data
    was a full season stale (missing 2025) without a single request failing -
    _download now pulls one file per season and needs to tolerate the current
    year's file not existing yet (it doesn't exist until that season's games
    start) rather than treating that as a fatal error."""
    monkeypatch.setattr(nfl, "date", type("D", (date,), {"today": classmethod(lambda cls: date(2026, 9, 8))}))

    def fake_get(url, timeout=60):
        if "2026" in url:
            return _FakeResponse(404)
        for season in (2025, 2024, 2023):
            if str(season) in url:
                return _FakeResponse(200, _season_csv_bytes(season))
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(nfl.requests, "get", fake_get)
    cache_path = tmp_path / "nfl_stats.csv"
    nfl._download(cache_path)

    result = pd.read_csv(cache_path)
    assert sorted(result["season"].unique()) == [2023, 2024, 2025]


def test_fetch_stats_drops_bye_week_placeholder_rows(tmp_path, monkeypatch):
    """Regression test for a real crash: this source gives a bye-week team one
    all-null placeholder row per week (no player_id, no player_display_name,
    every stat 0) instead of just omitting that team - normalize_name() blew
    up calling .lower() on that NaN display name the moment this data reached
    build_name_index. These aren't real player-games and must be dropped
    before anything downstream sees them."""
    cache_path = tmp_path / "nfl_stats.csv"
    monkeypatch.setattr(nfl.config, "stats_cache_path", lambda sport_key, suffix="csv": cache_path)
    pd.DataFrame([
        {"player_id": "p1", "player_display_name": "Real Player", "position": "WR", "team": "AAA",
         "season": 2025, "week": 1, "season_type": "REG"},
        {"player_id": None, "player_display_name": None, "position": None, "team": "BBB",
         "season": 2025, "week": 1, "season_type": "REG"},
    ]).to_csv(cache_path, index=False)

    df = nfl.fetch_stats()
    assert len(df) == 1
    assert df.iloc[0]["player_id"] == "p1"


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
