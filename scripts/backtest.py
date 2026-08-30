"""Does a high recent hit rate actually predict anything, or is it noise?

The app flags a prop when a player has cleared some number in most of their
last N games. This backtest checks whether that's a real signal or just
regression-to-the-mean: does a hot recent stretch relative to a stable
long-run number keep paying off, or does it fade back toward 50/50?

Method (run separately per sport, per stat column):
  For each player, walk through their game log game by game. At each point i
  (with enough history before it and enough games after it):
    - `line`  = median of every game up through i-1 (a stand-in for where a
      book would plausibly set a number, since we don't have historical odds
      to backtest against - see the README's caveat on this).
    - `prior` = hit rate (value > line) over the trailing LOOKBACK games
      (exactly what the app itself would compute as of that point).
    - `future`= hit rate (value > line) over the following HORIZON games -
      the actual, still-unknown-at-the-time outcome.
  Across every player/split, bucket by `prior` and look at the average
  `future` in each bucket. If prior hit rate predicts anything, high-prior
  buckets should show a higher future hit rate than low-prior buckets. If
  it's noise, every bucket reverts toward ~50%.

Usage:
    python scripts/backtest.py                  # NFL + MLB (only sports with data right now)
    python scripts/backtest.py --sport nfl
    python scripts/backtest.py --lookback 5 --horizon 3
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sports import SPORTS  # noqa: E402

BUCKETS = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
FLAG_THRESHOLD = 0.7  # matches the app's default --min-hit-rate-ish filter (report.html defaults to 70%)


def stat_columns_for(sport) -> list[str]:
    cols = set()
    for cols_list in sport.market_map.values():
        cols.update(cols_list)
    return sorted(cols)


def backtest_column(df, order_by, column: str, lookback: int, horizon: int) -> list[tuple[float, float]]:
    records = []
    min_games = lookback + horizon + 10  # leave room for several splits per player
    for _, g in df.groupby("player_id"):
        g = g.sort_values(order_by)
        values = g[column].tolist()
        n = len(values)
        if n < min_games:
            continue
        for i in range(lookback, n - horizon + 1):
            line = statistics.median(values[:i])
            trailing = values[i - lookback:i]
            future = values[i:i + horizon]
            hr_prior = sum(v > line for v in trailing) / lookback
            hr_future = sum(v > line for v in future) / horizon
            records.append((hr_prior, hr_future))
    return records


def summarize(records: list[tuple[float, float]], label: str) -> None:
    if len(records) < 30:
        print(f"  {label}: only {len(records)} sample(s) - not enough to say anything")
        return

    priors = [r[0] for r in records]
    futures = [r[1] for r in records]
    n = len(records)

    mean_p = sum(priors) / n
    mean_f = sum(futures) / n
    var_p = sum((p - mean_p) ** 2 for p in priors) / n
    var_f = sum((f - mean_f) ** 2 for f in futures) / n
    cov = sum((priors[i] - mean_p) * (futures[i] - mean_f) for i in range(n)) / n
    corr = cov / (var_p * var_f) ** 0.5 if var_p > 0 and var_f > 0 else 0.0

    print(f"  {label}  (n={n}, corr={corr:+.3f})")
    for lo, hi in BUCKETS:
        bucket = [f for p, f in records if lo <= p < hi]
        if not bucket:
            continue
        avg = sum(bucket) / len(bucket)
        print(f"    prior {lo:.0%}-{hi:.0%}  ->  future avg {avg:.1%}   (n={len(bucket)})")

    flagged = [f for p, f in records if p >= FLAG_THRESHOLD]
    if flagged:
        print(f"    props the app WOULD flag (prior >= {FLAG_THRESHOLD:.0%}): "
              f"future avg {sum(flagged) / len(flagged):.1%}  (n={len(flagged)})  "
              f"vs. baseline {mean_f:.1%} across everything")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", choices=[*SPORTS.keys(), "all"], default="all")
    parser.add_argument("--lookback", type=int, default=10, help="Trailing games (matches the app's default)")
    parser.add_argument("--horizon", type=int, default=5, help="How many future games to check the prediction against")
    args = parser.parse_args()

    sport_keys = list(SPORTS.keys()) if args.sport == "all" else [args.sport]

    all_records = []
    for sport_key in sport_keys:
        sport = SPORTS[sport_key]
        df = sport.fetch_stats(force=False)
        if len(df) == 0:
            print(f"\n=== {sport.display_name}: no data available, skipping ===")
            continue

        print(f"\n=== {sport.display_name} ({len(df)} player-game rows) ===")
        max_games = df.groupby("player_id").size().max()
        min_games_needed = args.lookback + args.horizon + 10
        if max_games < min_games_needed:
            print(f"  no player has {min_games_needed}+ games in the cached history "
                  f"(longest is {max_games}) - skipping. This sport's live cache only "
                  f"holds a rolling window (see espn_common.DAYS_BACK), too shallow for "
                  f"this backtest until more of the season accumulates.")
            continue

        sport_records = []
        for column in stat_columns_for(sport):
            records = backtest_column(df, sport.order_by, column, args.lookback, args.horizon)
            if records:
                summarize(records, column)
                sport_records.extend(records)
        if sport_records:
            print(f"  --- {sport.display_name} pooled across all stats ---")
            summarize(sport_records, "all stats combined")
            all_records.extend(sport_records)

    if all_records:
        print(f"\n=== Overall, every sport combined ===")
        summarize(all_records, "everything")


if __name__ == "__main__":
    main()
