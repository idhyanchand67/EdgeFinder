# Methodology audit: how EdgeFinder calculates edge, and why it overstates it

**Status:** pre-implementation. Nothing in the pipeline has been changed. This
document is the deliverable requested before any code changes - the seven
items under "before coding": current methodology, problems, candidate
approaches, data required, validation strategy, proposed methodology, and
assumptions.

Every claim below is tagged CONFIRMED (verified by reading the code or
computing from repo data), DERIVED (follows algebraically), or UNVERIFIED.

---

## 1. What the application actually does

Traced from raw data to the number on the page. Line references are to the
code as of this audit.

```
nflverse weekly stats / ESPN boxscore JSON
    -> stats_df: one row per player-game
Odds API /events, then /events/{id}/odds per event
    -> props: one row per player x market x side x bookmaker
              (fetch_odds.py:41-64)
              each row carries: line ("point"), price, side, book, commence_time
    v
hit_rates.compute_hit_rates()                      [hit_rates.py:37]
    group Over/Under rows into one record per
      (player, market, line, book)                 [:53]
    resolve player name -> player_id               [name_match.py]
    values = last `lookback` games, most recent
      first, summing the market's stat column(s)   [:6-10]  lookback=10
    drop if games_sample < min_games               [:75]    min_games=5
    overs  = count(value > line)                   [:78]
    unders = count(value < line)                   [:79]
    pushes = games_sample - overs - unders         [:80]
    hit_rate_over  = overs  / games_sample         [:81]   <- denominator
    hit_rate_under = unders / games_sample         [:82]      includes pushes
    best_side = whichever hit rate is higher,
      restricted to sides that have a posted price [:20-34]
    implied = american_to_probability(best_price)  [:13-17]
    EDGE = best_hit_rate - implied                 [:33]
    sort descending by edge                        [:122]
    v
track_record.log_new_picks()                       [track_record.py]
    top 10 by edge, one entry per distinct
      (sport, player, market, line), never re-logged
track_record.grade_pending()
    after commence_time + 6h, actual vs line -> HIT / MISS / PUSH
track_record.summary()
    hit_rate = HIT / (graded, excluding PUSH)      <- different denominator
    v
build_report.render() -> report.html -> GitHub Pages
```

**So the metric is:**

```
Edge = (raw hit rate over last <=10 games, on whichever side looks better)
       - (implied probability of that side, computed from a single book's
          price, with the bookmaker margin left in)
```

CONFIRMED, from the code. Three things this does *not* do, despite appearances:

- **No opponent, injury, home/away, rest, or usage information enters the
  probability.** Matchup rating and injury badges are computed in `main.py`
  and displayed, and `OUT` players are excluded from Top 10, but no context
  variable touches the number itself.
- **No vig removal**, even though both sides' prices are in memory at the
  moment edge is computed (`price_over` and `price_under`, `hit_rates.py:84-85`).
- **No uncertainty of any kind** enters the ranking. A 5-game sample and a
  10-game sample compete on equal terms.

### What is already sound

Stated up front, because not everything here is broken:

- **`scripts/backtest.py` has no look-ahead leakage.** CONFIRMED by reading
  it: `:52` sorts before values are extracted, `:58` the stand-in line is
  `median(values[:i])` (strictly before `i`), `:59` the trailing window is
  `values[i-lookback:i]` (strictly before `i`), `:60` the future window starts
  at `i`. No overlap, no off-by-one. The implementation matches its docstring.
- **The forward test is honest in design.** `log_new_picks` records the first
  call and never updates it, so the track record cannot drift into a
  moving target. That is the right discipline and it is rare.
- **A side with no posted price can no longer win.** `_pick_best_side`
  explicitly prefers a bettable side over a better-looking unbettable one.
- **Grading discipline is good**: a 6-hour buffer, and `find_stale_pending`
  flags picks that should have graded and didn't - which caught two real data
  bugs.

The problems below are about statistics, not about engineering care.

---

## 2. The statistical problems

### P1. The edge formula is guaranteed to overstate, by algebra, not by luck

This is the finding that matters most, and it does not depend on sample size.

For any prop where both sides are quoted:

```
edge_over  = hit_rate_over  - implied_over
edge_under = hit_rate_under - implied_under

edge_over + edge_under = (hit_rate_over + hit_rate_under)
                       - (implied_over  + implied_under)
```

The first bracket is bounded above by 1, since
`(overs + unders) / n = (n - pushes) / n <= 1`.

The second bracket is the bookmaker's overround, which is **greater** than 1
by construction - that is how the book earns. Measured on this repository's
own `data/props_sample.json`, across the 16 two-sided quotes it contains:

```
mean (implied_over + implied_under) = 1.0489     CONFIRMED
mean vig                            = 4.89 percentage points
```

Therefore:

```
edge_over + edge_under <= 1 - 1.0489 = -0.0489      DERIVED
```

**The two sides' edges always sum to a negative number.** Their average is at
most -2.4pp. A prop's "true" average edge under this formula is negative
before any data is looked at.

`_pick_best_side` then takes `max(hit_rate_over, hit_rate_under)`
(`hit_rates.py:28`). Selecting the larger of two estimates whose edges sum to
a fixed negative constant means **every positive edge the app reports is the
upward deviation of a noisy estimate around a negative mean.** With a player
whose true probability exactly matches the no-vig market price - zero real
signal - this metric still reports a positive edge roughly half the time, and
those are precisely the props that reach Top 10.

The app is not measuring mispricing. It is measuring which side of a coin
flip happened to land more often recently, and calling the deviation edge.

### P2. 8 of 10 is not an 80% probability

Wilson 95% intervals, and what each implies against a standard -110 price
(break-even 52.38%):

| Observed | Point | Wilson 95% | Width | Raw edge | Edge on lower bound |
|---|---|---|---|---|---|
| 2/3 | 66.7% | 20.8% – 93.9% | 73.1pp | +14.3pp | **−31.6pp** |
| 8/10 | 80.0% | 49.0% – 94.3% | 45.3pp | +27.6pp | **−3.4pp** |
| 15/20 | 75.0% | 53.1% – 88.8% | 35.7pp | +22.6pp | +0.7pp |
| 40/50 | 80.0% | 67.0% – 88.8% | 21.8pp | +27.6pp | +14.6pp |
| 80/100 | 80.0% | 71.1% – 86.7% | 15.5pp | +27.6pp | +18.7pp |
| 800/1000 | 80.0% | 77.4% – 82.4% | 5.0pp | +27.6pp | +25.0pp |

CONFIRMED by computation. The worked example from the brief - 8/10, raw edge
+27.62pp - **flips sign** under a 95% lower bound. Three observations with an
identical 80% point estimate (8/10, 80/100, 800/1000) carry edges that are
indistinguishable from noise, clearly real, and overwhelmingly real
respectively. The current metric treats all three identically.

The app's actual floor is `min_games = 5` (`config.py:24`), which is worse
than every row in that table except 2/3.

### P3. Two different definitions of "hit rate" in one codebase

`hit_rates.py:81` divides by `games_sample`, which **includes pushes**. A push
is scored as a miss for both sides. `track_record.summary()` divides by graded
picks **excluding** pushes - the betting-correct treatment, since a push
refunds the stake.

CONFIRMED but currently inert: all 95 logged picks have half-point lines, so
zero pushes have occurred. It is a latent defect that activates the moment an
integer line appears (goalie saves, strikeouts), and it means the ranking and
the scorecard do not currently agree on what a hit rate is.

### P4. Top 10 is an extreme order statistic over thousands of candidates

Every run scores every player x market x line x book combination across four
sports and surfaces the ten largest. Even with no signal anywhere, the maximum
of a large sample of noisy estimates is large. Nothing corrects for the number
of comparisons, and the same ten are then logged as the track record - so the
scorecard is built from the most selected-on subset available.

### P5. No regression to the mean, anywhere

A 10-game hit rate is used raw. There is no shrinkage toward the player's own
season baseline, their position, or the league. An 8/10 is treated as
identical evidence whether the player's season-long rate is 45% or 78%.

### P6. Equal weighting inside the window

`_recent_values` takes the last N games with equal weight (`hit_rates.py:6-10`).
Game 10 counts exactly as much as game 1, then game 11 counts zero. That is a
step function, not a recency model, and no alternative has been tested.

### P7. Vig is not removed although both prices are available

`implied_prob` returns the raw vigged probability. Comparing a probability
estimate to a vigged break-even inflates apparent edge by roughly half the
overround (~2.4pp here) on every single prop. The fix requires no new data:
both prices are already in scope at `hit_rates.py:84-85`.

### P8. Context is computed, displayed, and then discarded

Matchup rating (Tough/Average/Favorable) and injury status are attached to
each result in `main.py` but never enter the probability or the ranking. The
app shows the user information it refuses to use itself.

### P9. The backtest cannot validate the thing being claimed

`scripts/backtest.py` is causally clean, but it contains **no prices at all**.
It compares a future hit rate against a median-derived stand-in line. That
tests whether a statistic is predictable. It cannot test whether a price is
wrong, which is the claim the app makes. Separately, its loop strides by 1
(`:57`), so consecutive records share `lookback-1` trailing and `horizon-1`
future games while `summarize()` (`:83`) reports `n` and a Pearson correlation
as if they were independent draws. Effective sample size is a small fraction
of the printed one.

### P10. The live track record is not yet evidence of anything

As of this audit, from `data/pick_log.csv`: CONFIRMED

```
95 logged picks, 40 graded, 55 pending
26 hits / 40 decided = 65.0%
Wilson 95% CI: 49.5% - 77.9%    <- still contains 50%
```

Edge tertiles among graded picks:

| Bucket | n | Hit rate | Mean edge at pick |
|---|---|---|---|
| Top third | 13 | 69.2% | +58.4pp |
| Middle third | 13 | 61.5% | +51.3pp |
| Bottom third | 14 | 64.3% | +47.4pp |

There is a hint of ordering at the top but no reliable gradient, on 13 picks a
bucket. Note also the scale: a mean *claimed* edge of +58pp against an
observed hit rate of 69% is the overstatement in P1 and P2 made visible - if
those edges were real, the top bucket would be hitting near 100%.

### P11. Calibration is never measured

No reliability curve, Brier score, log loss, or calibration error exists
anywhere in the codebase. There is currently no way to answer "when the app
says 70%, how often does it happen?"

### P12. The early pick log is not clean

19 of 95 rows use an older `pick_id` format that included the sportsbook, so a
few early rows are the same underlying bet logged twice. CONFIRMED. The impact
today is immaterial - deduplicating gives 25/39 = 64.1% against the raw
26/40 = 65.0% - and the current `_pick_id` correctly excludes the book. Worth
knowing before anyone treats early rows as independent.

---

## 3. Candidate approaches

| Model | What it estimates | Verdict |
|---|---|---|
| **A. Raw hit rate** | `hits / n` | Keep only as the baseline every other model must beat. |
| **B. Beta-Binomial** | Posterior over `p` | Right idea, insufficient alone. See below on priors. |
| **C. Weighted hit rate** | Decay-weighted `p` | Test as a component; not a standalone answer. |
| **D. Logistic regression** | `P(over)` from features | Viable for NFL. Data-starved elsewhere. |
| **E. Gradient boosting** | `P(over)` | Premature. Revisit when sample supports it. |
| **F. Distributional** | `P(X > line)` from a fitted distribution of the statistic | **Recommended.** |

### On the Beta prior

`Beta(1,1)` should not be used. It is uniform over `[0,1]`, which asserts that
a player is as likely to be a 95% over-hitter as a 50% one - a claim the data
flatly contradicts, since lines are set to make props near coin flips. Its
effect on 8/10 is cosmetic:

| Prior | Posterior mean for 8/10 |
|---|---|
| Beta(1,1) | 0.750 |
| Beta(2,2) | 0.714 |
| Beta(10,10) | 0.600 |
| Beta(25,25) | 0.550 |

The prior's strength *is* the model. It should be estimated, not chosen:
**empirical Bayes**, fitting `Beta(a, b)` to the observed distribution of
hit rates across all players within a sport-market, which will land near 50%
with a strength reflecting how much players genuinely differ. Hierarchical
structure (player within position within league) lets thin samples borrow from
the population - which is exactly what P5 is missing.

### Why F, not B, is the recommended direction

Collapsing to a binary throws away the margin. A player averaging 74.5 yards
against a 74.5 line and one averaging 20.5 against the same line are utterly
different situations; a hit-rate model sees only "under." A distributional
model uses how far from the line each game fell, re-prices any line instantly
without needing a fresh hit-rate sample, and naturally produces the
uncertainty the ranking needs.

Distribution per statistic type, fitted rather than assumed:

- Counting stats with overdispersion (receptions, strikeouts, shots):
  **Negative Binomial**. Poisson only if the variance-to-mean ratio supports it.
- Continuous volume (yards): **Gamma** or log-normal; Student-t if tails demand.
- Bounded/rare counts (touchdowns): Poisson or zero-inflated variants.

The fit must be checked, not assumed - if no standard family fits a market,
that market is better served by B with hierarchical shrinkage.

---

## 4. Data required

### Already available
Player-game statistics; the line; the chosen side's price; both sides' prices
at compute time (in memory only); commence time; opponent, injury, home/away
(derivable, currently display-only).

### Missing, in priority order

1. **Both sides' prices, persisted.** Needed for no-vig. They already exist in
   memory and are simply not written to `pick_log.csv`. Cheapest high-value
   change in this document - it costs no API quota.
2. **Closing line and closing odds.** Without these, closing line value cannot
   be computed, and CLV is the only way to detect real edge without waiting
   for a profitability sample that would take years. Requires a second fetch
   near kickoff; quota cost is UNVERIFIED and must be measured before
   committing.
3. **Consensus across books.** A no-vig consensus is a better estimate of the
   market's true probability than any single book's two-sided quote.
4. **Pre-game context as features**: rest days, home/away, opponent identity,
   team total and spread. Mostly derivable from data already fetched.
5. **Usage/role**: snap share, target share, projected minutes. Not currently
   fetched from any source.

### Volume, honestly

For a logistic model, order 10^3-10^4 labelled player-games per sport-market
before out-of-sample results mean much; for gradient boosting, more. NFL has
three seasons via nflverse and can support this. **NBA, MLB and NHL cache only
a 45-day rolling window** (`espn_common.DAYS_BACK`), which is too shallow for
any model beyond B, and too shallow even for the existing backtest - which
already refuses to run on them for exactly this reason. Any modelling plan
that assumes four sports is assuming data that does not exist.

---

## 5. Validation strategy

- **Chronological only.** Expanding window: train on weeks 1..k, test on week
  k+1, advance, repeat. Random splits are invalid here - they let a model
  learn from a player's future to predict their past.
- **Three-way split**: train / validation / a final test period touched once.
  Model choice, feature choice, lookback choice and the calibration layer are
  all fitted inside train+validation. The test period is opened at the end.
- **Calibration measured with**: reliability diagram in the bins specified
  (50-55, 55-60, ... 80+), Brier score, log loss, expected calibration error.
- **Primary metrics: log loss and calibration error.** ROI is reported but is
  far too noisy at this sample size to select on.
- **Multiple testing**: the candidate grid (lookbacks x models x markets x
  sports) must be pre-registered, results FDR-adjusted, and the locked holdout
  never reused. This matters more here than anywhere else in the plan, because
  P4 shows the app already has a selection problem before any modelling starts.
- **CLV as the forward test.** Once closing lines are captured, "does model
  edge predict favourable line movement" is answerable in weeks rather than
  seasons, and it does not require winning a single bet.

---

## 6. Proposed methodology, staged

Nothing below is built yet; this is the plan being submitted for approval.

**Stage 0 - data, no modelling.** Persist both sides' prices. Add no-vig
market probability. Begin capturing closing lines. Nothing user-visible
changes. This must come first because every later stage needs the data.

**Stage 1 - stop the algebraic overstatement (P1, P3, P7).**
Remove `max(over, under)` selection: compute and report edge for a side chosen
on grounds other than which estimate is larger, or report both sides honestly.
Exclude pushes from the hit-rate denominator so the two definitions agree. Use
the no-vig market probability as the comparison point. **These three changes
alone will substantially reduce the number of props showing positive edge, and
that is the intended outcome.**

**Stage 2 - probability model.** Distributional (F) with hierarchical
shrinkage, per sport-market, NFL first since it is the only sport with the
data depth. Model A stays as the baseline.

**Stage 3 - calibration.** Fit isotonic or Platt on validation folds; verify
the reliability curve; never fit on the test period.

**Stage 4 - the metric.** With `p` the calibrated probability and `q` the
no-vig market probability:

```
Edge          = p - q
Conservative  = p_lower_credible_bound - q
EV per 1 unit = p * profit_per_unit - (1 - p) * 1

  where profit_per_unit = price/100          for American price > 0
                        = 100/|price|        for American price < 0
```

Rank by **EV**, not by probability edge - a 5pp edge at +200 is worth far more
than a 5pp edge at -300, and the current ranking cannot see that difference.
Display the conservative edge alongside, and surface the credible interval so
that "61% [59-63]" and "61% [45-76]" are visibly different opportunities.

The architecture should keep the probability estimator behind one interface so
models A/B/C/D/F can be swapped and compared without touching the report.

---

## 7. Assumptions, and what I did not verify

- The vig figure (4.89pp) comes from the 16 two-sided quotes in
  `data/props_sample.json`. Live market vig on player props is typically
  wider. The direction of P1 is unaffected - any overround above zero produces
  a negative sum - but the magnitude is illustrative, not measured live.
- **I did not run `scripts/backtest.py`.** It needs a populated stats cache
  that is gitignored and not present. Its correctness claims here come from
  reading the code, not executing it.
- Whether the current Odds API tier can return historical or closing odds is
  UNVERIFIED and needs checking before Stage 0 item 2 is scoped.
- All empirical figures rest on 40 graded picks. They are directionally
  useful and statistically weak, and nothing here should be read as a
  measurement of whether the app works. P1 is the exception: it is algebraic
  and holds regardless of sample size.
- I have not assessed whether any of this is profitable after vig and
  realistic execution. Nothing in this document claims a profitable strategy
  exists.

---

## Bottom line

The premise is not disproven. It is unmeasured, and the current metric is
constructed in a way that guarantees it will look better than it is.

P1 is the one to internalise: **with zero real predictive power, this formula
still produces a Top 10 full of large positive edges.** That is why the
displayed +58pp average edge coexists with a 65% hit rate, and why fixing the
metric will make the app report far fewer opportunities. Fewer, honest numbers
is the goal.
