"""Settings shared across every sport: paths, Odds API access, and scoring defaults.

Sport-specific stuff (stats source, market -> stat-column mapping, market labels)
lives in src/sports/<sport>.py instead - see src/sports/base.py for the shape.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROPS_SAMPLE_JSON = DATA_DIR / "props_sample.json"
REPORT_HTML = ROOT / "report.html"
TEMPLATE_HTML = Path(__file__).resolve().parent / "template.html"

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
REGIONS = "us"
ODDS_FORMAT = "american"

DEFAULT_LOOKBACK = 10
DEFAULT_MIN_GAMES = 5


def stats_cache_path(sport_key: str, suffix: str = "csv") -> Path:
    return DATA_DIR / f"{sport_key}_stats.{suffix}"


def props_json_path(sport_key: str) -> Path:
    return DATA_DIR / f"{sport_key}_props.json"
