# CURRICULUM_RESULT (AC-10)

**TIED**

| | median teacher | median field |
|---|---:|---:|
| P0 control | 0.3250 | 0.3600 |
| P1 elite self-play | 0.3250 | 0.3733 |
| difference | +0.0000 | +0.0133 |

- NOT  two_p1_seeds_beat_median_p0_teacher
- MET  two_p1_seeds_beat_median_p0_field
- NOT  median_p1_teacher_gain_ge_0.03
- NOT  median_p1_field_gain_ge_0.03
- MET  one_median_gain_90pct
- MET  no_majority_p1_regression
- MET  reliability_passes

**Caveat.** P1 ran the stage-0 mixture (15% elite) for its entire budget: the in-run evaluation defect recorded in failures/ left the curriculum gates without scores, so the 15->25->35->45% escalation was never exercised. P0 vs P1 therefore compares unchanged population against FIXED 15% elite self-play, not against the adaptive schedule.
