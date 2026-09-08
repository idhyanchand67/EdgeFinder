# Changelog

All notable changes to this project, newest first. There's no semantic
versioning here - this ships continuously via
[`refresh.yml`](.github/workflows/refresh.yml) rather than in discrete
releases - so entries are grouped by date instead of a version number.
Automated `Update pick log [automated]` commits (the scheduled workflow
committing `data/pick_log.csv` back to the repo) aren't listed individually;
everything below is an actual code or behavior change.

## 2026-09-08

### Added
- Automated data-integrity check: flags any track-record pick still stuck
  "pending" more than 24h after its game ended, as a visible GitHub Actions
  `::warning::` annotation and step-summary block.

### Changed
- Consolidated the report's eight filter fields (search, day, sport,
  position, market, sportsbook, min hit rate, min sample) into a single
  labeled tile instead of a loose row of boxes.

## 2026-09-07

### Fixed
- Two real bugs that left MLB/NBA/NHL track-record picks stuck "pending"
  for over a week: a player-id type mismatch in the grading lookup
  (`int64` vs. `str`), and entire days silently and permanently dropped
  from the stats cache after a transient fetch failure. See
  [Engineering notes](README.md#engineering-notes-real-bugs-found-and-fixed).

## 2026-09-06

### Added
- Matchup badge (Tough/Average/Favorable) now shows on Top 10 pick cards,
  not just the full table.

### Fixed
- A name-collision bug that resolved an ambiguous player name (two active
  MLB players named Jose Fermin) to the wrong player's game.
- A crash grading a sport's first-ever graded pick, caused by a pandas
  dtype issue on a column that had never held a non-null value before.
- Stale "Matchup (NFL only)" documentation, left over from before
  MLB/NBA/NHL matchup tiers existed.

## 2026-09-04

### Added
- 60-test automated suite (`tests/`), running in CI on every push and pull
  request to `main`.

### Fixed
- A latent crash risk in NFL's matchup-tier logic for a sparse-data window
  (no guard against a position being entirely absent), caught while writing
  the tests above.

## 2026-09-03

### Added
- Sportsbook filter on the report.
- MLB matchup difficulty (opponent pitching ERA for batters, opponent
  runs/game for pitchers).
- NBA and NHL matchup difficulty, ready for their seasons to start
  (points-allowed-by-position for NBA; skater points-allowed plus goalie
  opponent shot volume for NHL).
- `player_goalie_saves` back into NHL's market list.

### Fixed
- Top 10 pick cards overlapping at phone-width viewports.
- Cross-run duplicate picks in the tracking log (a different sportsbook
  "winning" best price in a later run was counted as a new pick).

## 2026-09-02

### Added
- Pick-tracking log (`data/pick_log.csv`): logs the top 10 picks by edge
  each run, grades them HIT/MISS/PUSH once games finish - the honest
  forward-test of whether edge predicts anything.
- In-page "How this works" documentation section on the report itself.

### Fixed
- Cross-book duplicate picks (the same prop offered by three sportsbooks
  counting as three separate Top 10 entries).
- Stale team data: corrected by pulling ESPN's live rosters instead of
  only filtering out apparent mismatches, after user-reported offseason
  trades were being misclassified as bad odds-feed data.
- Missing-odds ranking bug: a prop's best side could be chosen by
  historical hit rate alone even with no price posted for it; now ranks
  by edge and only ever picks a side that's actually bettable.

## 2026-08-29

### Added
- Injury status tags and NFL opponent matchup context.
- `scripts/backtest.py`, checking whether trailing hit rate actually
  predicts anything (it does - see the README).

## 2026-08-28

### Added
- NFL preseason filtering and a Top 10 daily picks panel.

### Changed
- Trimmed market coverage and widened the refresh cadence to fit The Odds
  API's credit budget.

## 2026-08-26

### Added
- Initial commit: NFL prop hit-rate finder.
- Expanded to NBA, MLB, and NHL.
- Scheduled GitHub Actions workflow, publishing live results to GitHub
  Pages.
