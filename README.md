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
   needed. A **Top 10 picks** panel up top surfaces the best-hit-rate props
   for whichever day is selected (defaults to the nearest upcoming slate).
   Below that, the full table filters by day, sport, position, market,
   minimum hit rate, and minimum sample size, and sorts by clicking any
   column.
5. **NFL preseason games are excluded automatically.** Recent-history hit
   rates are built from real regular-season usage, and preseason games don't
   reflect that (backups play starter snaps, game plans are vanilla) - so
   scoring them against that history would be misleading. The cutoff is
   computed each run as the Thursday after Labor Day (NFL's real Week 1
   rule), not hardcoded to one season, and props for excluded games are
   filtered out *before* any Odds API quota is spent on them, not after.
6. **Injury status and NFL matchup context add signal the raw stat line
   ignores.** A `Q`/`OUT` badge next to a player's name comes from ESPN's
   public injuries feed (one call per sport, covers every team) - a hot hit
   rate means less if the player's questionable or already ruled out, so
   `OUT` players are excluded from Top 10 entirely (still shown, tagged, in
   the full table below). For NFL specifically, a **Matchup** column
   (Tough/Average/Favorable) ranks the upcoming opponent's defense against
   that position, computed from the same cached stats - fantasy points/game
   allowed to that position, bucketed into thirds. A 90% hit rate racked up
   against soft defenses reads differently against a tough one.

## Does the core premise actually hold up?

`scripts/backtest.py` checks whether "hit rate over the last N games" predicts
anything, or is just noise:

```bash
python scripts/backtest.py            # NFL + MLB (only sports with enough cached history right now)
```

For each player and stat, it walks their game log and at each point compares
the hit rate over the trailing `--lookback` games against a stand-in line
(the median of everything before that point - real historical odds aren't
available to backtest against, see the caveat below), then checks the hit
rate over the following `--horizon` games against that same line.

**Result on NFL** (16,136 player-games, 3 seasons): a strong, consistently
monotonic relationship - a 70%+ trailing hit rate predicted a **56.7% forward
hit rate** (n=1,289), against a **19.1% baseline** across every player/stat
combination (correlation +0.70). That's not noise. Yardage props specifically
(the most comparable to what books actually offer) showed the same pattern
more moderately, e.g. receiving yards: 56.0% forward vs. 42.6% baseline.

**The important caveat**: this mostly demonstrates that a player's *role* is
sticky game-to-game (someone getting more touches recently tends to keep
getting them) - a real and useful pattern, but not the same claim as "this
beats the current sportsbook line." The stand-in line here is a slow-moving
historical median, not a real market price; an actual book already adjusts
for exactly this kind of role change, often quickly. Testing whether the
signal survives *against real historical odds* would need a historical-odds
data source (a much pricier Odds API tier), which this project doesn't have.
So: recent hit rate is a legitimate signal about who's trending, not
proof of an exploitable mispricing - which is exactly why the report treats
it as a research filter rather than a bet recommendation.

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

`.github/workflows/refresh.yml` runs `main.py` on a schedule (twice a day by
default) and publishes `report.html` to GitHub Pages - a stable URL that
always shows the latest scored props, no local run needed.

### Odds API credits

Each run costs Odds API quota per event x market x region requested - that's
not a rounding error. A single run against the smallest paid plan (20,000
credits/month) with just NFL and MLB active (NBA/NHL were off-season) cost
**166 credits**. At the old default of every 6 hours, that alone projects to
~20,000/month - your entire monthly budget, before NBA/NHL even come back
into season. Two changes brought that down:

- Each sport's `MARKET_MAP` (in `src/sports/<sport>.py`) is trimmed to its
  most commonly-bet props (~50% fewer markets per sport) rather than every
  market the Odds API offers for that sport.
- The default cron is twice a day instead of every 6 hours.

Together that lands around 1,200-1,500 credits/month even with all four
sports live - comfortable headroom instead of running at the ceiling. If you
want deeper market coverage back, add entries back to a sport's `MARKET_MAP`
(and matching `MARKET_LABELS`) and watch the `x-requests-remaining` numbers
in the Actions log for a run or two before committing to it.

One-time setup, both in the repo's GitHub settings:

1. **Add your Odds API key as a secret** so the workflow can use it without it
   ever being committed or visible in logs: on the repo's GitHub page, go to
   **Settings -> Secrets and variables -> Actions -> New repository secret**,
   name it `ODDS_API_KEY`, and paste in the value. (If you have the `gh` CLI
   installed, `gh secret set ODDS_API_KEY --repo idhyanchand67/EdgeFinder` does
   the same thing from your own terminal - it prompts for the value rather
   than taking it as a visible argument.)
2. **Enable Pages**: **Settings -> Pages -> Source -> GitHub Actions**.

After that, either wait for the next scheduled run or trigger one immediately
from the **Actions** tab (`Refresh props and publish` -> **Run workflow**).
The published page's URL shows up under **Settings -> Pages** once the first
run finishes.

The twice-daily cadence is a starting point, not a rule - narrow it in
`refresh.yml` if you want fresher lines and have the credit budget for it (see
above), or widen it further if you don't. The stats caches
(`data/*_stats.csv`) persist between runs via `actions/cache`, so only new
games are fetched each time, not a full re-backfill.

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
scripts/backtest.py         checks whether recent hit rate actually predicts anything (see above)
src/config.py               Odds API access, shared paths, scoring defaults
src/fetch_odds.py           pulls current player props from The Odds API (sport-agnostic)
src/name_match.py           normalizes names so book spellings match the stats source's
src/hit_rates.py            core calculation: line vs. last-N-games history (sport-agnostic)
src/injuries.py             ESPN injuries feed -> OUT/RISK tags, one call per sport
src/build_report.py         injects combined results into the report template
src/template.html           the report page: table, filters, sort, sparklines, injury/matchup tags
src/sports/base.py          SportConfig - the interface every sport module implements
src/sports/nfl.py           nflverse fetch, NFL market map/labels, preseason filter, matchup tiers
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
- **Injury status is matched by name only**, the same normalization as prop
  matching - it isn't sport-ID-linked, so an unusual name mismatch fails
  silently (no badge shown) rather than tagging the wrong player.
- **NFL matchup tiers use fantasy points allowed as the only signal.** It's a
  reasonable single proxy for defense-vs-position strength, not a full
  model - it doesn't account for pace, game script, or a defense that's
  banged up at one specific spot (e.g. a good run defense missing its
  starting corners). Treat "Tough"/"Favorable" as a lean, not a verdict.
- **Matchup context is NFL-only for now.** NBA/MLB/NHL have real
  matchup-relevant signals too (opponent defensive rating, opposing
  starter/park factors, goals-against), but each needs its own model rather
  than reusing NFL's fantasy-points-allowed approach - not built yet.
- Name matching is exact-normalized (case/punctuation/suffix-insensitive) with
  a team tiebreak for duplicates - an unusual spelling mismatch between a book
  and the stats source will show up as "could not match" in the console
  output rather than a wrong player.
- Odds API's player-prop markets vary by book and week; not every market in a
  sport's `MARKET_MAP` will have odds available every week.
- NFL history is `season_type == "REG"` only - playoff games aren't included.
- The NFL preseason cutoff is a calendar heuristic (Thursday after Labor Day),
  not read from the Odds API itself - correct for how the NFL actually
  schedules Week 1, but a rule change on their end would need a matching
  update in `src/sports/nfl.py`'s `_regular_season_start`.
- The **Day** filter and default (nearest upcoming slate) are computed in the
  viewer's own browser timezone, so the "same" report can default to a
  different day for two people looking at it from different timezones near a
  UTC date boundary.
- Combo props (e.g. rush+rec yards, PRA) sum the mapped columns per game;
  that's usually but not always how a book settles them - check a book's own
  rules for edge cases (e.g. OT, stat corrections).
