import pandas as pd

from src.name_match import build_name_index, normalize_name, resolve_player_id


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize_name("Ja'Marr Chase") == "jamarr chase"
    assert normalize_name("A.J. Brown") == "aj brown"


def test_normalize_strips_suffixes():
    assert normalize_name("Michael Pittman Jr.") == "michael pittman"
    assert normalize_name("Odell Beckham III") == "odell beckham"
    assert normalize_name("Kenneth Walker III") == normalize_name("Kenneth Walker")


def test_normalize_collapses_whitespace_and_empty_input():
    assert normalize_name("  Josh   Allen  ") == "josh allen"
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def _stats_df():
    return pd.DataFrame([
        {"player_id": "p1", "player_display_name": "Mike Williams", "team": "LAC"},
        {"player_id": "p2", "player_display_name": "Mike Williams", "team": "NYJ"},
        {"player_id": "p3", "player_display_name": "Ja'Marr Chase", "team": "CIN"},
    ])


def test_resolve_unique_name_matches_regardless_of_team():
    df = _stats_df()
    index = build_name_index(df)
    assert resolve_player_id("Ja'Marr Chase", "Cincinnati Bengals", index, df) == "p3"


def test_resolve_ambiguous_name_uses_team_tiebreak():
    df = _stats_df()
    index = build_name_index(df)
    assert resolve_player_id("Mike Williams", "NYJ", index, df) == "p2"
    assert resolve_player_id("Mike Williams", "LAC", index, df) == "p1"


def test_resolve_ambiguous_name_falls_back_without_team_match():
    df = _stats_df()
    index = build_name_index(df)
    # Team doesn't match either candidate (e.g. a stale/mismatched team) -
    # still returns *a* candidate rather than giving up.
    assert resolve_player_id("Mike Williams", "Some Other Team", index, df) in ("p1", "p2")


def test_resolve_unknown_name_returns_none():
    df = _stats_df()
    index = build_name_index(df)
    assert resolve_player_id("Nobody Here", "CIN", index, df) is None
