import pandas as pd

from src.hit_rates import _pick_best_side, compute_hit_rates, implied_prob
from src.sports.base import SportConfig


def test_implied_prob_negative_odds():
    # -110 is close to a 52.4% implied win probability.
    assert round(implied_prob(-110), 4) == round(110 / 210, 4)


def test_implied_prob_positive_odds():
    # +150 is a 40% implied win probability.
    assert round(implied_prob(150), 4) == 0.4


def test_implied_prob_none_price():
    assert implied_prob(None) is None


def test_pick_best_side_prefers_priced_side_over_unpriced_regardless_of_hit_rate():
    """Regression test: a side with no posted price must never win, even if its
    historical hit rate is better - this was a real production bug (a prop
    showing '100%, no odds' for a side nobody could actually bet)."""
    side, hit_rate, price, edge = _pick_best_side(
        hit_rate_over=0.0, hit_rate_under=1.0, price_over=116, price_under=None,
    )
    assert side == "Over"
    assert price == 116
    assert hit_rate == 0.0


def test_pick_best_side_picks_higher_hit_rate_when_both_priced():
    side, hit_rate, price, edge = _pick_best_side(
        hit_rate_over=0.8, hit_rate_under=0.2, price_over=-110, price_under=-110,
    )
    assert side == "Over"
    assert hit_rate == 0.8


def test_pick_best_side_edge_is_near_zero_for_a_fairly_priced_near_certainty():
    """A prop priced as a near-certainty (e.g. -2000) that hits at the rate its
    own price implies should score close to zero edge, not a misleadingly high one."""
    side, hit_rate, price, edge = _pick_best_side(
        hit_rate_over=0.0, hit_rate_under=1.0, price_over=None, price_under=-2000,
    )
    assert side == "Under"
    assert abs(edge) < 0.05


def _sport(market_map=None, order_by=None):
    return SportConfig(
        key="test", display_name="Test", odds_sport_key="test_key",
        market_map=market_map or {"player_points": ["pts"]},
        market_labels={"player_points": "Points"},
        order_by=order_by or ["game_date"],
        fetch_stats=lambda force=False: pd.DataFrame(),
    )


def _stats_df():
    return pd.DataFrame([
        {"player_id": "p1", "player_display_name": "Test Player", "team": "AAA",
         "position": "G", "game_date": f"2026-01-{d:02d}", "pts": pts}
        for d, pts in enumerate([20, 22, 25, 18, 30, 28, 24, 26, 19, 31], start=1)
    ])


def test_compute_hit_rates_counts_overs_and_unders_correctly():
    stats_df = _stats_df()
    props = [
        {"player_name": "Test Player", "market": "player_points", "line": 23.5, "side": "Over",
         "price": -115, "sportsbook": "TestBook", "home_team": "A", "away_team": "B",
         "commence_time": "2026-02-01T00:00:00Z"},
        {"player_name": "Test Player", "market": "player_points", "line": 23.5, "side": "Under",
         "price": -105, "sportsbook": "TestBook", "home_team": "A", "away_team": "B",
         "commence_time": "2026-02-01T00:00:00Z"},
    ]
    results = compute_hit_rates(_sport(), stats_df, props, lookback=10, min_games=5)
    assert len(results) == 1
    r = results[0]
    assert r["games_sample"] == 10
    # Values over 23.5: 25, 30, 28, 24, 26, 31 = 6 of 10
    assert r["hit_rate_over"] == 0.6
    assert r["hit_rate_under"] == 0.4
    assert r["player_id"] == "p1"


def test_compute_hit_rates_respects_min_games_filter():
    stats_df = _stats_df()
    props = [
        {"player_name": "Test Player", "market": "player_points", "line": 23.5, "side": "Over",
         "price": -115, "sportsbook": "TestBook", "home_team": "A", "away_team": "B",
         "commence_time": "2026-02-01T00:00:00Z"},
    ]
    results = compute_hit_rates(_sport(), stats_df, props, lookback=10, min_games=20)
    assert results == []


def test_compute_hit_rates_skips_unknown_market():
    stats_df = _stats_df()
    props = [
        {"player_name": "Test Player", "market": "not_a_real_market", "line": 1.5, "side": "Over",
         "price": -115, "sportsbook": "TestBook", "home_team": "A", "away_team": "B",
         "commence_time": "2026-02-01T00:00:00Z"},
    ]
    results = compute_hit_rates(_sport(), stats_df, props, lookback=10, min_games=5)
    assert results == []


def test_compute_hit_rates_skips_unmatched_player():
    stats_df = _stats_df()
    props = [
        {"player_name": "Nobody Real", "market": "player_points", "line": 20.5, "side": "Over",
         "price": -110, "sportsbook": "TestBook", "home_team": "A", "away_team": "B",
         "commence_time": "2026-02-01T00:00:00Z"},
    ]
    results = compute_hit_rates(_sport(), stats_df, props, lookback=10, min_games=5)
    assert results == []
