"""CLI entrypoint: fetch data, score prop hit rates, render report.html.

Usage:
    python main.py                     # all sports, live odds (needs ODDS_API_KEY in .env)
    python main.py --sport nfl         # just one sport
    python main.py --demo              # bundled sample props, no API key needed
    python main.py --refresh-stats     # force re-download/re-backfill of stats
    python main.py --lookback 5 --min-games 3
"""
import argparse
import json
from datetime import datetime, timezone

from src import build_report, config, current_roster, fetch_odds, hit_rates, injuries, track_record
from src.name_match import normalize_name
from src.sports import SPORTS
from src.sports import nfl as nfl_sport


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", choices=[*SPORTS.keys(), "all"], default="all", help="Which sport(s) to score")
    parser.add_argument("--refresh-stats", action="store_true", help="Force re-download/re-backfill of stats")
    parser.add_argument("--demo", action="store_true", help="Use bundled sample props instead of calling the Odds API")
    parser.add_argument("--lookback", type=int, default=config.DEFAULT_LOOKBACK, help="Trailing games to score against")
    parser.add_argument("--min-games", type=int, default=config.DEFAULT_MIN_GAMES, help="Minimum games sample to include a prop")
    args = parser.parse_args()

    sport_keys = list(SPORTS.keys()) if args.sport == "all" else [args.sport]

    demo_props_by_sport = {}
    if args.demo:
        demo_props_by_sport = json.loads(config.PROPS_SAMPLE_JSON.read_text())

    log_df = track_record.load_log()

    all_results = []
    sports_included = []
    for sport_key in sport_keys:
        sport = SPORTS[sport_key]
        print(f"\n=== {sport.display_name} ===")

        stats_df = sport.fetch_stats(force=args.refresh_stats)
        if len(stats_df) == 0:
            print(f"  no game data available for {sport.display_name} right now (off-season?) - skipping")
            continue
        print(f"  {len(stats_df)} player-game rows loaded")

        if args.demo:
            props = demo_props_by_sport.get(sport_key, [])
            if not props:
                print(f"  no sample props for {sport.display_name} in {config.PROPS_SAMPLE_JSON.name} - skipping")
                continue
            before = len(props)
            props = [p for p in props if sport.game_filter(p)]
            if len(props) < before:
                print(f"  skipping {before - len(props)} sample prop(s) that fail this sport's game filter")
            print(f"  using {len(props)} sample props (--demo mode)")
        else:
            props = fetch_odds.fetch_and_save(sport_key, sport.odds_sport_key, sport.market_map, game_filter=sport.game_filter)

        results = hit_rates.compute_hit_rates(sport, stats_df, props, lookback=args.lookback, min_games=args.min_games)

        if sport_key == "nfl":
            # Correct stale stats-derived teams (nflverse only updates once a
            # traded player has actually played a game for their new team)
            # against ESPN's live rosters *before* checking for a valid game -
            # otherwise a real trade looks identical to bad odds-feed data.
            roster_map = current_roster.fetch_current_teams()
            current_roster.apply_current_teams(results, roster_map)
            results = nfl_sport.filter_valid_games(results)

        injury_map = injuries.fetch_injury_map(sport_key)
        for r in results:
            r["injury_status"] = injury_map.get(normalize_name(r["player"]))
        if sport_key == "nfl":
            nfl_sport.attach_matchups(results, stats_df)

        print(f"  scored {len(results)} props")
        all_results.extend(results)
        sports_included.append(sport.display_name)

        if not args.demo:
            log_df = track_record.grade_pending(log_df, sport, stats_df)

    all_results.sort(key=lambda r: r["edge"] if r["edge"] is not None else float("-inf"), reverse=True)

    if not args.demo:
        log_df = track_record.log_new_picks(log_df, all_results)
        track_record.save_log(log_df)

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "lookback": args.lookback,
        "min_games": args.min_games,
        "sports": sports_included,
        "track_record": track_record.summary(log_df),
    }
    build_report.render(all_results, meta, log_df)


if __name__ == "__main__":
    main()
