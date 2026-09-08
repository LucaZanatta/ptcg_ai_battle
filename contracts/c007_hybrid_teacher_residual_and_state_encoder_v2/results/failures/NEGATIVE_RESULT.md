# Failures / Negative-result record — c007

**No blocking failures.** All 16 acceptance criteria were executed and verified; the
contract is `PASS`. This file documents the (acceptable, §1/§33) **negative competitive
result** and the adversarial checks that confirm it is honest rather than a hidden defect.

## The negative result
No distilled/hybrid agent beats the frozen Dragapult teacher:
- Four pre-registered one-rule damage-counter variants (V_plan_a, V_reset, V_thresh,
  V_greedy) were A/B'd over **two independent 400-game batches each**; **none clears the
  90% bootstrap LCB>0 improvement gate in both batches**.
- `BEST_HYBRID = NONE`, `SUBMISSION_C = DO_NOT_SUBMIT`, `RESIDUAL_RL_READINESS = NOT_READY`.

Mechanism: the teacher's Phantom Dive spread-allocation heuristic is well-tuned; a narrow
one-rule residual has no exploitable seam. Apparent per-batch edges are sampling noise
(difference SE ≈ 0.035 at 400 games/arm) — point estimates flip sign across batches
(V_plan_a −0.028 → +0.058; V_greedy −0.058 → +0.025).

## Why this is honest, not a bug (adversarial checks)
1. **Instrumentation is behavior-equivalent.** 19,050/19,050 replay decisions + 100 live
   games, 0 mismatch — the plan labels are captured without perturbing the teacher.
2. **The encoder is real and loss-audited.** 12 explicit board slots, exact multisets,
   cross-option encoder, real previous-action identity; all 19,050 decisions encode
   deterministically; §7.7 audit justifies every omission. Model gradients numerically
   checked; a real value-head sentinel-leak bug was caught and fixed before training.
3. **The models learned.** Held-out test agreement ~0.72 (≫ a first-index policy); ECE
   0.024 (well-calibrated). They imitate the teacher well; they simply cannot exceed it.
4. **The hybrid is safe and reliable.** H0 is action-identical to the teacher (0/19,264
   mismatch); H1/H2 run 240 games each with zero invalid/exception/timeout/fallback; H2
   makes 0 overrides (overrides disabled — no reproducible improvement) and is therefore
   action-identical to the teacher.
5. **Non-inferiority is definitional.** H2-vs-teacher is a mirror match (0 overrides);
   point 0.491, one-sided 95% LB 0.4625 over 800 games — the LB straddles the 0.47 gate
   by pure sampling variance, not real inferiority. AC-11 completes regardless (it may
   pass when H2 misses the competitive gate).
6. **The privileged aux heads were tested and honestly reported as unhelpful** (ablation
   V2B−V2A iw −0.004); c006's `MEMORY_NOT_JUSTIFIED` is revisited, not assumed.
7. **The gate was not lowered.** The improvement gate requires LCB>0 in two independent
   batches; it was applied as registered and failed. No re-fishing for a passing sample.

## Consequence (all rule-forced)
`BEST_HYBRID=NONE` → `SUBMISSION_C=DO_NOT_SUBMIT` → `KAGGLE_UPLOAD=SKIPPED_BY_GATE` →
`PROMOTION_DECISION=NO_HYBRID_SUBMISSION` → `RESIDUAL_RL_READINESS=NOT_READY`. The frozen
teacher (ref 54948560, same-run public score 703.6) remains the standing submission.

## Notes / minor limitations (non-blocking)
- Branch-and-rollout is technically available via the engine search API (execution-verified
  fork+rollout) but is determinized + `random_device`-stochastic and hard to synchronize the
  teacher within after a deviation; the §12 controlled-variant fallback was used, with
  policy-level (not fabricated per-state) evidence.
- Cross-option-set sensitivity is low (0.003): the encoder supports set interaction (§7.5)
  but the teacher's per-option scoring is largely set-independent, so it is little used.
