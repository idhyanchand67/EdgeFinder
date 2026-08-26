from . import mlb, nba, nfl, nhl
from .base import SportConfig

SPORTS: dict[str, SportConfig] = {
    nfl.SPORT.key: nfl.SPORT,
    nba.SPORT.key: nba.SPORT,
    mlb.SPORT.key: mlb.SPORT,
    nhl.SPORT.key: nhl.SPORT,
}

__all__ = ["SPORTS", "SportConfig"]
