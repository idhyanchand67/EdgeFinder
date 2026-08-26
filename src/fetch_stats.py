"""Downloads nflverse's weekly per-player stats (free, no API key) and caches it locally."""
import sys
import time

import pandas as pd
import requests

from . import config


def download(force: bool = False) -> None:
    if config.STATS_CSV.exists() and not force:
        age_hours = (time.time() - config.STATS_CSV.stat().st_mtime) / 3600
        if age_hours < 12:
            print(f"Using cached {config.STATS_CSV.name} ({age_hours:.1f}h old). Pass --refresh-stats to force.")
            return

    print(f"Downloading nflverse player stats from {config.NFLVERSE_STATS_URL} ...")
    resp = requests.get(config.NFLVERSE_STATS_URL, timeout=120)
    resp.raise_for_status()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.STATS_CSV.write_bytes(resp.content)
    print(f"Saved {len(resp.content) / 1e6:.1f} MB to {config.STATS_CSV}")


def load(seasons_back: int = config.SEASONS_BACK) -> pd.DataFrame:
    if not config.STATS_CSV.exists():
        download()
    df = pd.read_csv(config.STATS_CSV, low_memory=False)
    df = df[df["season_type"] == "REG"]
    current_season = int(df["season"].max())
    df = df[df["season"] >= current_season - seasons_back + 1]
    df = df.sort_values(["season", "week"])
    return df.reset_index(drop=True)


def load_or_fetch(seasons_back: int = config.SEASONS_BACK, force: bool = False) -> pd.DataFrame:
    download(force=force)
    return load(seasons_back=seasons_back)


if __name__ == "__main__":
    force = "--refresh-stats" in sys.argv
    df = load_or_fetch(force=force)
    print(f"{len(df)} player-game rows across seasons {sorted(df['season'].unique())}")
