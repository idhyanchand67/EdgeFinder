# EdgeFinder

Finds player prop bets where the current sportsbook line would have hit (or
missed) unusually often over that player's recent games, across NFL, NBA,
MLB, and NHL, rendered as a single sortable/filterable `report.html`.

**Not betting advice.** Hit rate against a line's *history* says nothing about
whether the *current* line already prices that pattern in. Treat this as a
research filter, not a signal to bet blind.

## How it works

1. **Historical stats**, one adapter per sport:
   - **NFL**: [nflverse](https://github.com/nflverse/nflverse-data)'s free weekly
     player-stats release (no key), last 3 seasons.
   - **NBA / MLB / NHL**: ESPN's public (unofficial, undocumented) boxscore
     JSON, backfilled game-by-game for the last 45 days and cached locally
     (see [Known limitations](#known-limitations)). `stats.nba.com`'s own API
     blocks a lot of non-browser traffic and `balldontlie.io` now requires a
     signup key, so ESPN was the one free, no-key source that reliably
     answered during testing.
2. **Current prop lines** come from [The Odds API](https://the-odds-api.com/)
   (player props require a paid plan there). Each line is matched to that
   player's game log by name.
3. For each prop, the app looks at that player's last *N* games (default 10)
   and reports the hit rate for whichever side (Over/Under) hit more often.
4. Everything renders into `report.html` - open it in a browser, no server
   needed. Filter by sport, position, market, minimum hit rate, and minimum
   sample size; sort by clicking any column.

## Quick start

```bash
pip install -r requirements.txt
python main.py --demo      # bundled sample props, no API key needed, all sports
```

Open `report.html`. A sport with no games in-season (e.g. NBA/NHL in summer)
is skipped automatically with a console note - that's expected, not a bug.

## Using live odds

1. Get a key from [the-odds-api.com](https://the-odds-api.com/) (player prop
   markets need a paid plan there).
2. `cp .env.example .env` and fill in `ODDS_API_KEY`.
3. `python main.py`

Each run re-downloads current events and requested prop markets from the Odds
API - that costs API quota per event/market/region, so trim a sport's
`MARKET_MAP` in `src/sports/<sport>.py` to only the props you care about if
you're on a limited plan.

## Live, auto-refreshing results

`.github/workflows/refresh.yml` runs `main.py` on a schedule (every 6 hours by
default) and publishes `report.html` to GitHub Pages - a stable URL that
always shows the latest scored props, no local run needed.

One-time setup, both in the repo's GitHub settings:

1. **Add your Odds API key as a secret** so the workflow can use it without it
   ever being committed or visible in logs:
   ```bash
   gh secret set ODDS_API_KEY --repo idhyanchand67/EdgeFinder
   ```
   (run this yourself, in your own terminal - it prompts for the value rather
   than taking it as a visible argument). Or add it via
   **Settings -> Secrets and variables -> Actions -> New repository secret**.
2. **Enable Pages**: **Settings -> Pages -> Source -> GitHub Actions**.

After that, either wait for the next scheduled run or trigger one immediately
from the **Actions** tab (`Refresh props and publish` -> **Run workflow**).
The published page's URL shows up under **Settings -> Pages** once the first
run finishes.

The 6-hour cadence is a starting point, not a rule - each run costs Odds API
quota per event/market/region, so widen the cron in `refresh.yml` if you're on
a limited plan, or narrow it close to game days if you want fresher lines.
The stats caches (`data/*_stats.csv`) persist between runs via
`actions/cache`, so only new games are fetched each time, not a full
re-backfill.

## Options

```
python main.py --sport nba          # just one sport: nfl | nba | mlb | nhl | all (default)
python main.py --lookback 5         # score against last 5 games instead of 10
python main.py --min-games 3        # include players with as few as 3 games
python main.py --refresh-stats      # force re-download/re-backfill of stats
```

## Layout

```
main.py                    CLI entrypoint - loops over selected sports, builds one combined report
src/config.py               Odds API access, shared paths, scoring defaults
src/fetch_odds.py           pulls current player props from The Odds API (sport-agnostic)
src/name_match.py           normalizes names so book spellings match the stats source's
src/hit_rates.py            core calculation: line vs. last-N-games history (sport-agnostic)
src/build_report.py         injects combined results into the report template
src/template.html           the report page: table, filters, sort, sparklines
src/sports/base.py          SportConfig - the interface every sport module implements
src/sports/nfl.py           nflverse fetch + NFL market map/labels
src/sports/nba.py           ESPN fetch + NBA market map/labels
src/sports/mlb.py           ESPN fetch + MLB market map/labels (batting + pitching)
src/sports/nhl.py           ESPN fetch + NHL market map/labels (skaters + goalies)
src/sports/espn_common.py   shared scoreboard/boxscore fetch + incremental local cache
data/props_sample.json      demo data for --demo, keyed by sport (real players, made-up lines)
data/<sport>_stats.csv      cached per-sport stats (gitignored, rebuilt/backfilled on demand)
.github/workflows/refresh.yml  scheduled run -> publishes report.html to GitHub Pages
```

## Adding another sport

Odds API covers many more sports than the four here (NCAAF, NCAAB, soccer,
tennis, golf, esports, ...), but most of them don't have a clean free
per-player game-log source the way these four do - that's the actual limiter,
not the code. To add one that does: create `src/sports/<sport>.py` exporting a
`SPORT = SportConfig(...)` (see `src/sports/base.py`) with a `fetch_stats()`
that returns a DataFrame with at least `player_id`, `player_display_name`,
`team`, `position`, plus your `order_by` column(s) and whatever stat columns
your `market_map` references - then register it in `src/sports/__init__.py`.
Nothing else needs to change.

## Known limitations

- **ESPN's API is unofficial and undocumented.** It's widely used by hobby
  projects and answered reliably in testing, but it could change or start
  blocking scripted access without notice - unlike nflverse (an open dataset)
  or a documented, key-based API.
- **First run per sport is slow.** There's no bulk "every player's game log"
  endpoint on ESPN, only per-game boxscores, so NBA/MLB/NHL backfill by
  scanning the last 45 days of scoreboards and fetching each completed game's
  boxscore individually (a few hundred requests, with a small delay between
  each to be polite). Every run after that only fetches games newer than
  what's already cached in `data/<sport>_stats.csv`, so it's fast.
- **MLB has no total-bases market.** ESPN's compact box score line doesn't
  break out doubles/triples, so total bases isn't computable from this data
  and is left out of `MARKET_MAP`.
- **Two-way MLB players** (pitching and batting in the same game) get two
  separate rows for that game - batting and pitching are tracked as different
  stat columns on different rows, so their combined games-played count can
  look inflated. Rare in practice (mainly Shohei Ohtani).
- **NBA/NHL rows have no position** in ESPN's boxscore payload for skaters, so
  the Position filter is blank for those sports (MLB and NFL do have it).
- Name matching is exact-normalized (case/punctuation/suffix-insensitive) with
  a team tiebreak for duplicates - an unusual spelling mismatch between a book
  and the stats source will show up as "could not match" in the console
  output rather than a wrong player.
- Odds API's player-prop markets vary by book and week; not every market in a
  sport's `MARKET_MAP` will have odds available every week.
- NFL history is `season_type == "REG"` only - playoff games aren't included.
- Combo props (e.g. rush+rec yards, PRA) sum the mapped columns per game;
  that's usually but not always how a book settles them - check a book's own
  rules for edge cases (e.g. OT, stat corrections).
