# c006 — Distilled Policy Baseline — Summary

## Final status
**PASS** — 14/14 acceptance criteria executed and verified. The result is a
**principled negative**: two compact distilled students were trained, evaluated
offline and in full cabt games, and honestly judged **not** non-inferior to the
frozen Dragapult teacher. Per §1/§21 this is an acceptable PASS with
`BEST_STUDENT=NONE`, `SUBMISSION_B=DO_NOT_SUBMIT`, `RL_READINESS=NOT_READY_FOR_RL`.

## Dataset examples and games
Rebuilt **ordered** sequence dataset from the c005 capture *without regenerating
games* (decision/turn/step + previous-context/action restored; decision_index
recovered losslessly from the c005 example_id hash; split membership preserved
exactly): **19,050** examples across **240** games — train 170/13,795,
validation 37/2,991, test 33/2,264.

## Stateless ambiguity
Under the documented normalization (serial/step/clock removed), **exact**
observation aliasing = **0** conflicting decisions → empirical upper bound on
stateless exact agreement = **1.0**; only 14 near-duplicate conflicts. Observation
aliasing is *not* the limiting factor — the teacher's internal state is largely
recomputable from the visible board. (This foreshadows that memory won't help.)

## Card vocabulary size
**1,270** rows = 1,267 legal cards (each its own row + 52 structured features, no
`<UNK>` collapse) + PAD/MASK/UNKNOWN_INVALID_ID. Deterministic from
`cg.api.all_card_data()`; all teacher/opponent deck cards present.

## S1/S2 parameter counts
- **S1 (stateless)**: 152,673 params (target 150k–500k). ✓
- **S2 (recurrent, GRU)**: 273,441 params (target 250k–650k). ✓
Both models are pure-numpy (autograd gradient-checked; Node-forward == numpy-forward
to 1e-16), so the evaluated/shipped model IS the trained model.

## Training seeds and selected checkpoints
3 registered seeds per architecture, all completed; early stopping on validation
importance-weighted agreement; **re-run of S1 seed 101 is byte-identical**
(reproducible, OMP_NUM_THREADS=1).
- **S1 selected**: seed 303, val iw-agreement 0.7066 (sha 293fb39fb5da…).
- **S2 selected**: seed 222, val iw-agreement 0.6982 (sha fbdfb0ef2dd4…).

## Test agreement metrics (frozen test, opened once)
| model | overall exact | importance-weighted | high-impact | P99 latency (single-proc) |
|---|---|---|---|---|
| S1 | 0.7323 | 0.6951 | 0.6748 | 0.071 ms |
| S2 | 0.7248 | 0.6897 | 0.6757 | 0.106 ms |

## Memory decision — **MEMORY_NOT_JUSTIFIED**
Both registered quantitative thresholds fail: S2−S1 high-impact test gain
**+0.09pp** (< 2pp); game-level importance-weighted agreement difference 95% CI
**[-0.029, 0.016]** (includes 0). S2 ≈ S1 offline (matched inputs) — "memory does
not help" is robust, not an inference artifact. No material gameplay improvement can
be claimed for a policy that isn't non-inferior.

## Student–teacher results (non-inferiority)
One-sided 95% lower bound (seat-balanced bootstrap; win=1/draw=.5/loss=0), 200
games each, both stopped early as clearly inferior:
- **S1 vs teacher**: point 0.120, LB95 **0.085** → non-inferior **False**.
- **S2 vs teacher**: point 0.170, LB95 **0.125** → non-inferior **False**.
All 400 games completed cleanly (0 errors/timeouts/invalid) — the losses are genuine.

## Strategic-gauntlet results (both seats, sequential protocol)
Mean seat-balanced score vs the fixed field {Mega Lucario, Mega Abomasnow, Iono,
teacher mirror}: **teacher 0.604, S1 0.188, S2 0.150, control 0.106**. **Both
students beat the deterministic control** (they genuinely learned to imitate) but
show **major matchup regressions vs the teacher on all 8 student×opponent matchups**.
Bradley-Terry ranks teacher and the strong official opponents well above the students.

## Reliability and latency
**Zero** reliability defects across all evaluation games (80 smoke + 400
head-to-head + 800 gauntlet). Authoritative single-process per-move latency: S1 P99
0.071 ms, S2 P99 0.106 ms; extracted-package P99 0.464 ms — all far inside the match
clock. (Gameplay-harness latency figures are inflated by parallel CPU contention and
are not match-time latency.)

## Best student — **NONE**
Neither student passes teacher non-inferiority (§15). A student is not chosen merely
for beating the other.

## Submission B decision — **DO_NOT_SUBMIT**
Gate not met (no best student). A clearly-marked **NOT_FOR_SUBMISSION** diagnostic
archive was built and validated (40 extracted-archive games, 0 defects, P99 0.464 ms,
runtime modules byte-identical to the evaluated repo); the real
`submission_B_student.tar.gz` is intentionally absent (§20).

## Kaggle upload status / reference / processing / scores
- **KAGGLE_UPLOAD = SKIPPED_BY_GATE** — no upload performed (gate DO_NOT_SUBMIT).
- Student submission reference: **none**; student public score: **none**.
- Teacher ref **54948560**: recorded public score **617.8**, live same-window
  snapshot **674.6** (SubmissionStatus.COMPLETE) — timestamped ladder snapshots.
- **PROMOTION_DECISION = NO_STUDENT_SUBMISSION** — the frozen teacher remains the
  standing submission; no student score exists to promote.

## RL readiness — **NOT_READY_FOR_RL**
Highest-leverage blocker: no distilled student is non-inferior to the teacher (best
one-sided LB 0.125 vs 0.45; major regressions field-wide). Behavioral cloning
reproduces ~73% of decisions but compounding errors collapse full-game strength.
What IS ready: decoder covers 100% of teacher decision forms without strategic
fallback (no ordered forms), checkpoints+eval are reproducible, and
packaging/latency pass — so the blocker is policy strength, not operations.

## Known limitations
See `STATUS.json.known_limitations` (compounding-error BC gap; a minor S2-only
prev-action input skew documented not retrained; conservative size/latency posture
inherited from c005; non-reproducible engine trajectories with reproducible
analysis/checkpoints).

## Recommended next contract
c007: close the gameplay gap before RL — on-policy relabeling (DAgger-style
interactive correction against the frozen teacher) and/or a richer teaching signal —
then re-test non-inferiority; only then consider RL.
