"""CLI entrypoint: fetch data, score prop hit rates, render report.html.

Usage:
    python main.py                 # live odds (needs ODDS_API_KEY in .env)
    python main.py --demo          # bundled sample props, no API key needed
    python main.py --refresh-stats # force re-download of nflverse stats
    python main.py --lookback 5 --min-games 3
"""
import argparse
import json

from src import build_report, config, fetch_odds, fetch_stats, hit_rates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh-stats", action="store_true", help="Force re-download of nflverse player stats")
    parser.add_argument("--demo", action="store_true", help="Use bundled sample props instead of calling the Odds API")
    parser.add_argument("--lookback", type=int, default=config.DEFAULT_LOOKBACK, help="Trailing games to score against")
    parser.add_argument("--min-games", type=int, default=config.DEFAULT_MIN_GAMES, help="Minimum games sample to include a prop")
    args = parser.parse_args()

    stats_df = fetch_stats.load_or_fetch(force=args.refresh_stats)
    print(f"Loaded {len(stats_df)} player-game rows.")

    if args.demo:
        props = json.loads(config.PROPS_SAMPLE_JSON.read_text())
        print(f"Using {len(props)} sample props from {config.PROPS_SAMPLE_JSON.name} (--demo mode).")
    else:
        props = fetch_odds.fetch_and_save()

    results = hit_rates.compute_hit_rates(stats_df, props, lookback=args.lookback, min_games=args.min_games)
    build_report.render(results, stats_df, args.lookback, args.min_games)


if __name__ == "__main__":
    main()
