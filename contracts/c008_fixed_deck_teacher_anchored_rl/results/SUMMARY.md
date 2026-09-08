# c008 — Fixed-Deck Teacher-Anchored RL — Summary

**Status: PASS (16/16 acceptance criteria executed and verified).** A complete, honest RL
experiment on the frozen c005 Dragapult deck. Result: **RL learns but does not beat the
tuned frozen teacher** within the bounded simulator budget, and teacher anchoring (R2) does
not outperform plain supervised-initialised RL (R1) or the teacher.

## Decisions
```
BEST_RL_ARM        = NONE
RL_FEASIBILITY     = INCONCLUSIVE
SUBMISSION_D       = DO_NOT_SUBMIT
PROMOTION_DECISION = NO_RL_SUBMISSION
NEXT_STEP          = REVISE_RL
```

## Dependencies / fixed variable
- c005 `4137d98` -> c006 `08ebac8` -> c007 `1f3fc63` -> c008; all immutable and unchanged (re-hashed).
- Fixed deck `sha256:8055443275c8…` (exact c005 Dragapult) for every arm/checkpoint/eval.
- Teacher `dragapult`, Kaggle submission ref `54948560`; same-run public score **705.4**.

## PPO configuration
Pure-numpy masked PPO (gradient-checked; deterministic toy positive control learns).
gamma 0.997, GAE lambda 0.95, clip 0.20, value coef 0.50, entropy 0.010->0.002, grad-norm
0.50, 4 epochs/rollout, rollout >=128 games AND >=8192 trainable decisions, minibatch 512,
AdamW (R0 lr 3e-4; R1/R2 lr 1e-4), value clipping, per-update advantage normalization.
Reward: win +1 / draw 0 / loss -1 only (no shaping). One non-forced selection = one RL step;
forced steps bypass. Policy 562,819 params (V2-A trunk + value head + STOP logit).

## Environment throughput
~0.5s/game (engine). Policy inference P99 3.5-3.8 ms is measured during the final reliability
eval under `nproc 16` and is **contention-inflated**; single-process per-decision inference is
sub-millisecond (the trunk is the c007 V2-A encoder, ~0.4 ms P99 single-process in c007). PPO
update ~16-38 s (8192x4, BLAS-threaded; RL is non-reproducible so multi-threaded BLAS is used).
Zero invalid actions, exceptions, timeouts, or ordered-decoder blocks across all training and eval.

## Games / decisions per arm
| arm | seeds | games | per-seed stop |
|---|---|---|---|
| R0 (random) | 101,202 | 15,210 | weak-vs-all@5000 ; budget@10000 |
| R1 (V2-A init) | 101,202 | 30,175 | reject@20000 ; reject@10000 |
| R2 (V2-A + teacher anchors) | 101,202,303 | 50,281 | reject@10000 ; reject@20000 ; reject@20000 |
| **total** | | **95,666** (< 230k cap) | |

Screening = evaluation (not training budget). Every seed ran to a registered early-stop or
budget. One documented pre-training defect (screening control-label) was corrected under the
registration restart rule; see `failures/DEFECT_control_label_screening.md`.

## Learning-curve conclusions
- **R0 (plain RL from random):** value head fits (explained variance ~0.8) but return stays
  negative and blend plateaus ~0.17 (teacher ~0.05). Plain RL does not learn to beat even the
  engineering control reliably within 10k games.
- **R1 (V2-A init):** a positive learning curve in **both** seeds — validation blend rises
  from ~0.30 to a ~0.40 peak (teacher screening score ~0.32 at peak), then PPO **degrades**
  back below the rejection thresholds (classic instability).
- **R2 (teacher-anchored):** decayed teacher-replay (0.50->0.05) and reference-KL (0.05->0.01)
  schedules verified applied. R2 learns similarly but **does not exceed R1 or the teacher**;
  peaks ~0.335 blend then degrades. The primary R2 > teacher hypothesis is not supported.

## Final evaluation (best checkpoint per arm — fairest to RL; all seeds reported)
- **Reliability:** R0/R1/R2 each 240 games, **zero invalid/exception/timeout**, P99 3.5-3.8 ms.
- **Teacher head-to-head (400 games each):** R0 0.060 (LB 0.042), R1 0.185 (LB 0.155),
  R2 0.130 (LB 0.103). **None non-inferior** (LB >= 0.47 required); even RL's strongest
  checkpoint loses ~81% to the teacher.
  - Note: checkpoints were *selected* on the registered 40-game screening blend (R1's peak
    screened at teacher ~0.325); the **400-game head-to-head is the authoritative strength
    estimate** and the gap reflects screening-cadence noise, not a regression between checkpoints.
- **Strategic mean-vs-field (control separate):** teacher **0.528** vs R1 0.289, R2 0.189,
  R0 0.11.
- **Held-out Mega Abomasnow** (never used in training/selection): teacher 0.50 vs R1 0.263,
  R2 0.112, R0 0.087.
- **Reproducible improvement:** none (no +5pp matchup, no global improvement).
- **Major regressions:** every arm is major-regressed vs teacher on multiple matchups
  (candidate <= teacher-0.07 at >=90% bootstrap) — this alone blocks submission.

## Best RL arm / feasibility
`BEST_RL_ARM = NONE` (no arm passes reliability + non-inferiority + no-major-regression).
`RL_FEASIBILITY = INCONCLUSIVE`: RL demonstrably learns (R1's positive learning curve across
>=2 seeds, working value head, zero defects) but no candidate reaches teacher non-inferiority
or a reproducible strategic improvement under the registered budget.

## Submission / Kaggle / promotion
`SUBMISSION_D = DO_NOT_SUBMIT` (no eligible candidate; a policy is never submitted for rising
training reward). **Kaggle upload SKIPPED_BY_GATE** (no upload; no credentials exposed).
Teacher ref 54948560 refreshed read-only: **705.4**. `PROMOTION_DECISION = NO_RL_SUBMISSION`
— the frozen teacher remains the standing competition submission.

## Next step / highest-leverage blocker
`NEXT_STEP = REVISE_RL`. **Blocker:** RL learns but no candidate reaches teacher
non-inferiority (best one-sided LB 0.155 << 0.47) — the sparse +/-1 terminal reward over
~70-decision games is too weak a credit-assignment signal for bounded numpy PPO to move a
fixed-deck policy past the tuned rule-based teacher, and PPO is unstable (peaks then
degrades). Revising toward denser value modeling / selective search, longer stabilized
budgets, or trust-region-tighter anchoring is the highest-leverage next move before any
consolidation.

## Known limitations
Pure-numpy PPO under a bounded simulator budget; sparse terminal reward; engine
`random_device` makes RL games non-reproducible (the toy PPO control, GAE, masking, and
dependency checks are deterministic); R2 on-policy teacher-action term disabled (unproven
synchronization after divergent RL actions) — R2 used offline replay + reference KL only.

## Integrity
6 `c008:` source-only commits; **no file under c005/c006/c007 modified** (re-hashed); no
`.so` committed; no credentials; results/ is uncommitted review evidence.
