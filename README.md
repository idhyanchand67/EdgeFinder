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
   needed. A **Top 10 picks** panel up top surfaces the best props for
   whichever day is selected (defaults to the nearest upcoming slate). Below
   that, the full table filters by day, sport, position, market, minimum hit
   rate, and minimum sample size, and sorts by clicking any column.
5. **Ranked by edge, not raw hit rate.** A prop that's "hit" 100% of its last
   10 games isn't interesting if the book already prices it as a near-certainty
   (e.g. a home-run prop's Under, at -2000) - the price already knows. Edge is
   hit rate minus the win probability the price itself implies, so a coinflip
   prop that's actually hit 80% of the time ranks far above a "sure thing"
   priced accordingly. This also fixed a real bug: the report used to pick
   whichever side (Over/Under) had the better historical hit rate even when
   that side had no posted price at all, showing a misleading "100%, no odds"
   line no one could actually bet - it now only picks a side that's bettable.
6. **NFL preseason games are excluded automatically.** Recent-history hit
   rates are built from real regular-season usage, and preseason games don't
   reflect that (backups play starter snaps, game plans are vanilla) - so
   scoring them against that history would be misleading. The cutoff is
   computed each run as the Thursday after Labor Day (NFL's real Week 1
   rule), not hardcoded to one season, and props for excluded games are
   filtered out *before* any Odds API quota is spent on them, not after.
7. **Injury status and opponent matchup context add signal the raw stat line
   ignores.** A `Q`/`OUT` badge next to a player's name comes from ESPN's
   public injuries feed (one call per sport, covers every team) - a hot hit
   rate means less if the player's questionable or already ruled out, so
   `OUT` players are excluded from Top 10 entirely (still shown, tagged, in
   the full table below).

   A **Matchup** column (Tough/Average/Favorable) shows how tough the
   upcoming opponent actually is, computed from the same cached stats - no
   extra data source, and always following the same rule: "Tough" means
   whatever the opponent has been doing tends to *suppress* this player's own
   number, so it leans toward Under; "Favorable" leans toward Over.
   - **NFL / NBA**: the opponent's defense against that *position*
     (points/game allowed, bucketed into thirds) - defense-vs-position is a
     meaningful unit in both. This needed one addition to make possible:
     `opponent_team` is now tracked per player-game row for every ESPN-sourced
     sport (it wasn't before), resolved for free from the same game data
     already being fetched, no extra API calls.
   - **MLB** doesn't have a defense-vs-position structure - a batter faces one
     pitcher, not a defensive front - so it uses two separate team-level
     signals instead: batter props against the opponent's **pitching** (team
     ERA), pitcher props against the opponent's **batting** (runs/game).
   - **NHL** splits the same way MLB does, for the same reason a goalie isn't
     a "position" the way a forward is: skater props (goals/assists/points/
     shots) use the position-vs-defense model like NFL/NBA (points allowed to
     forwards vs. defensemen); goalie saves (`player_goalie_saves`, added back
     to `MARKET_MAP` for this) use the opponent's own shot-generation rate -
     fewer shots against suppresses a goalie's save count, so a *low*-shot
     opponent is "Tough" there, not a high-shot one.
   - NBA and NHL are off-season - this was verified with synthetic data (see
     `git log`), not real games, since none exist yet to check against. Worth
     a spot check once each season actually starts.
8. **A visible Game column, and current rosters instead of stale ones.** Every
   prop shows which two teams are actually playing (e.g. "Packers @ Vikings").
   That surfaced players showing up under games their (stats-derived) team had
   nothing to do with - a 49er under a Vikings/Packers game, an Arizona
   quarterback under the same one - 14 of 16 NFL games in one snapshot, up to
   45% of one game's props. The real cause: nflverse's "team" is whichever
   team a player's *last logged game* was for, and during the offseason a
   trade doesn't show up there until the player has actually played a game
   for their new team - both of those "wrong team" players had, in fact, just
   been traded. `src/current_roster.py` pulls ESPN's live rosters (one call
   per team, updates on the trade itself, not on the next kickoff) and
   corrects the displayed team before anything else runs - matchup, the Game
   column, and the safety-net check all use the corrected team.
   `src/sports/nfl.py`'s `filter_valid_games` still runs afterward as a
   backstop, but now only for whatever's left after that correction: a
   genuine odds-feed issue, or a player this run's roster fetch missed.

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

### Closing the gap: tracking our own picks forward

The backtest above can only test against a stand-in line (a historical
median), because real historical odds aren't available. `src/track_record.py`
closes that gap the honest way - by using the actual live edge metric against
real future outcomes instead of a proxy:

- Every run, the current top 10 props by edge get logged to
  `data/pick_log.csv` - once, the first time each one appears, never updated
  on a later run. That's what keeps this an honest forward test instead of a
  moving target.
- Once a logged pick's game is over (plus a buffer for stats to catch up),
  the next run looks up what the player actually did in *that specific game*
  and marks it HIT, MISS, or PUSH.
- The report's **Track record** section shows the running results: graded
  count, hit rate excluding pushes, average edge at the time each pick was
  made, and the full list so it's checkable, not just a headline number.

Matching a logged pick to its exact game differs by sport: NBA/MLB/NHL stats
carry a real date, so it's the closest game within 36 hours of the pick's
kickoff time. NFL's data only has season+week, so `src/sports/nfl.py`
converts the pick's kickoff time to a week number using the same rule as the
preseason cutoff, then matches on that.

This needs no historical-odds subscription and starts producing real results
immediately - it just takes time to accumulate, since a pick logged today
can't be graded until its game has actually been played. There's no way to
backfill history that was never logged.

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

The workflow also commits `data/pick_log.csv` back to the repo after every
run (needs `contents: write` in `refresh.yml`'s permissions, already set) -
that's what lets the [pick-tracking log](#closing-the-gap-tracking-our-own-picks-forward)
survive between runs instead of vanishing when the runner shuts down.

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
src/hit_rates.py            core calculation: line vs. last-N-games history, best side, edge (sport-agnostic)
src/injuries.py             ESPN injuries feed -> OUT/RISK tags, one call per sport
src/current_roster.py       ESPN live rosters -> corrects stale (pre-trade) NFL team data
src/track_record.py         logs Top 10 picks, grades them once their games are over
src/build_report.py         injects combined results + pick log into the report template
src/template.html           the report page: table, filters, sort, sparklines, injury/matchup tags, track record
src/sports/base.py          SportConfig - the interface every sport module implements
src/sports/nfl.py           nflverse fetch, NFL market map/labels, preseason filter, matchup tiers, game matching
src/sports/nba.py           ESPN fetch, NBA market map/labels, matchup tiers (points allowed by position)
src/sports/mlb.py           ESPN fetch, MLB market map/labels, matchup tiers (ERA / runs per game)
src/sports/nhl.py           ESPN fetch, NHL market map/labels, matchup tiers (skaters + goalies)
src/sports/espn_common.py   shared scoreboard/boxscore fetch + incremental local cache + opponent_team resolution
data/props_sample.json      demo data for --demo, keyed by sport (real players, made-up lines)
data/<sport>_stats.csv      cached per-sport stats (gitignored, rebuilt/backfilled on demand)
data/pick_log.csv           the pick-tracking log (committed, not gitignored - it's the point)
.github/workflows/refresh.yml  scheduled run -> publishes report.html to GitHub Pages, commits the pick log
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

- **The current-team correction is NFL-only, and depends on ESPN's roster
  endpoint being complete.** One team's roster sub-endpoint has been observed
  returning 404 while every other team (and that same team's non-roster
  endpoints) work fine - `current_roster.py` logs a warning and skips that
  team for the run rather than failing, so its players just fall back to
  their stats-derived team until a later run's fetch succeeds. NBA/MLB/NHL
  don't have this correction yet, so a mid-season trade there would show the
  same kind of staleness NFL had before this fix - lower priority while
  those leagues are still off-season.
- `filter_valid_games` (see item 8) is a backstop, not the primary fix, and
  still can't catch every version of a bad match - a prop attached to the
  *wrong game the player's actual current team is still playing* (e.g. mixed
  up between two games the same team played in the same week) would pass it
  silently, since the team still matches one side of *some* game.
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
- **An earlier version of this doc said NBA's box score data has no
  position field - that was wrong.** `nba.py`'s `_extract` already pulls it
  (`athlete.position.abbreviation`), and a raw ESPN response confirmed it's
  populated (e.g. "Forward"/"F"). Left here as a correction since NBA is
  off-season and there's no real 2026-27 data yet to fully verify it holds
  for every player, not just spot-checked ones.
- **Injury status is matched by name only**, the same normalization as prop
  matching - it isn't sport-ID-linked, so an unusual name mismatch fails
  silently (no badge shown) rather than tagging the wrong player.
- **Matchup tiers use one proxy signal each, not a full model.** NFL/NBA use
  points (or fantasy points) allowed by position; MLB uses team ERA/runs-per-
  game; NHL uses points allowed by skater position and opponent shot volume
  for goalies. None of these account for pace, game script, park factors, or
  a team missing a specific starter (a good pitching staff minus its actual
  probable starter isn't reflected). MLB's signals in particular are
  team-level, not tied to the specific opposing starting pitcher a batter
  will actually face - that would need a probable-starters data source this
  project doesn't have. Treat "Tough"/"Favorable" as a lean, not a verdict.
- **NBA and NHL's matchup tiers are unverified against real games.** Both
  sports are off-season - the logic was validated with fabricated data
  exercising the actual code path (see the commit that added this), not a
  real slate, since none exists yet to check against. Worth a spot check
  once each season starts.
- **NHL now requests `player_goalie_saves`** (added back after being cut
  during the credit-budget pass), a fifth market on top of the four already
  trimmed to. Small in absolute terms while NHL is off-season, but worth
  factoring in once real games (and real quota spend) start in October.
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
