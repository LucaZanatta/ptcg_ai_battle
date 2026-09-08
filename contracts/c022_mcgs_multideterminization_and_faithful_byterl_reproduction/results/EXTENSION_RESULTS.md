# What the extension window bought

A user-granted compute window to 07:00 on 2026-07-31 funded two arms, both registered in
`PREREGISTERED_EXTENSION.json` **before either ran**, and both chosen because they could confirm
conclusions this contract had already published against itself.

One answered its question. One was defeated by the same wall the whole MCGS branch keeps hitting.

---

## 1. `BYTERL_FIXED_DECK_AT_SCALE` — the faithful system does learn

`br3_fixed_deck_long`: BR3, fixed deck, **fresh random weights**, identical hyperparameters to the
registered arm, run to a substantially larger sample budget. Checkpoints evaluated on the same
128-game external panel as they landed, same seed 777001, ten points.

| checkpoint | field score | Wilson 95% |
|---|---:|---|
| u012000 | 0.0547 | [0.0267, 0.1086] |
| u036000 | 0.0859 | [0.0487, 0.1473] |
| u060000 | 0.1328 | [0.0846, 0.2024] |
| u086000 | 0.0547 | [0.0267, 0.1086] |
| u110000 | 0.1328 | [0.0846, 0.2024] |
| u134000 | 0.1328 | [0.0846, 0.2024] |
| u150000 | 0.1328 | [0.0846, 0.2024] |
| u174000 | 0.1250 | [0.0784, 0.1934] |
| u198000 | 0.1250 | [0.0784, 0.1934] |
| u222000 | **0.1797** | [0.1228, 0.2552] |

Pooled, because a single 128-game evaluation has a ~10-point interval and reading ten of them by
eye is how the u060000 excursion nearly became a finding:

| | games | field score | Wilson 95% |
|---|---:|---:|---|
| random floor (`floor_fixed_deck`) | 128 | 0.0234 | [0.008, 0.0666] |
| **early half** (u012000–u110000) | 640 | 0.0922 | [0.0721, 0.1171] |
| **late half** (u134000–u222000) | 640 | **0.1391** | **[0.1144, 0.168]** |

**Both halves separate from the random floor.** The late half's lower bound (0.1144) clears the
floor's upper bound (0.0666) by a wide margin, and so does the early half's (0.0721).

**So `BYTERL_FIXED_DECK`'s first requirement — "a statistically credible improvement over random
initialization/floor" — is MET**, where the registered arm at 9.11% of the matched budget could
not meet it at any checkpoint.

**The second requirement is not.** The rise from 0.0922 to 0.1391 is +4.7 pp, but the two
intervals overlap — by 0.0027, which is a hair, and a hair is not a separation. The u086000 dip
back to 0.0547 is real and is why. So: *credibly better than random, with a trajectory that is
suggestive and not established.* `BYTERL_FIXED_DECK` remains `PARTIAL`, on the second requirement
rather than the first.

### What this changes about the contract's ByteRL reading

The registered arms were flat inside the floor's interval at 9–11% of the matched budget, and
`FIDELITY_RULES §5` required reporting that as unresolved rather than as method failure. This arm
shows that was the correct call and not merely the cautious one: **given more of the sample budget
the published system learns to beat random play on this game.** The earlier flatness was budget.

It is worth being precise about how much this is and is not. The frozen competitive bar scores
0.5833 on the broad panel. This arm reaches ~0.14–0.18. Learning is demonstrated; competitiveness
is not, and nothing here suggests the gap closes at the matched budget.

### One structural detail worth recording

The evaluation scores quantize: 0.1328 is exactly 17/128, 0.0547 exactly 7/128. With 128 games
over four opponents that is 32 games each, and the wins come almost entirely from one matchup —
the same 0-for-three-opponents structure the final panel found in the MCGS candidates, arriving
independently in a learned policy. Both methods, trained and searched by completely different
means, end up beating the same single archetype and nothing else.

---

## 2. `MCGS_ENSEMBLE_AT_DEPTH` — blocked, twice, by simulation cost

`FINDING_the_calibration_gain_is_compute.md` named this as the measurement most likely to overturn
its own conclusion: the ensemble contributes 1.2% of the calibration improvement at 96 simulations
per decision, and how between-world disagreement scales with depth was unmeasured.

**At 768 simulations per decision (8×)**: `k8_s768` completed **15 of 40 games**, 62.5% abandoned
against `paired_k8`'s 0%. The registered 8 pp exclusion-spread gate was violated sevenfold, and
per `D15` the survivors are the games that finish fast — a biased subsample. Quarantined in
`failures/superseded/depth_768_guard_bound/`, cited nowhere. Recorded as `D27`.

**At 384 simulations per decision (4×)**: `k8_s384` ran to its two-hour arm timeout without
completing 40 games, and its control could not then fit the window.

The arithmetic is the same both times. A simulation costs **~29 ms** here; 384 simulations across
a 50-decision budget is ~560–900 s of search per game, 768 is 1,100–1,900 s, and a per-game guard
sized to either produces arm durations this hardware cannot deliver at 40 games. Raising the guard
does not help — `D15` established that abandonment here is the stalemate rate, so a longer guard
lengthens the games that were never going to terminate.

**So the depth question remains open, and it is open for a recorded, measured reason rather than
for want of trying.** It is the single measurement most likely to change the MCGS conclusion, and
it needs either a faster simulator or a per-game guard budget this machine does not have. The
1.2% figure therefore stands **as measured at 96 simulations per decision**, and
`FINDING_the_calibration_gain_is_compute.md`'s own closing caveat — that the two regimes need not
behave alike — stands with it.

---

## What was NOT done with the window, and why

- **`br3_end_to_end` was left at 10.85%.** Running both decisive arms would have halved each. §2
  orders fixed-deck first and it carries no deck-construction confound, so one decisive answer was
  chosen over two indecisive ones. `BYTERL_E2E` remains undertrained as a consequence, and that is
  a choice rather than an oversight.
- **`TRANSFER` was not run.** Its gate opened only when `BYTERL_REFERENCE_FIDELITY` reached PASS,
  and T1/T2 need 200 paired games each against a measured noise floor. There was no window for it
  after the depth arms consumed their share.
- **M09/M10 frozen-decision stability and the M08 ceiling remeasurement** remain queued, both
  registered, both unrun.

Nothing in this file modifies a threshold, an aggregation rule or a previously reported number.
The registered arms stand exactly as committed.
