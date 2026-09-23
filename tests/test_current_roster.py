from src.current_roster import apply_current_teams, fetch_current_teams


def _roster_response(names):
    return {"athletes": [{"items": [{"displayName": n} for n in names]}]}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_current_teams_drops_a_name_collision_across_rosters(monkeypatch):
    """Regression test for a real production bug: Jacoby Brissett's team got
    silently set to whichever roster happened to be scanned last, because the
    map was built with no collision check at all. A name on two rosters at
    once must be left out of the map - not resolved by iteration order -
    so apply_current_teams falls back to the player's real stats-derived team
    instead of an arbitrary guess."""
    def fake_get(url, timeout=20):
        if "/ari/roster" in url:
            return _FakeResponse(_roster_response(["Jacoby Brissett"]))
        if "/ne/roster" in url:
            return _FakeResponse(_roster_response(["Jacoby Brissett"]))
        if "/min/roster" in url:
            return _FakeResponse(_roster_response(["Jauan Jennings"]))
        return _FakeResponse(_roster_response([]))

    monkeypatch.setattr("src.current_roster.requests.get", fake_get)
    roster_map = fetch_current_teams()

    assert "jacoby brissett" not in roster_map
    assert roster_map["jauan jennings"] == "MIN"


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
