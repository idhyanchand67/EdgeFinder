"""Matches sportsbook prop lines against recent game logs and scores hit rate."""
from .name_match import build_name_index, resolve_player_id
from .sports.base import SportConfig


def _recent_values(player_games, order_by: list[str], columns: list[str], lookback: int):
    """Most-recent-first list of summed-column values, one per game played."""
    ordered = player_games.sort_values(order_by)
    recent = ordered.tail(lookback).iloc[::-1]
    return [float(recent[columns].iloc[i].sum()) for i in range(len(recent))]


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

    results = []
    unmatched = set()
    for (player_name, market, line, sportsbook), prop in grouped.items():
        if line is None:
            continue
        pid = resolve_player_id(player_name, prop.get("home_team"), name_index, stats_df)
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

        last_row = player_games.sort_values(sport.order_by).iloc[-1]
        results.append({
            "sport": sport.key,
            "sport_label": sport.display_name,
            "player": last_row.get("player_display_name", player_name),
            "team": last_row.get("team"),
            "position": last_row.get("position"),
            "market": market,
            "market_label": sport.market_labels.get(market, market),
            "line": line,
            "sportsbook": sportsbook,
            "price_over": prop.get("price_over"),
            "price_under": prop.get("price_under"),
            "commence_time": prop.get("commence_time"),
            "games_sample": games_sample,
            "hit_rate_over": round(overs / games_sample, 3),
            "hit_rate_under": round(unders / games_sample, 3),
            "pushes": pushes,
            "recent_values": values,
        })

    if unmatched:
        print(f"  [{sport.key}] could not match {len(unmatched)} player name(s) to stats data: "
              f"{sorted(unmatched)[:10]}" + (" ..." if len(unmatched) > 10 else ""))

    results.sort(key=lambda r: max(r["hit_rate_over"], r["hit_rate_under"]), reverse=True)
    return results
