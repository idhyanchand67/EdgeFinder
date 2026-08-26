"""Shared constants: where data comes from and how markets map to stat columns."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATS_CSV = DATA_DIR / "player_stats.csv"
PROPS_JSON = DATA_DIR / "props.json"
PROPS_SAMPLE_JSON = DATA_DIR / "props_sample.json"
REPORT_HTML = ROOT / "report.html"
TEMPLATE_HTML = Path(__file__).resolve().parent / "template.html"

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "americanfootball_nfl"
REGIONS = "us"
ODDS_FORMAT = "american"

# nflverse's weekly per-player offensive stats, updated after every game.
NFLVERSE_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv"
)

# How many trailing NFL seasons of game logs to pull for hit-rate history.
SEASONS_BACK = 3

# Odds API player-prop market key -> nflverse stat column(s) to compare the
# line against. A list means the columns are summed per game (combo props).
MARKET_MAP = {
    "player_pass_yds": ["passing_yards"],
    "player_pass_tds": ["passing_tds"],
    "player_pass_completions": ["completions"],
    "player_pass_attempts": ["attempts"],
    "player_pass_interceptions": ["interceptions"],
    "player_rush_yds": ["rushing_yards"],
    "player_rush_attempts": ["carries"],
    "player_rush_tds": ["rushing_tds"],
    "player_reception_yds": ["receiving_yards"],
    "player_receptions": ["receptions"],
    "player_reception_tds": ["receiving_tds"],
    "player_rush_reception_yds": ["rushing_yards", "receiving_yards"],
    "player_pass_rush_reception_yds": ["passing_yards", "rushing_yards", "receiving_yards"],
    "player_rush_reception_tds": ["rushing_tds", "receiving_tds"],
    "player_pass_rush_reception_tds": ["passing_tds", "rushing_tds", "receiving_tds"],
}

# Default set of markets to request from the Odds API (each costs quota per event).
DEFAULT_MARKETS = list(MARKET_MAP.keys())

DEFAULT_LOOKBACK = 10
DEFAULT_MIN_GAMES = 5
