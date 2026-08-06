# SUBMISSION_F Decision (AC-16)

**SUBMISSION_F = DO_NOT_SUBMIT**

Best agent `S_633_g30176` — teacher 0.33499999999999996, field 0.3666666666666667, teacher LB95 0.29500000000000004.
Frozen teacher same-panel field baseline: **0.545**.

- PASS — best_agent_is_not_the_incumbent
- PASS — reliability_passes
- FAIL — teacher_non_inferiority_lb95_ge_0.47
- FAIL — beats_frozen_teacher_same_panel_field
- FAIL — no_major_regression_vs_teacher
- PASS — uses_exact_frozen_deck
- N/A — package_validation

The gate is not met, so nothing is uploaded and no archive is built. A validated training loop is explicitly not sufficient for submission.
