# NFL Prop Hit Rates

Finds player prop bets where the current sportsbook line would have hit (or
missed) unusually often over that player's recent games, and renders it as a
single sortable/filterable `report.html`.

**Not betting advice.** Hit rate against a line's *history* says nothing about
whether the *current* line already prices that pattern in. Treat this as a
research filter, not a signal to bet blind.

## How it works

1. **Historical stats** come from [nflverse](https://github.com/nflverse/nflverse-data)'s
   free weekly player-stats release (no API key) — passing/rushing/receiving
   yards, TDs, receptions, etc. for every player, every game, last 3 seasons.
2. **Current prop lines** come from [The Odds API](https://the-odds-api.com/)
   (player props require a paid plan there). Each line is matched to that
   player's game log by name.
3. For each prop, the app looks at that player's last *N* games (default 10),
   counts how many times the actual stat beat the current line, and reports
   the hit rate for whichever side (Over/Under) hit more often.
4. Everything renders into `report.html` — open it in a browser, no server
   needed. Filter by position, market, minimum hit rate, and minimum sample
   size; sort by clicking any column.

## Quick start

```bash
pip install -r requirements.txt
python main.py --demo      # bundled sample props, no API key needed
```

Open `report.html`.

## Using live odds

1. Get a key from [the-odds-api.com](https://the-odds-api.com/) (player prop
   markets need a paid plan there).
2. `cp .env.example .env` and fill in `ODDS_API_KEY`.
3. `python main.py`

Each run re-downloads current events and requested prop markets from the Odds
API — that costs API quota per event/market/region, so trim
`DEFAULT_MARKETS` in [src/config.py](src/config.py) to only the props you
care about if you're on a limited plan.

## Options

```
python main.py --lookback 5        # score against last 5 games instead of 10
python main.py --min-games 3       # include players with as few as 3 games
python main.py --refresh-stats     # force re-download of nflverse stats (else cached 12h)
```

## Layout

```
main.py               CLI entrypoint
src/config.py         data sources, market -> stat-column mapping, defaults
src/fetch_stats.py     downloads + caches nflverse weekly player stats
src/fetch_odds.py      pulls current player props from The Odds API
src/name_match.py      normalizes names so book spellings match nflverse's
src/hit_rates.py       core calculation: line vs. last-N-games history
src/build_report.py    injects results into the report template
src/template.html      the report page: table, filters, sort, sparklines
data/props_sample.json demo data for --demo (real players, made-up lines)
data/player_stats.csv  cached nflverse download (gitignored, rebuilt on demand)
```

## Known limitations

- Name matching is exact-normalized (case/punctuation/suffix-insensitive) with
  a team tiebreak for duplicates — an unusual spelling mismatch between a book
  and nflverse will show up as "could not match" in the console output rather
  than a wrong player.
- Odds API's player-prop markets vary by book and week; not every market in
  `MARKET_MAP` will have odds available every week.
- `season_type == "REG"` only — playoff games aren't included in the history.
- Combo props (e.g. rush+rec yards) sum the mapped columns per game; that's
  usually but not always how the book settles them — check a book's own rules
  for edge cases (e.g. OT, stat corrections).
