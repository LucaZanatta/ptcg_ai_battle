# Prior-results audit — c014 and c015 from raw artifacts (§9)

Audited 2026-07-26T19:04:02.556277+02:00 (Europe/Rome).

re-derived from raw per-game records, archive bytes, decision traces and the live Kaggle listing; SUMMARY.md and STATUS.json were not trusted on their own.

## Branch classification

| branch | operational | evidence integrity | competitive strength | role |
|---|---|---|---|---|
| c014 custom Archaludon/Cinderace | PASS | PASS | WEAK | CONTROL |
| c015 custom Iono/Bellibolt | PASS | DEFECTIVE | FALSIFIED | ARCHIVE |

### c014 — operationally valid, competitively weak

Published matchup rates were recomputed from the raw per-game records: **0 disagreements**. The evidence is sound; the agent is not.

| opponent | games | score rate (recomputed) |
|---|---|---|
| iono | 100 | 0.02 |
| dragapult | 100 | 0.09 |
| mega_abomasnow | 100 | 0.35 |
| mega_lucario | 100 | 0.48 |
| __self__ | 100 | 0.48 |
| __safe__ | 100 | 0.67 |

Public mining took 0.143 h. Package hash re-computed from the archive's own bytes matches its manifest: **True**.

**Lesson preserved deliberately:** a from-scratch priority table did not reproduce a strong public Archaludon agent. That is the error c016 exists to correct.

### c015 — thesis falsified AND reporting defective

The pre-registered falsifier required > **0.6** against the c014 target. Raw records give **0.36**. Falsified: **True**.

**3 report-integrity defects** found by re-derivation:

- **c015_mechanism_b_zero_opportunity_success_claim** (HIGH) — strategy_coherence.json records Mechanism B with ZERO opportunities and ZERO executions, because the recompute step initialised the counters and never populated them from the expert's own tallies. complementarity_report.json nevertheless states B executed '1.000 when attacking and legal'. A rate asserted over a zero denominator is exactly the claim §22 requires a validator to reject; it must read NOT_OBSERVED.
- **c015_attachment_rate_degenerate_denominator** (MEDIUM) — numerator and denominator are incremented on the same branch, so this rate is 1.000 by construction and measures nothing. It cannot distinguish correct from incorrect attachment.
- **c015_status_public_score_stale** (LOW) — STATUS.json kept the poll-time reading while the board recorded a later one. The public score is a live ladder rating, so a single stored value is a snapshot and must be labelled as one.

The first of these is the precise failure mode §22 requires the c016 validator to reject: a success rate asserted over a zero denominator. c016's validator implements that check, and zero opportunities must be reported as `NOT_OBSERVED`.

### Dragapult

temporary internal champion — the strongest confirmed package the project owns, explicitly NOT a winning target. Latest listing reading: **719.7** (SubmissionStatus.COMPLETE).

| submission | ref | latest reading |
|---|---|---|
| Dragapult control | 54948560 | 719.7 |
| c014 custom | 55004756 | 516.8 |
| c015 custom | 55005237 | 412.9 |

the public score is a live ladder rating; these are timestamped readings.

### Reusable inputs

14 c014 public-source snapshot files are available and hashed; c016 starts from them before any fresh search (§11).

