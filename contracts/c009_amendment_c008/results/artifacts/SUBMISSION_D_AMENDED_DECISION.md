# SUBMISSION_D_AMENDED Decision (AC-13)

**SUBMISSION_D_AMENDED = DO_NOT_SUBMIT**

Best saved checkpoint: R1_101_ckpt_g10040.

- reliability_zero_defects: PASS
- teacher_non_inferiority: FAIL
- reproducible_improvement_over_teacher: FAIL
- no_major_regression: FAIL
- exact_frozen_deck: PASS

The amended gate requires ALL of reliability, teacher non-inferiority, reproducible improvement over the teacher, no major regression, the exact frozen deck, and package validation. Teacher non-inferiority fails (best one-sided LB 0.1875 < 0.47) and major regressions exist, so no already-trained checkpoint qualifies. No retraining was performed. Kaggle upload is SKIPPED_BY_GATE; the frozen teacher (ref 54948560) remains the standing submission.

RL improving over its own initialization is explicitly NOT a submission criterion.
