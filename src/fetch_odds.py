"""Pulls current NFL player-prop lines from The Odds API (https://the-odds-api.com/).

Player props are event-scoped in the Odds API's v4 endpoint, so this fetches the
list of upcoming events first, then requests the configured markets for each one.
Each event+market request consumes API quota - keep DEFAULT_MARKETS trimmed to
what you actually want.
"""
import json
import sys

import requests

from . import config


def _get(path: str, **params) -> requests.Response:
    params["apiKey"] = config.ODDS_API_KEY
    resp = requests.get(f"{config.ODDS_API_BASE}{path}", params=params, timeout=30)
    remaining = resp.headers.get("x-requests-remaining")
    if remaining is not None:
        print(f"  (Odds API quota remaining: {remaining})", file=sys.stderr)
    resp.raise_for_status()
    return resp


def fetch_upcoming_events() -> list[dict]:
    resp = _get(f"/sports/{config.SPORT_KEY}/events")
    return resp.json()


def fetch_props_for_event(event_id: str, markets: list[str]) -> dict:
    resp = _get(
        f"/sports/{config.SPORT_KEY}/events/{event_id}/odds",
        regions=config.REGIONS,
        markets=",".join(markets),
        oddsFormat=config.ODDS_FORMAT,
    )
    return resp.json()


def _normalize(event: dict, event_odds: dict) -> list[dict]:
    props = []
    home = event.get("home_team")
    away = event.get("away_team")
    commence_time = event.get("commence_time")
    for bookmaker in event_odds.get("bookmakers", []):
        book = bookmaker.get("title")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in config.MARKET_MAP:
                continue
            for outcome in market.get("outcomes", []):
                props.append({
                    "player_name": outcome.get("description"),
                    "market": market_key,
                    "side": outcome.get("name"),  # "Over" / "Under"
                    "line": outcome.get("point"),
                    "price": outcome.get("price"),
                    "sportsbook": book,
                    "home_team": home,
                    "away_team": away,
                    "commence_time": commence_time,
                })
    return props


def fetch_all_props(markets: list[str] = None) -> list[dict]:
    if not config.ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Copy .env.example to .env and fill in a key "
            "from https://the-odds-api.com/, or run with --demo to use sample data."
        )
    markets = markets or config.DEFAULT_MARKETS
    events = fetch_upcoming_events()
    print(f"Found {len(events)} upcoming events.")
    all_props = []
    for event in events:
        print(f"Fetching props for {event.get('away_team')} @ {event.get('home_team')} ...")
        try:
            event_odds = fetch_props_for_event(event["id"], markets)
        except requests.HTTPError as e:
            print(f"  skipped ({e})", file=sys.stderr)
            continue
        all_props.extend(_normalize(event, event_odds))
    return all_props


def fetch_and_save(markets: list[str] = None) -> list[dict]:
    props = fetch_all_props(markets=markets)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PROPS_JSON.write_text(json.dumps(props, indent=2))
    print(f"Saved {len(props)} prop lines to {config.PROPS_JSON}")
    return props


if __name__ == "__main__":
    fetch_and_save()
