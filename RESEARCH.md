# RESEARCH.md - what we have and have not established

The findings ledger. **Read the table, then read only the rows you care
about.** This file exists separately from [AI_NOTES.md](AI_NOTES.md) because
that one mixes protocol, engineering state and chronology, and became hard to
read straight through. The split:

- **This file** - what is true about the *methodology*. Hypotheses, verdicts,
  evidence.
- **AI_NOTES.md** - how sessions hand work to each other. Protocol, current
  engineering state, open tasks.

If you are trying to answer "does this app work," you want this file only.

---

## Ledger

Status: **REFUTED** (shown false) · **CONFIRMED** (shown true) · **OPEN** (not
yet testable or not yet tested) · **UNTESTABLE** (blocked on data that does not
exist).

| # | Claim | Status | Evidence | Detail |
|---|---|---|---|---|
| 1 | Edge as currently computed measures mispricing | **REFUTED** | `edge_over + edge_under <= -4.89pp` always; the metric selects the upward deviation of a noisy estimate around a negative mean | [audit P1](docs/methodology-audit.md#p1-the-edge-formula-is-guaranteed-to-overstate-by-algebra-not-by-luck) |
| 2 | A 10-game hit rate is a usable probability | **REFUTED** | 8/10 raw edge +27.6pp becomes −3.4pp on a 95% lower bound | [audit P2](docs/methodology-audit.md#p2-8-of-10-is-not-an-80-probability) |
| 3 | The 65% track record is evidence the method works | **REFUTED** | 26/40, Wilson 95% CI 49.5–77.9%, contains 50% | [audit P10](docs/methodology-audit.md#p10-the-live-track-record-is-not-yet-evidence-of-anything) |
| 4 | Higher edge predicts better outcomes | **OPEN** | Tertiles 69.2 / 61.5 / 64.3% — no reliable gradient, n=13 per bucket | [audit P10](docs/methodology-audit.md#p10-the-live-track-record-is-not-yet-evidence-of-anything) |
| 5 | The backtest validates the edge claim | **REFUTED** | It contains no prices; it tests stat predictability, not market beating | [audit P9](docs/methodology-audit.md#p9-the-backtest-cannot-validate-the-thing-being-claimed) |
| 6 | The backtest leaks future information | **REFUTED** | `backtest.py:52,58-60` — windows are strictly causal, no off-by-one | [audit §1](docs/methodology-audit.md#what-is-already-sound) |
| 7 | Recent form predicts beating a real posted line | **UNTESTABLE** | No historical or closing line data is captured anywhere | [audit §4](docs/methodology-audit.md#4-data-required) |
| 8 | Model probabilities are calibrated | **OPEN** | Nothing in the codebase measures calibration | [audit P11](docs/methodology-audit.md#p11-calibration-is-never-measured) |
| 9 | Context (matchup, injury) improves the estimate | **OPEN** | Computed and displayed, never used in the number | [audit P8](docs/methodology-audit.md#p8-context-is-computed-displayed-and-then-discarded) |

**Where that leaves things:** the premise is not disproven — it is unmeasured,
and the current metric is built so that it will look good whether or not it
works. Rows 1, 2 and 5 are structural and do not depend on sample size. Rows
4, 8 and 9 are genuinely open questions worth money if answered.

---

## What would move a row

The shortest path from OPEN to answered, cheapest first:

1. **Persist both sides' prices** (no API cost — they are already in memory).
   Unblocks no-vig probability, which row 1 requires.
2. **Capture closing lines.** Unblocks row 7 and makes closing line value
   computable — the only way to detect real edge in weeks rather than seasons.
3. **Wait for sample.** Row 4 needs roughly 90+ decided picks before the
   tertile comparison means anything; at 40 it is noise.

---

## Log

Newest first. One entry per research session. Keep entries short — put the
substance in a linked document and the verdict in the ledger.

### 2026-09-11 · Methodology audit

Full pipeline traced from raw data to displayed edge, every statistically
questionable assumption catalogued, candidate replacements compared, and a
staged implementation plan proposed. No code changed.

**Headline finding:** the edge formula overstates by algebra, not by bad luck.
Because a book's two implied probabilities sum to more than 1 while two hit
rates sum to at most 1, the two sides' edges always sum to a negative number —
so picking whichever side looks better guarantees that reported edge is noise
measured upward from a negative mean. With zero predictive power, the app
still produces a Top 10 full of large positive edges.

Full document: **[docs/methodology-audit.md](docs/methodology-audit.md)**

**Awaiting:** owner approval of the staged plan before any implementation.
