"""Pulls current player-prop lines for one sport from The Odds API (https://the-odds-api.com/).

Player props are event-scoped in the Odds API's v4 endpoint, so this fetches the
list of upcoming events first, then requests the configured markets for each one.
Each event+market request consumes API quota - keep the markets list trimmed to
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


def fetch_upcoming_events(odds_sport_key: str) -> list[dict]:
    resp = _get(f"/sports/{odds_sport_key}/events")
    return resp.json()


def fetch_props_for_event(odds_sport_key: str, event_id: str, markets: list[str]) -> dict:
    resp = _get(
        f"/sports/{odds_sport_key}/events/{event_id}/odds",
        regions=config.REGIONS,
        markets=",".join(markets),
        oddsFormat=config.ODDS_FORMAT,
    )
    return resp.json()


def _normalize(event: dict, event_odds: dict, market_map: dict) -> list[dict]:
    props = []
    home = event.get("home_team")
    away = event.get("away_team")
    commence_time = event.get("commence_time")
    for bookmaker in event_odds.get("bookmakers", []):
        book = bookmaker.get("title")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in market_map:
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


def fetch_all_props(odds_sport_key: str, market_map: dict, markets: list[str] = None, game_filter=None) -> list[dict]:
    if not config.ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Copy .env.example to .env and fill in a key "
            "from https://the-odds-api.com/, or run with --demo to use sample data."
        )
    markets = markets or list(market_map.keys())
    events = fetch_upcoming_events(odds_sport_key)
    if game_filter is not None:
        kept = [e for e in events if game_filter(e)]
        skipped = len(events) - len(kept)
        if skipped:
            print(f"  skipping {skipped} event(s) that fail this sport's game filter (e.g. NFL preseason) "
                  f"before spending any quota on them")
        events = kept
    print(f"  found {len(events)} upcoming events for {odds_sport_key}")
    all_props = []
    for event in events:
        try:
            event_odds = fetch_props_for_event(odds_sport_key, event["id"], markets)
        except requests.HTTPError as e:
            print(f"  skipped {event.get('away_team')} @ {event.get('home_team')} ({e})", file=sys.stderr)
            continue
        all_props.extend(_normalize(event, event_odds, market_map))
    return all_props


def fetch_and_save(sport_key: str, odds_sport_key: str, market_map: dict, markets: list[str] = None, game_filter=None) -> list[dict]:
    props = fetch_all_props(odds_sport_key, market_map, markets=markets, game_filter=game_filter)
    out_path = config.props_json_path(sport_key)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(props, indent=2))
    print(f"  saved {len(props)} prop lines to {out_path}")
    return props
