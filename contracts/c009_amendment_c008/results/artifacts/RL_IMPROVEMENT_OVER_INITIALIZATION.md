# RL Improvement Over Initialization (AC-10)

**RL_IMPROVED_OVER_INITIALIZATION = YES**

c008 never evaluated the untouched c007 V2-A initialization, so it could not tell whether RL improved anything. c009 evaluates it (B0) under the identical protocol.

| candidate | teacher score | vs B0 (P) | strategic field | vs B0 (P) | beats B0 (§11.2) |
|---|---|---|---|---|---|
| **B0_v2a** (untouched V2-A) | 0.16 | — | 0.1525 | — | reference |
| R1_101 | 0.220 | +0.060 (P=0.98) | 0.255 | +0.103 (P=1.00) | **YES** |
| R2_303 | 0.158 | -0.003 (P=0.44) | 0.228 | +0.075 (P=1.00) | no |
| R2_101 | 0.160 | +0.000 (P=0.49) | 0.185 | +0.033 (P=0.89) | no |
| R0_202 | 0.030 | -0.130 (P=0.00) | 0.100 | -0.052 (P=0.01) | no |

### R1_101 satisfies every §11.2 criterion
- teacher_score_exceeds_b0: True
- strategic_field_not_lower: True
- one_difference_90pct_above_zero: True
- no_major_regression_vs_b0: True

Teacher score 0.160 → 0.220 (90% CI on the difference [0.013, 0.105]); strategic field 0.152 → 0.255 (90% CI [0.06, 0.148]).

**This is improvement over the initialization, NOT over the teacher.** The frozen teacher scores 0.570 on the same field; the best RL checkpoint scores 0.255 and is not teacher-non-inferior.
