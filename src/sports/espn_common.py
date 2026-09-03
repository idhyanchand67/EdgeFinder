"""Shared fetch/cache logic for sports pulled from ESPN's public (unofficial,
undocumented but widely used) scoreboard/boxscore JSON endpoints: NBA, MLB, NHL.

There's no bulk "every player's game log" endpoint here, only per-game boxscores,
so this backfills day by day and caches every game it has already parsed -
a first run scans `days_back` days of history; every run after that only
fetches days newer than what's already cached.
"""
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from .. import config

BASE = "https://site.api.espn.com/apis/site/v2/sports"
REQUEST_DELAY = 0.15  # be polite to an unofficial, unauthenticated endpoint

# One row per (player, game). extract_fn turns one team's boxscore block into rows.
ExtractFn = Callable[[dict, dict, str], list[dict]]


def _get(url: str, **params) -> dict:
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _completed_event_ids(league_path: str, day: date) -> list[str]:
    data = _get(f"{BASE}/{league_path}/scoreboard", dates=day.strftime("%Y%m%d"))
    ids = []
    for ev in data.get("events", []):
        if ev.get("status", {}).get("type", {}).get("completed"):
            ids.append(ev["id"])
    return ids


def opponent_abbr(team_abbr: str, header: dict) -> str | None:
    """The other team in this game's header.competitions[0].competitors - lets a
    sport track who a player's opponent was for each game, for matchup-difficulty
    stats computed later (e.g. "points allowed to this position"), without an
    extra API call: the summary response already lists both teams."""
    for c in (header.get("competitions") or [{}])[0].get("competitors", []):
        other = c.get("team", {}).get("abbreviation")
        if other and other != team_abbr:
            return other
    return None


def _boxscore_rows(league_path: str, event_id: str, extract_fn: ExtractFn) -> list[dict]:
    data = _get(f"{BASE}/{league_path}/summary", event=event_id)
    box = data.get("boxscore", {})
    header = data.get("header", {})
    game_date = data.get("header", {}).get("competitions", [{}])[0].get("date", "")
    rows = []
    for team_block in box.get("players", []):
        for row in extract_fn(team_block, header, game_date):
            row["event_id"] = event_id
            rows.append(row)
    return rows


def backfill(sport_key: str, league_path: str, extract_fn: ExtractFn, days_back: int, force: bool) -> pd.DataFrame:
    cache_path = config.stats_cache_path(sport_key)
    existing = None
    seen_event_ids: set[str] = set()

    if cache_path.exists() and cache_path.stat().st_size > 0 and not force:
        existing = pd.read_csv(cache_path, low_memory=False)
        if existing.empty:
            existing = None

    if existing is not None:
        seen_event_ids = set(existing["event_id"].astype(str))
        last_date = pd.to_datetime(existing["game_date"]).max().date()
        start = last_date + timedelta(days=1)
        print(f"[{sport_key}] {len(existing)} cached rows through {last_date}, fetching new games since then")
    else:
        start = date.today() - timedelta(days=days_back)
        print(f"[{sport_key}] no cache (or --refresh-stats) - backfilling last {days_back} days")

    end = date.today()
    new_rows = []
    d = start
    while d <= end:
        try:
            event_ids = _completed_event_ids(league_path, d)
        except requests.RequestException as e:
            print(f"[{sport_key}] skipped {d} (scoreboard fetch failed: {e})")
            d += timedelta(days=1)
            continue
        for event_id in event_ids:
            if event_id in seen_event_ids:
                continue
            try:
                new_rows.extend(_boxscore_rows(league_path, event_id, extract_fn))
            except requests.RequestException as e:
                print(f"[{sport_key}] skipped event {event_id} (boxscore fetch failed: {e})")
            time.sleep(REQUEST_DELAY)
        d += timedelta(days=1)

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([existing, new_df], ignore_index=True) if existing is not None else new_df
        print(f"[{sport_key}] fetched {len(new_rows)} new player-game rows")
    else:
        combined = existing if existing is not None else pd.DataFrame(new_rows)
        print(f"[{sport_key}] no new completed games since last run")

    if combined.empty:
        return combined

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(cache_path, index=False)
    combined = combined.sort_values("game_date").reset_index(drop=True)
    return combined
