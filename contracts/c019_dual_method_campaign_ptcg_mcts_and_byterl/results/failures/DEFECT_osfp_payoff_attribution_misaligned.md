# DEFECT — OSFP payoff attribution was misaligned, and two promotion-rule bugs behind it

**Found:** 2026-07-27, during a routine status read of the `scaled` ByteRL run at ~57,000 games.
**Disposition:** run killed at 60,960 games / 30,416 optimizer steps / LP2-of-8; all three defects
fixed; training restarted from fresh random initialization under tag `scaled2`.

## 1. Result-to-opponent identity bug (the corrupting one)

`tools/c019_byterl_train.py` built a per-round `jobs` list in sampling order, split it round-robin
across actors, then recombined actor outputs and paired them back with:

```python
chunks[i % a.actors].append(job)      # round-robin OUT
trajs = [t for r in results for t in r]   # actor-order IN
for (job, opp_rec), tr in zip(jobs, trajs):   # <-- pairs by POSITION
```

`trajs` is concatenated in **actor order**, not job order, so `zip` attributed each game's result
to a **different game's sampled opponent**. Measured directly against the raw game log:

```
opponent_sample rows checked: 60,960   agree: 41,418   MISALIGNED: 19,542   (32.1%)
```

Consequence: `osfp.record_result(opp_rec, tr.result_pm_one)` fired whenever the *sampled* record
said HISTORICAL, but the payoff it added came from whichever game landed at that index — usually
a self-play game with mean payoff ≈ 0. The G table was diluted toward zero:

| learning period | G recorded | true sum from raw games | true mean payoff |
|---|---|---|---|
| LP1 | 17.0 over C=7,985 | 167.0 over 7,985 | +0.0209 |
| LP2 | 117.0 (cumulative) | 386.0 (cumulative) | +0.0273 |

The `C` counts were correct (they count sampled records, which were not permuted) and the
per-game `result_pm_one` in `raw_games/` was correct (it comes from the trajectory itself, not
from the pairing). **Training was unaffected** — the learner consumes trajectories, never the
pairing — but every promotion decision rested on a corrupted payoff table, and
`METHOD_FIDELITY.md` requires actual G/C tables.

**Fix:** pair by `game_id` through a dict, and assert the invariant rather than trusting it —
duplicate ids, missing trajectories, and any sampled-vs-played opponent-kind disagreement now
raise instead of being absorbed.

## 2. ξ compared against a mean payoff instead of a win rate

`promotion_decision()` computed `winrates = G[i] / C[i]` — a mean payoff on `[-1, 1]` — and
compared it against `xi = 0.55`, a win rate on `[0, 1]`. `sample_probabilities()` in the same
module already used the correct conversion `((G/C) + 1) / 2`, so the two halves of OSFP
disagreed with each other.

The practical effect: a 0.55 *mean payoff* is a **77.5% win rate**, so performance promotion was
set roughly 22 points above the registered threshold and was effectively unreachable.

**Fix:** convert to a win rate before comparing, and report both `winrates` and `mean_payoffs`
so the units are visible in the evidence rather than inferred.

This did not change any decision the killed run actually made — corrected win rates were 0.5105
(LP1) and 0.5136 (LP2), still below ξ — but it would have suppressed a genuine promotion later.

## 3. Forced-add off-by-one

`if lps_without_add > max_lp` allowed **seven** learning periods without an addition when the
registered `c = 6` permits at most six. Combined with the run's configuration (`--learning-periods
8`, counter reaching 6 at LP7), the forced addition **would never have fired**: the campaign would
have finished with one historical checkpoint and missed the two-addition floor outright.

**Fix:** `>=`, so the counter reaching `max_lp` forces the addition on the next period.

## Why the tests did not catch 2 or 3

`tests/test_c019_fixtures.py::TestOSFPPromotion` used `G=[8.0, 9.0], C=[10, 10]` — a mean payoff
of 0.8, where both the correct and the buggy convention agree — and `lps_without_add=7`, where
both `>` and `>=` agree. Extreme fixtures pass under either reading of a threshold.

Four discriminating tests added, each of which fails against the pre-fix code:

- `test_xi_is_compared_against_a_win_rate_not_a_mean_payoff` — 60% win rate = 0.20 mean payoff
- `test_a_losing_record_never_promotes_even_at_the_boundary` — exactly 0.55, strict `>`
- `test_win_rates_are_reported_on_the_unit_interval`
- `test_forced_add_fires_exactly_at_max_lp` — fires at `6`, not at `7`

## Cost and what was kept

60,960 games and 30,416 optimizer steps discarded. The artifacts are retained under the `scaled`
tag as the evidence for this record; no result derived from them is reported as a campaign
finding. The restart is from fresh random initialization, which `CONTRACT.md` requires of the
ByteRL branch in any case, so no partially-trained weights carry across the fix.

The restart is also reconfigured — `--games-per-lp 8000 --learning-periods 10` instead of
`20000 × 8` — because the original shape could not reach a second historical addition inside any
feasible wall clock even after defect 3 is fixed. Smaller learning periods check promotion more
often, reach the forced addition at LP7 rather than never, and leave two further periods in which
historical sampling is exercised against a pool of size two rather than a degenerate pool of one.
