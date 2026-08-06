# RL Readiness

**RL_READINESS = NOT_READY_FOR_RL**

BEST_STUDENT=NONE; SUBMISSION_B=DO_NOT_SUBMIT. The student is materially weaker than the teacher, so RL (explicitly out of scope for c006) must not begin.

## Highest-leverage blocker

No distilled student is non-inferior to the teacher: best one-sided 95% lower bound is 0.125 vs the 0.45 threshold, and both students show major matchup regressions across the entire strategic field. Behavioral cloning reproduces ~73% of teacher decisions offline but compounding errors collapse full-game strength. Highest-leverage next step: close the gameplay gap (interactive correction / DAgger-style on-policy relabeling, or a stronger teaching signal) BEFORE RL.

## What IS ready
- Decoder/representation covers 100% of teacher decision forms without strategic fallback (ordered forms absent).
- Frozen checkpoints + evaluation are reproducible (byte-identical re-run).
- Packaging + CPU latency are fine (single-process P99 0.464ms) — the blocker is policy strength, not operations.
