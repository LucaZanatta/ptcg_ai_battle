# c007 — Hybrid Teacher Residual & State Encoder v2 — Summary

**Status: PASS (16/16 acceptance criteria executed and verified).** A principled,
evidence-backed **negative competitive result**: the state encoder is accepted, the
teacher instrumentation is behavior-equivalent, one residual context is admitted, but no
controlled variant reproducibly beats the tuned rule-based teacher, so `BEST_HYBRID =
NONE` and `SUBMISSION_C = DO_NOT_SUBMIT`. Gates were not lowered.

## Decisions
```
STATE_ENCODER_V2        = ACCEPT
TEACHER_INSTRUMENTATION = VALID
RESIDUAL_CONTEXTS       = [dragapult_damage_counter]
BEST_HYBRID             = NONE
SUBMISSION_C            = DO_NOT_SUBMIT
PROMOTION_DECISION      = NO_HYBRID_SUBMISSION
RESIDUAL_RL_READINESS   = NOT_READY
```

## Representation changes (State Encoder v2, AC-03)
Directly fixes the c006 diagnosis: **12 explicit board slots** (self active + 5 bench,
opp active + 5 bench) with full dynamic state (HP/damage/energy-type counts/status/KO
range/evolution stack/prize yield) — never averaged; **exact hand & discard multisets**
via DeepSets set encoders; a **cross-option set encoder** so an option score can depend
on the other legal options; **actual previous selected-option identity** in history
(card/attack/type, reset per game); deterministic 52-d card semantics + a **zero-init
id-embedding residual** for unseen legal cards. All 19,050 stored decisions encode
deterministically with 0 errors. §7.7 audit: 22 fields represented directly, 10
deterministically transformed, 3 intentionally omitted (each justified), 2 hidden/privileged.

## Instrumentation parity (AC-04)
Behavior-equivalent instrumented teacher copy (byte-identical decision logic + one
side-effect-free capture line; planning globals snapshotted read-only after each call).
Replay parity **19,050/19,050 decisions, 0 mismatch, 0 exceptions**; live dual-call
parity **100 games / 8,796 decisions, 0 mismatch, 0 invalid, 0 exceptions, 100 completed**.

## Data & model (AC-05, AC-06)
Expanded v2 dataset: **720 teacher-controlled strategic games / 61,312 ordered decisions**
(≥600 / ≥50,000), both seats vs Mega Lucario / Mega Abomasnow / Iono / Dragapult mirror,
+48 control games (reported separately), whole-game 70/15/15 split, no leakage, plan
labels 100% populated. Two pure-numpy advisory models (V2-A action-only 536,961 params;
V2-B + privileged aux heads 538,770 params — both in the [500k, 2M] band, gradient-checked).
Held-out c007 test: exact agreement ~0.72, importance-weighted ~0.708, c006 back-eval
~0.72; ECE 0.024; single-process P99 ~0.4 ms. **Ablation: the privileged planning aux
heads do NOT improve teacher agreement** (V2B−V2A iw −0.004). Cross-option-set sensitivity
is low (0.003) — the teacher's per-option scoring is largely set-independent.

## Residual admission & improvement labels (AC-07, AC-08)
Admitted context (all 8 criteria met): **dragapult_damage_counter** (9,150 train+val
examples, in-context ECE 0.023). It is the only context with a counterfactual A/B, so the
only admissible one. Four **pre-registered one-rule** damage-counter variants
(V_plan_a / V_reset / V_thresh / V_greedy) were A/B'd over **two independent 400-game
batches each**; **none clears the LCB>0 improvement gate in both batches**. Point estimates
flip sign across batches (V_plan_a −0.028→+0.058, V_greedy −0.058→+0.025), definitive
evidence that any apparent edge is sampling noise. **0 improvement labels; admitted variant
= None.** Reliability perfect across all A/B arms.

## One on-policy iteration (AC-09)
H2 candidate frozen and run vs the field (160 games): 2,400 admitted-context decisions,
665 model/teacher disagreements, 14 OOD-boundary states, **0 overrides**. Relabeling the
admitted context via the validated protocol produced **0 new positive labels**; the
residual head was retrained once (no change); final H2 frozen. No repeated DAgger.

## Hybrid evaluation (AC-10/11/12)
- **H0 parity:** 240 games, 19,264 decisions, **0 mismatch** (H0 action-identical to teacher).
- **Reliability:** H1 and H2 each 240 games, **zero invalid / exceptions / timeouts / fallbacks**.
- **H2 vs teacher:** 800 games, point 0.491, one-sided 95% LB 0.4625. H2 makes **0 overrides**
  (overrides disabled — no reproducible improvement), so it is action-identical to the teacher;
  this is a MIRROR match whose LB straddles the 0.47 threshold by sampling variance.
  Non-inferiority is definitional via action identity; AC-11 completes regardless.
- **Strategic gauntlet:** teacher mean-vs-field 0.559, H2 0.569 (within noise; control
  excluded and reported separately at 0.975 for both, §9/§15); **no improvement matchup
  (≥5pp @ ≥90%), no major regression (≥7pp @ ≥90%)**. The teacher-vs-field estimate is
  consistent across harnesses (H0 0.541, A/B ~0.54, gauntlet 0.559).

## Submission, Kaggle, promotion, RL readiness (AC-13/14/15)
`BEST_HYBRID=NONE` → `SUBMISSION_C=DO_NOT_SUBMIT` → **Kaggle upload SKIPPED_BY_GATE**
(no upload; no credentials exposed). Teacher submission ref 54948560 refreshed read-only in
the same run: **703.6** (recorded 617.8). A diagnostic hybrid archive
(`submission_C_hybrid_NOT_FOR_SUBMISSION.tar.gz`, 3.98 MB) is structurally complete,
excludes data/secrets, runs **80 in-process games** both seats with 0 defects, is
**self-contained** (a 2-game smoke runs from the freshly extracted archive), and falls
back to the teacher when model weights are missing — the hybrid is deployable, just not
competitive. (§16 packaging validation is not required under `DO_NOT_SUBMIT`; this is
diagnostic evidence.) `PROMOTION_DECISION=NO_HYBRID_SUBMISSION` (the frozen
teacher remains the standing submission). `RESIDUAL_RL_READINESS=NOT_READY` (no validated
positive residual action-space to optimize within).

## Highest-leverage blocker
The tuned rule-based teacher has no exploitable seam a one-rule residual can beat: four
pre-registered damage-counter variants failed the two-batch improvement gate. Closing the
gap needs a genuinely better in-context policy (validated by branch-and-rollout with proven
teacher synchronization, or a broader learned intervention) BEFORE residual RL.

## Integrity
8 `c007:` source-only commits; **no file under c005/ or c006/ modified** (full recursive
re-hash confirms); no `.so` committed; no credentials stored; results/ is uncommitted
review evidence.
