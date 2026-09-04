from src.current_roster import apply_current_teams


def test_apply_current_teams_corrects_a_traded_player():
    results = [{"player": "Jauan Jennings", "team": "SF"}]
    roster_map = {"jauan jennings": "MIN"}
    apply_current_teams(results, roster_map)
    assert results[0]["team"] == "MIN"


def test_apply_current_teams_leaves_unknown_players_alone():
    results = [{"player": "Nobody Traded", "team": "SF"}]
    roster_map = {"jauan jennings": "MIN"}
    apply_current_teams(results, roster_map)
    assert results[0]["team"] == "SF"


def test_apply_current_teams_is_a_noop_when_team_already_matches():
    results = [{"player": "Jauan Jennings", "team": "MIN"}]
    roster_map = {"jauan jennings": "MIN"}
    apply_current_teams(results, roster_map)
    assert results[0]["team"] == "MIN"
