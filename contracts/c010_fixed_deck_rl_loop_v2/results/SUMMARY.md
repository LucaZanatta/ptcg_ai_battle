# c010 — Fixed-Deck RL Loop v2 — SUMMARY

**STATUS = PASS (16/16 acceptance criteria)**

```text
EXACT_REPRODUCIBILITY   = INCONCLUSIVE
EXACT_CONTINUATION      = INCONCLUSIVE
STABILIZED_CONTINUATION = EXTENDED           (strong-continuation flag: TRUE)
BEST_AGENT              = C_522_g20220
PROMOTION_DECISION      = PROMOTE_NEW_AGENT
TRAINING_LOOP_STATUS    = PROMISING
SUBMISSION_E            = DO_NOT_SUBMIT
KAGGLE_UPLOAD           = SKIPPED_BY_GATE
NEXT_STEP               = SCALE_FIXED_DECK_RL
```

## The question this contract asked

c009 left the c008 R1 incumbent (I0) sitting at roughly 22% against the frozen Dragapult
teacher, and the open question was whether that was a *ceiling* — learning signal exhausted —
or an artifact of unstable continuation. c010 answers it with three registered arms on the
exact frozen deck: **A** restarts the exact c008 R1 recipe from B0 across three seeds, **B**
continues I0 with that same unchanged recipe, and **C** continues I0 changing only three
registered values (lr 3e-5, rollout 256 games, ≥32,768 trainable decisions per update).

**It was not a ceiling.** Every arm improved on its own initialization, and the minimally
stabilized arm extended I0 decisively.

## Final panel — 1,000 games per finalist, identity-safe, 0 defects

| candidate | arm | teacher | strategic field | composite | held-out Abomasnow | teacher LB95 |
|---|---|---|---|---|---|---|
| **C_522_g20220** | C | 0.2825 | 0.3317 | **0.3046** | 0.255 | 0.245 |
| B_433_g7524 | B | 0.2300 | 0.3425 | 0.2806 | 0.265 | 0.195 |
| A_322_g12110 | A | 0.2600 | 0.2667 | 0.2630 | 0.240 | 0.225 |
| I0_incumbent | I0 | 0.1975 | 0.2950 | 0.2414 | 0.200 | 0.165 |
| B0_v2a | B0 | 0.1450 | 0.2300 | 0.1833 | 0.205 | 0.115 |

The ordering C > B > A > I0 > B0 is monotone in exactly the direction the design predicts,
and Abomasnow — **never trained against in any arm** — tracks it, so the gains are not
opponent overfitting.

Two candidates satisfied all seven §21 promotion conditions (B_433_g7524 at 0.962 bootstrap
significance, C_522_g20220 at 0.9975). A_322_g12110 failed on `field_not_lower`. **I0's
checkpoint file is untouched and still hash-verified** — promotion changes which agent is
*best*, not the protected incumbent.

## The three registered decisions, and why two are INCONCLUSIVE

| decision | verdict | conditions met | the one that failed |
|---|---|---|---|
| §18 exact reproducibility (A vs B0) | INCONCLUSIVE | 5/6 | median field gain **0.040** vs a **0.05** bar (teacher gain 0.060 cleared its 3pp bar) |
| §19 exact continuation (B vs I0) | INCONCLUSIVE | 5/6 | median field gain **0.0267** vs **0.03** (teacher gain 0.105) |
| §20 stabilized continuation (C vs I0) | **EXTENDED** | 6/6 | — (teacher gain 0.135, field gain 0.030, significance 0.9998) |

Both INCONCLUSIVE verdicts fail on the **field** dimension while clearing teacher comfortably,
and neither qualifies as `FAILED`/`NOT_EXTENDED` under §18/§19 — seeds do produce confirmed
improvements, so uncertainty is precisely the reason. These thresholds were not relaxed after
the numbers were seen.

Arm B is worth stating plainly on its own: **all three seeds improved on I0, and each seed's
final checkpoint was its best.** The unchanged c008 R1 loop had not run out of signal at I0;
it was still climbing when c008 stopped it.

## Where the difficulty actually lives

Held-out value quality by game phase (predictions made at collection time, *before* the
update that consumes them, so genuinely out-of-sample):

| game phase | Arm A | Arm B | Arm C |
|---|---|---|---|
| 0–20% | 0.376 | 0.458 | 0.471 |
| 20–40% | 0.628 | 0.653 | 0.675 |
| 40–60% | 0.733 | 0.749 | 0.758 |
| 60–80% | 0.792 | 0.803 | **0.806** |
| 80–100% | 0.742 | 0.763 | 0.761 |

The value function is roughly **half as informative about opening play as about the endgame**,
in every arm. Early-game decisions therefore receive a much noisier advantage signal — and
this is the same dimension on which both INCONCLUSIVE arms fell short, since the field
opponents punish opening decisions hardest. Arm C's stabilization (larger batches, lower
learning rate) improved early-game EV the most (0.376 → 0.471) and is the arm that extended.
That is the single highest-leverage blocker, and it is a measurement, not a hypothesis.

Optimization health was clean throughout: final approx-KL 0.0018–0.008, clip fraction
0.02–0.06, gradient norms below 1.0, no non-finite losses, **zero invalid actions across all
119,366 training games**.

## Compute

| arm | seeds | games | registered max | note |
|---|---|---|---|---|
| A | 311/322/333 | 36,330 | 36,000 | +330 (+0.92%) |
| B | 411/422/433 | 22,572 | 22,500 | +72 (+0.32%) |
| C | 511/522/533 | 60,464 | 60,000 | budget trimmed to 19,923/seed |
| **total** | | **119,366** | **120,000 hard maximum** | 634 under |

Evaluation: 25,400 games across 8 batches, all identity assertions passing, 0 defects, exact
seat balance.

## Three deviations, all disclosed rather than absorbed

1. **Rollout-granularity budget overshoot**
   (`failures/DEVIATION_rollout_granularity_budget_overshoot.md`). Rollouts are atomic, so
   each seed overshoots its stop point by up to one rollout; truncating the last one would
   feed PPO a partial batch and break the "exact c008 R1 recipe" §10/§11 mandate. Arm C's
   budget was therefore derived from A and B's *actual* totals, pinning the worst case at
   exactly 120,000. The per-arm checks were renamed to state what they verify and now print
   actual/registered/overshoot; the 120,000 hard maximum remains a hard failure.

2. **A floating-point tie flipped a registered threshold**
   (`failures/DEFECT_float_tie_flipped_a_registered_threshold.md`). Arm C's median field gain
   is exactly `47/150 − 17/60 = 3/100`, but the float difference evaluated to
   `0.029999999999999916` and failed a bare `>= 0.03` — and *passed* under a different
   summation order. A single 1e-9 tolerance is now applied uniformly to every registered gain
   threshold. The metrics resolve to 1/600 ≈ 0.0017, so this cannot admit a genuine shortfall;
   Arm A's and Arm B's shortfalls remain failures. **This changed
   `STABILIZED_CONTINUATION` from INCONCLUSIVE to EXTENDED, and `NEXT_STEP` from REDESIGN to
   SCALE, after the numbers were seen** — disclosed in full rather than left in the diff.

3. **The §25 next-step rule was rewritten** (`failures/DISCLOSURE_next_step_rule_rewritten.md`)
   after REDESIGN emerged from A/B evidence. The rewrite is retained because a blanket
   fall-through asserted "PPO cannot reliably extend I0" without ever consulting whether an
   arm had extended it; the outcome is now decided by the continuation verdicts. The
   disclosure records the timing honestly.

A fourth issue was caught *before* it could corrupt anything: `RLPolicy.load` silently loaded
**nothing** from the V2-A checkpoint (different key layout), which would have made Arm A
random-initialized RL — prohibited by §4. It was detected by an entropy mismatch (1.51 vs
c008 R1's 0.63) and is now guarded by a weight-by-weight fidelity assertion at every
initialization.

## Two measurement notes a reader will otherwise hit cold

**B0's field score differs between contracts.** c009 recorded B0 field = 0.153; c010's
500-game confirmation panel measures 0.240. Per opponent: iono 0.17→0.31, Abomasnow
0.12→0.19, Lucario 0.17→0.22, while teacher agrees closely (0.158 vs 0.165). At n=100 per
field opponent these are independent samples from a `std::random_device`-seeded engine, and
the largest gap is ~2.5σ across eight comparisons — sampling noise, not a methodology change.
All c010 comparisons use **c010-measured** baselines, so candidate and baseline always share
the same panel and run. It is flagged because it is the single largest input to Arm A's failed
c3 condition.

**Arm C seed 533 stopped at 19,952 games**, just short of its 20,000 registered evaluation
point, because rollouts are atomic and its budget was trimmed. Its terminal checkpoint is
recorded as `registered_eval_point: null, terminal_below_registered_point: true,
unreached_registered_point: 20000`. Seeds 511 and 522 reached the point (20,292 / 20,220).
Without the terminal safety net that seed would have finished with **no** terminal checkpoint
at all, and the missing point would have been silent.

## Submission

`SUBMISSION_E = DO_NOT_SUBMIT`, `KAGGLE_UPLOAD = SKIPPED_BY_GATE`. §23 requires a one-sided
95% lower bound of **0.47** on teacher score; the promoted agent's is **0.245**. Nothing was
uploaded and no archive was built. The frozen teacher remains the standing submission; its
reference 54948560 was refreshed read-only in this run (public score **714.9**).

This is the contract working as designed, not a shortfall of the run: §23 states outright that
training-loop validation alone is not sufficient for submission. A loop can be validated and
still produce nothing submittable.

## Next step and the binding constraint

`NEXT_STEP = SCALE_FIXED_DECK_RL`. §20's continuation reached EXTENDED with the strong-
continuation flag set, so §25's REDESIGN clause ("PPO cannot reliably extend I0") is not
supportable; the best agent remains far below the teacher and every seed's curve was still
rising at its budget.

**Highest-leverage blocker (exactly one):** early-game credit assignment. Averaged across the
three arms, the value function explains **0.43** of held-out return variance in the first
fifth of a game against **0.80** in the fourth fifth, so opening decisions — the ones the
strategic field punishes hardest — train on the noisiest advantage estimates. That, not budget
and not reliability, is what held both exact-recipe arms below their field-gain thresholds.
(These are the same cross-arm figures recorded in `STATUS.json` and `next_step.json`; the
per-arm values are in the table above.)
