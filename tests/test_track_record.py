from datetime import datetime, timedelta, timezone

import pandas as pd

from src import track_record
from src.sports.base import SportConfig


def _result(**overrides):
    base = {
        "sport": "test", "sport_label": "Test", "player_id": "p1", "player": "Test Player",
        "team": "AAA", "market": "player_points", "market_label": "Points", "line": 20.5,
        "best_side": "Over", "best_price": -110, "best_hit_rate": 0.8, "edge": 0.3,
        "games_sample": 10, "commence_time": "2026-02-01T00:00:00Z", "injury_status": None,
    }
    base.update(overrides)
    return base


def test_pick_id_excludes_sportsbook():
    """Regression test: a real bug had the same prop logged twice across runs
    because a different book had the best price each time. pick_id must not
    vary with which book currently has the best price."""
    a = track_record._pick_id({"sport": "nfl", "player_id": "p1", "market": "m", "line": 1.5,
                                "commence_time": "t", "sportsbook": "DraftKings"})
    b = track_record._pick_id({"sport": "nfl", "player_id": "p1", "market": "m", "line": 1.5,
                                "commence_time": "t", "sportsbook": "FanDuel"})
    assert a == b


def test_log_new_picks_dedupes_same_prop_across_books_keeping_best_edge():
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    results = [
        _result(edge=0.10),  # worse price, same underlying prop
        _result(edge=0.30, best_price=120),  # better price - should win
    ]
    log_df = track_record.log_new_picks(empty_log, results, now=datetime.now(timezone.utc))
    assert len(log_df) == 1
    assert log_df.iloc[0]["edge_at_pick"] == 0.30


def test_log_new_picks_respects_top_n():
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    results = [_result(player_id=f"p{i}", edge=i / 100) for i in range(15)]
    log_df = track_record.log_new_picks(empty_log, results, now=datetime.now(timezone.utc))
    assert len(log_df) == track_record.TOP_N


def test_log_new_picks_never_relogs_the_same_pick():
    now = datetime.now(timezone.utc)
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    first_run = track_record.log_new_picks(empty_log, [_result(edge=0.3)], now=now)
    assert len(first_run) == 1

    # Same prop appears again in a later run, even with a different (higher) edge -
    # should NOT be logged again or updated.
    second_run = track_record.log_new_picks(first_run, [_result(edge=0.9)], now=now)
    assert len(second_run) == 1
    assert second_run.iloc[0]["edge_at_pick"] == 0.3


def test_log_new_picks_excludes_out_players():
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    log_df = track_record.log_new_picks(empty_log, [_result(injury_status="OUT")], now=datetime.now(timezone.utc))
    assert len(log_df) == 0


def test_log_new_picks_excludes_null_edge():
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    log_df = track_record.log_new_picks(empty_log, [_result(edge=None)], now=datetime.now(timezone.utc))
    assert len(log_df) == 0


def _sport_with_matcher():
    def match_game(player_games, commence_time):
        return player_games.iloc[0] if len(player_games) else None

    return SportConfig(
        key="test", display_name="Test", odds_sport_key="test_key",
        market_map={"player_points": ["pts"]}, market_labels={"player_points": "Points"},
        order_by=["game_date"], fetch_stats=lambda force=False: pd.DataFrame(),
        match_game=match_game,
    )


def _pending_log_row(**overrides):
    row = {col: None for col in track_record.LOG_COLUMNS}
    row.update({
        "pick_id": "test-pick", "sport": "test", "player_id": "p1", "market": "player_points",
        "line": 20.5, "side": "Over", "commence_time": "2026-02-01T00:00:00Z", "status": "pending",
    })
    row.update(overrides)
    return row


def test_grade_pending_marks_hit_when_actual_beats_the_line_on_over():
    log_df = pd.DataFrame([_pending_log_row(side="Over", line=20.5)])
    stats_df = pd.DataFrame([{"player_id": "p1", "pts": 25.0}])
    now = datetime.fromisoformat("2026-02-01T12:00:00+00:00")  # well past the 6h buffer
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["result"] == "HIT"
    assert graded.iloc[0]["status"] == "graded"


def test_grade_pending_handles_float64_result_column():
    """Regression test for a real production bug: before any pick has ever been
    graded, 'result' and 'graded_at' are None on every row, which a CSV
    round-trip (or an explicit dtype, as forced here) turns into a float64
    NaN column. Writing a string result into that column used to raise
    TypeError under newer pandas instead of silently upcasting to object."""
    log_df = pd.DataFrame([_pending_log_row(side="Over", line=20.5)])
    log_df["result"] = log_df["result"].astype("float64")
    log_df["graded_at"] = log_df["graded_at"].astype("float64")
    stats_df = pd.DataFrame([{"player_id": "p1", "pts": 25.0}])
    now = datetime.fromisoformat("2026-02-01T12:00:00+00:00")
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["result"] == "HIT"
    assert graded.iloc[0]["graded_at"] is not None


def test_grade_pending_marks_miss_when_actual_falls_short_on_over():
    log_df = pd.DataFrame([_pending_log_row(side="Over", line=20.5)])
    stats_df = pd.DataFrame([{"player_id": "p1", "pts": 10.0}])
    now = datetime.fromisoformat("2026-02-01T12:00:00+00:00")
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["result"] == "MISS"


def test_grade_pending_marks_push_on_exact_tie():
    log_df = pd.DataFrame([_pending_log_row(side="Over", line=20.0)])
    stats_df = pd.DataFrame([{"player_id": "p1", "pts": 20.0}])
    now = datetime.fromisoformat("2026-02-01T12:00:00+00:00")
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["result"] == "PUSH"


def test_grade_pending_matches_player_id_across_int_and_str_types():
    """Regression test for a real production bug: stats_df's player_id can be
    numpy int64 (a pure-digit id read back from the CSV cache infers numeric
    dtype) while the log's is always str (CSV round-tripping any non-numeric
    id, like NFL's, forces the whole column to object/str) - comparing them
    directly matched nothing, so every MLB/NBA/NHL pick stayed "pending"
    forever even days after its game ended."""
    log_df = pd.DataFrame([_pending_log_row(player_id="12345", side="Over", line=20.5)])
    stats_df = pd.DataFrame([{"player_id": 12345, "pts": 25.0}])  # int, not str
    now = datetime.fromisoformat("2026-02-01T12:00:00+00:00")
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["result"] == "HIT"
    assert graded.iloc[0]["status"] == "graded"


def test_grade_pending_respects_the_grade_buffer():
    """A game that just finished (or hasn't finished yet) shouldn't be graded -
    stays pending until enough time has passed."""
    log_df = pd.DataFrame([_pending_log_row(side="Over", line=20.5, commence_time="2026-02-01T00:00:00Z")])
    stats_df = pd.DataFrame([{"player_id": "p1", "pts": 25.0}])
    now = datetime.fromisoformat("2026-02-01T01:00:00+00:00")  # only 1h after commence, buffer is 6h
    graded = track_record.grade_pending(log_df, _sport_with_matcher(), stats_df, now=now)
    assert graded.iloc[0]["status"] == "pending"


def test_summary_excludes_pushes_from_hit_rate():
    log_df = pd.DataFrame([
        _pending_log_row(status="graded", result="HIT", edge_at_pick=0.3),
        _pending_log_row(status="graded", result="MISS", edge_at_pick=0.2),
        _pending_log_row(status="graded", result="PUSH", edge_at_pick=0.1),
        _pending_log_row(status="pending"),
    ])
    s = track_record.summary(log_df)
    assert s["graded"] == 2  # PUSH excluded from the decisive count
    assert s["hit_rate"] == 0.5
    assert s["pending"] == 1
    # Wilson 95% CI for 1/2 is wide and symmetric around 0.5 - just check it
    # brackets the point estimate rather than pinning exact floats.
    assert s["hit_rate_low"] < 0.5 < s["hit_rate_high"]


def test_summary_hit_rate_has_no_interval_when_nothing_graded():
    log_df = pd.DataFrame([_pending_log_row(status="pending")])
    s = track_record.summary(log_df)
    assert s["hit_rate"] is None
    assert s["hit_rate_low"] is None
    assert s["hit_rate_high"] is None


def test_wilson_interval_matches_known_value():
    # Cross-checked against AI_NOTES.md's own worked example: 23/37 -> 46.1%-75.9%.
    low, high = track_record.wilson_interval(23, 37)
    assert round(low * 100, 1) == 46.1
    assert round(high * 100, 1) == 75.9


def test_find_stale_pending_flags_a_pick_whose_game_ended_over_a_day_ago():
    """A pick still pending long after its game (plus the 6h grade buffer)
    ended almost always means the stats pipeline silently broke for it, not
    that grading is just running slow - this is the general-purpose canary
    for exactly the kind of bug that left real picks stuck for days without
    anyone noticing until a user pointed it out."""
    log_df = pd.DataFrame([_pending_log_row(commence_time="2026-02-01T00:00:00Z")])
    # commence + 6h buffer = 06:00; 30h after that is stale, well past STALE_THRESHOLD (24h)
    now = datetime.fromisoformat("2026-02-02T12:00:00+00:00")
    stale = track_record.find_stale_pending(log_df, now=now)
    assert len(stale) == 1


def test_find_stale_pending_ignores_a_pick_still_within_the_threshold():
    log_df = pd.DataFrame([_pending_log_row(commence_time="2026-02-01T00:00:00Z")])
    now = datetime.fromisoformat("2026-02-01T10:00:00+00:00")  # only 4h past the 6h buffer
    stale = track_record.find_stale_pending(log_df, now=now)
    assert len(stale) == 0


def test_find_stale_pending_ignores_already_graded_picks():
    log_df = pd.DataFrame([_pending_log_row(status="graded", commence_time="2026-01-01T00:00:00Z")])
    now = datetime.fromisoformat("2026-02-02T12:00:00+00:00")
    stale = track_record.find_stale_pending(log_df, now=now)
    assert len(stale) == 0


def test_find_stale_pending_handles_empty_log():
    empty_log = pd.DataFrame(columns=track_record.LOG_COLUMNS)
    assert len(track_record.find_stale_pending(empty_log, now=datetime.now(timezone.utc))) == 0
