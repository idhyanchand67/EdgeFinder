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
