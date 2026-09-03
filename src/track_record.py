"""Logs our own Top-10-by-edge picks each run, then grades them once the game
is over. This is the honest version of "does edge predict anything": the
backtest (scripts/backtest.py) could only test against a self-referential
historical-median stand-in line, because real historical odds aren't
available. This tests the actual live edge metric - using today's real
posted price - against real future outcomes.
"""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import config

LOG_COLUMNS = [
    "pick_id", "logged_at", "sport", "sport_label", "player_id", "player", "team",
    "market", "market_label", "line", "side", "price", "hit_rate_at_pick", "edge_at_pick",
    "games_sample", "commence_time", "status", "actual_value", "result", "graded_at",
]

LOG_PATH = config.DATA_DIR / "pick_log.csv"
TOP_N = 10
GRADE_BUFFER = timedelta(hours=6)  # let the game finish and stats catch up before grading


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=LOG_COLUMNS)
    df = pd.read_csv(LOG_PATH, dtype={"pick_id": str}, keep_default_na=True)
    for col in LOG_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def save_log(df: pd.DataFrame) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(LOG_PATH, index=False, columns=LOG_COLUMNS)


def _pick_id(r: dict) -> str:
    return "|".join(str(r.get(k)) for k in
                     ("sport", "player_id", "market", "line", "sportsbook", "commence_time"))


def log_new_picks(log_df: pd.DataFrame, all_results: list[dict], now: datetime = None) -> pd.DataFrame:
    """Appends the current run's top-N-by-edge picks that aren't already logged.
    Once logged, a pick is never re-logged or updated on a later run - we want
    the record of the first call, not the freshest, so this stays an honest
    forward test rather than a moving target."""
    now = now or datetime.now(timezone.utc)
    seen_ids = set(log_df["pick_id"]) if len(log_df) else set()

    candidates = [
        r for r in all_results
        if r.get("edge") is not None and r.get("injury_status") != "OUT" and r.get("player_id")
    ]
    candidates.sort(key=lambda r: r["edge"], reverse=True)

    new_rows = []
    for r in candidates[:TOP_N]:
        pid = _pick_id(r)
        if pid in seen_ids:
            continue
        new_rows.append({
            "pick_id": pid,
            "logged_at": now.strftime("%Y-%m-%d %H:%M UTC"),
            "sport": r["sport"],
            "sport_label": r["sport_label"],
            "player_id": r["player_id"],
            "player": r["player"],
            "team": r.get("team"),
            "market": r["market"],
            "market_label": r["market_label"],
            "line": r["line"],
            "side": r["best_side"],
            "price": r["best_price"],
            "hit_rate_at_pick": r["best_hit_rate"],
            "edge_at_pick": r["edge"],
            "games_sample": r["games_sample"],
            "commence_time": r.get("commence_time"),
            "status": "pending",
            "actual_value": None,
            "result": None,
            "graded_at": None,
        })
        seen_ids.add(pid)

    if not new_rows:
        return log_df
    print(f"  [track_record] logged {len(new_rows)} new pick(s)")
    return pd.concat([log_df, pd.DataFrame(new_rows)], ignore_index=True)


def _default_match_game(player_games: pd.DataFrame, commence_time: str):
    """For sports whose stats carry a real game_date (NBA/MLB/NHL): the closest
    game to the pick's commence_time, within 36h to allow for timezone slop."""
    if "game_date" not in player_games.columns or not commence_time:
        return None
    target = pd.to_datetime(commence_time, utc=True)
    dates = pd.to_datetime(player_games["game_date"], utc=True, errors="coerce")
    diffs = (dates - target).abs()
    if diffs.isna().all():
        return None
    idx = diffs.idxmin()
    if pd.isna(diffs[idx]) or diffs[idx] > pd.Timedelta(hours=36):
        return None
    return player_games.loc[idx]


def grade_pending(log_df: pd.DataFrame, sport, stats_df: pd.DataFrame, now: datetime = None) -> pd.DataFrame:
    """Grades logged picks for this sport whose games are old enough to have finished."""
    now = now or datetime.now(timezone.utc)
    matcher = sport.match_game or _default_match_game
    games_by_player = {pid: rows for pid, rows in stats_df.groupby("player_id")}

    pending_mask = (log_df["status"] == "pending") & (log_df["sport"] == sport.key)
    graded_count = 0
    for idx in log_df[pending_mask].index:
        row = log_df.loc[idx]
        commence = row["commence_time"]
        if not commence:
            continue
        commence_dt = pd.to_datetime(commence, utc=True)
        if now < commence_dt.to_pydatetime() + GRADE_BUFFER:
            continue  # game hasn't happened (or finished) yet

        player_games = games_by_player.get(row["player_id"])
        if player_games is None:
            continue
        game_row = matcher(player_games, commence)
        if game_row is None:
            continue  # not in the stats cache yet - try again next run

        columns = sport.market_map[row["market"]]
        actual_value = float(sum(game_row[c] for c in columns))
        line = float(row["line"])
        if actual_value == line:
            result = "PUSH"
        elif (actual_value > line) == (row["side"] == "Over"):
            result = "HIT"
        else:
            result = "MISS"

        log_df.loc[idx, "actual_value"] = actual_value
        log_df.loc[idx, "result"] = result
        log_df.loc[idx, "status"] = "graded"
        log_df.loc[idx, "graded_at"] = now.strftime("%Y-%m-%d %H:%M UTC")
        graded_count += 1

    if graded_count:
        print(f"  [track_record] graded {graded_count} pick(s) for {sport.display_name}")
    return log_df


def summary(log_df: pd.DataFrame) -> dict:
    graded = log_df[log_df["status"] == "graded"]
    decisive = graded[graded["result"] != "PUSH"]
    hits = (decisive["result"] == "HIT").sum()
    total = len(decisive)
    return {
        "graded": int(total),
        "pending": int((log_df["status"] == "pending").sum()),
        "hit_rate": round(hits / total, 3) if total else None,
        "avg_edge_at_pick": round(graded["edge_at_pick"].astype(float).mean(), 4) if len(graded) else None,
    }
