from datetime import date

import pandas as pd

from src.sports import espn_common


def _header(home_abbr, away_abbr):
    return {
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": home_abbr}},
                    {"homeAway": "away", "team": {"abbreviation": away_abbr}},
                ]
            }
        ]
    }


def test_opponent_abbr_finds_the_other_team():
    header = _header("PHI", "NY")
    assert espn_common.opponent_abbr("PHI", header) == "NY"
    assert espn_common.opponent_abbr("NY", header) == "PHI"


def test_opponent_abbr_returns_first_competitor_when_team_not_found():
    # team_abbr that matches neither competitor - returns the first one rather
    # than crashing, since every competitor is technically "not team_abbr".
    header = _header("PHI", "NY")
    assert espn_common.opponent_abbr("XXX", header) == "PHI"


def test_opponent_abbr_handles_missing_competitions():
    assert espn_common.opponent_abbr("PHI", {}) is None


def test_backfill_rescans_a_trailing_window_to_catch_a_dropped_day(tmp_path, monkeypatch):
    """Regression test for a real production bug: a scoreboard fetch that
    failed for one day used to be gone forever - the next run's start point
    was last_date + 1, always past a day that failed before a later day
    succeeded. Confirmed against real data: entire days (e.g. 2026-08-28,
    2026-09-03) were silently missing from the MLB cache, which left picks
    for those games' players stuck "pending" for days after the game ended.
    backfill() now re-scans a trailing window on every run instead, so a
    transient failure like that self-heals - seen_event_ids keeps it from
    re-adding anything already cached."""
    cache_path = tmp_path / "test_stats.csv"
    monkeypatch.setattr(espn_common.config, "stats_cache_path", lambda sport_key, suffix="csv": cache_path)

    pd.DataFrame([{"player_id": "p1", "game_date": "2026-01-10T00:00Z", "event_id": "E1", "pts": 5}]).to_csv(
        cache_path, index=False
    )

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 1, 12)

    monkeypatch.setattr(espn_common, "date", _FixedDate)
    monkeypatch.setattr(espn_common.time, "sleep", lambda _: None)

    def fake_completed_event_ids(league_path, day):
        if day == date(2026, 1, 7):  # a "dropped day" the old start point would never revisit
            return ["E2"]
        if day == date(2026, 1, 10):
            return ["E1"]
        return []

    def fake_boxscore_rows(league_path, event_id, extract_fn):
        assert event_id == "E2"  # E1 is already cached - must not be re-fetched
        return [{"player_id": "p2", "game_date": "2026-01-07T00:00Z", "event_id": "E2", "pts": 8}]

    monkeypatch.setattr(espn_common, "_completed_event_ids", fake_completed_event_ids)
    monkeypatch.setattr(espn_common, "_boxscore_rows", fake_boxscore_rows)

    combined = espn_common.backfill("test", "test/league", lambda *a: [], days_back=45, force=False)
    assert set(combined["event_id"].astype(str)) == {"E1", "E2"}
