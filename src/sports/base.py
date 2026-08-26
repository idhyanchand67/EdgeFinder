"""The interface every sport module implements, registered in src/sports/__init__.py."""
from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass
class SportConfig:
    key: str                          # short id: "nfl", "nba", "mlb", "nhl"
    display_name: str                 # "NFL", "NBA", ...
    odds_sport_key: str                # Odds API sport key, e.g. "americanfootball_nfl"
    market_map: dict[str, list[str]]   # odds market key -> stat column(s), summed if >1
    market_labels: dict[str, str]      # market key -> human-readable label
    order_by: list[str]                 # columns to sort ascending so .tail(N) = most recent games
    fetch_stats: Callable[..., pd.DataFrame]  # (force: bool) -> normalized stats DataFrame

    @property
    def default_markets(self) -> list[str]:
        return list(self.market_map.keys())


# Every fetch_stats() must return a DataFrame with at least these columns,
# plus whatever raw stat columns its market_map references:
#   player_id, player_display_name, team, position, <order_by columns...>
REQUIRED_COLUMNS = ["player_id", "player_display_name", "team", "position"]
