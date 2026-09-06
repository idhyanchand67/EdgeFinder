"""Matches sportsbook prop lines against recent game logs and scores hit rate."""
from .name_match import build_name_index, resolve_player_id
from .sports.base import SportConfig


def _recent_values(player_games, order_by: list[str], columns: list[str], lookback: int):
    """Most-recent-first list of summed-column values, one per game played."""
    ordered = player_games.sort_values(order_by)
    recent = ordered.tail(lookback).iloc[::-1]
    return [float(recent[columns].iloc[i].sum()) for i in range(len(recent))]


def implied_prob(price: float | None) -> float | None:
    """American odds -> implied win probability."""
    if price is None:
        return None
    return (-price) / (-price + 100) if price < 0 else 100 / (price + 100)


def _pick_best_side(hit_rate_over, hit_rate_under, price_over, price_under):
    """Prefers whichever side is actually bettable; a side with no posted price
    never wins even if its historical hit rate looks better on paper."""
    over_has_price = price_over is not None
    under_has_price = price_under is not None
    if over_has_price != under_has_price:
        over_better = over_has_price
    else:
        over_better = hit_rate_over >= hit_rate_under

    best_hit_rate = hit_rate_over if over_better else hit_rate_under
    best_price = price_over if over_better else price_under
    implied = implied_prob(best_price)
    edge = None if implied is None else round(best_hit_rate - implied, 4)
    return ("Over" if over_better else "Under"), best_hit_rate, best_price, edge


def compute_hit_rates(
    sport: SportConfig,
    stats_df,
    props: list[dict],
    lookback: int,
    min_games: int,
) -> list[dict]:
    name_index = build_name_index(stats_df)
    games_by_player = {pid: rows for pid, rows in stats_df.groupby("player_id")}

    # Collapse Over/Under rows for the same player+market+line+book into one record.
    grouped: dict[tuple, dict] = {}
    for prop in props:
        market = prop.get("market")
        if market not in sport.market_map:
            continue
        key = (prop.get("player_name"), market, prop.get("line"), prop.get("sportsbook"))
        entry = grouped.setdefault(key, dict(prop))
        entry[f"price_{prop.get('side', '').lower()}"] = prop.get("price")

    team_abbr = sport.team_abbr or {}
    results = []
    unmatched = set()
    for (player_name, market, line, sportsbook), prop in grouped.items():
        if line is None:
            continue
        # A name collision could be either team in this game, so both are
        # eligible for the tiebreak - not just home_team (see name_match.py).
        game_teams = {team_abbr.get(prop.get("home_team")), team_abbr.get(prop.get("away_team"))}
        pid = resolve_player_id(player_name, game_teams, name_index, stats_df)
        if pid is None or pid not in games_by_player:
            unmatched.add(player_name)
            continue

        player_games = games_by_player[pid]
        columns = sport.market_map[market]
        values = _recent_values(player_games, sport.order_by, columns, lookback)
        games_sample = len(values)
        if games_sample < min_games:
            continue

        overs = sum(1 for v in values if v > line)
        unders = sum(1 for v in values if v < line)
        pushes = games_sample - overs - unders
        hit_rate_over = round(overs / games_sample, 3)
        hit_rate_under = round(unders / games_sample, 3)

        price_over = prop.get("price_over")
        price_under = prop.get("price_under")
        best_side, best_hit_rate, best_price, edge = _pick_best_side(
            hit_rate_over, hit_rate_under, price_over, price_under
        )

        last_row = player_games.sort_values(sport.order_by).iloc[-1]
        results.append({
            "sport": sport.key,
            "sport_label": sport.display_name,
            "player_id": pid,
            "player": last_row.get("player_display_name", player_name),
            "team": last_row.get("team"),
            "position": last_row.get("position"),
            "market": market,
            "market_label": sport.market_labels.get(market, market),
            "line": line,
            "sportsbook": sportsbook,
            "price_over": price_over,
            "price_under": price_under,
            "commence_time": prop.get("commence_time"),
            "home_team": prop.get("home_team"),
            "away_team": prop.get("away_team"),
            "games_sample": games_sample,
            "hit_rate_over": hit_rate_over,
            "hit_rate_under": hit_rate_under,
            "pushes": pushes,
            "recent_values": values,
            "best_side": best_side,
            "best_hit_rate": best_hit_rate,
            "best_price": best_price,
            "edge": edge,
        })

    if unmatched:
        print(f"  [{sport.key}] could not match {len(unmatched)} player name(s) to stats data: "
              f"{sorted(unmatched)[:10]}" + (" ..." if len(unmatched) > 10 else ""))

    results.sort(key=lambda r: r["edge"] if r["edge"] is not None else float("-inf"), reverse=True)
    return results
