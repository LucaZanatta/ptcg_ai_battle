# Failures / Negative-result record — c006

**No blocking failures.** All 14 acceptance criteria were executed and verified; the
contract is `PASS`. This file documents the (acceptable, §1/§21) **negative model
result** and the checks that confirm it is honest rather than a hidden defect.

## The negative result
Neither distilled student is non-inferior to the frozen Dragapult teacher:
- S1 vs teacher: point 0.120, one-sided 95% LB **0.085**.
- S2 vs teacher: point 0.170, one-sided 95% LB **0.125** (threshold 0.45).
- Strategic gauntlet mean-vs-field: teacher 0.604, S1 0.188, S2 0.150, control 0.106.
- 8/8 student×opponent matchups are major regressions vs the teacher.

Mechanism: behavioral cloning reproduces ~73% of teacher decisions on held-out games,
but ~27% per-decision disagreement **compounds** over ~80-decision games (distribution
shift), collapsing full-game strength — a textbook BC limitation.

## Why this is honest, not a bug (adversarial checks run on captured data)
1. **Games are genuine, not crashes.** All 400 non-inferiority + 800 gauntlet + 80 smoke
   games completed `DONE/DONE` with **0** agent errors, **0** timeouts, **0** invalid
   selections. The losses are real games lost, not attributed exceptions.
2. **The models actually learned.** Both students **beat the deterministic control**
   (S1 0.188, S2 0.150 > control 0.106 mean-vs-field) and reach ~73% test agreement
   (≫ the ~15% a first-index policy scores). A decode/featurize bug would show up as
   sub-control play; it does not.
3. **Train == serve.** Node-forward == numpy-forward to 1e-16; the featurizer runs on the
   identical normalized observation in dataset and live play; checkpoints reproduce
   byte-identically. The evaluated model is the shipped model.
4. **Memory finding is robust.** S2 ≈ S1 offline (matched inputs) and both memory
   thresholds fail (high-impact +0.09pp; game-level iw CI includes 0) — consistent with
   the measured **zero** exact observation aliasing.

## Consequence (all rule-forced)
`BEST_STUDENT=NONE` → `SUBMISSION_B=DO_NOT_SUBMIT` → `KAGGLE_UPLOAD=SKIPPED_BY_GATE` →
`PROMOTION_DECISION=NO_STUDENT_SUBMISSION` → `RL_READINESS=NOT_READY_FOR_RL`. Gates were
**not** lowered to manufacture a submission. The frozen teacher remains the standing
Kaggle submission.
