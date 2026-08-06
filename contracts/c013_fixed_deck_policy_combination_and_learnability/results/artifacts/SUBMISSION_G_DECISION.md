# AC-14 — best agent and submission decision

**SUBMISSION_G = DO_NOT_SUBMIT**

- True best agent: `SOUP13_SOUP+P1_822` (weight_soup)
- Package-feasible best agent: `SOUP13_SOUP+P1_822` (weight_soup)

## §31 gate, condition by condition

| condition | required | measured | passes |
|---|---|---|---|
| teacher non-inferiority | one-sided 95% LB ≥ 0.47 | 0.318 | False |
| same-panel strategic improvement over frozen teacher | candidate field > teacher field | 0.360 vs 0.549 | False |
| no major regression | no opponent ≤ incumbent − 0.07 | — | True |
| exact frozen deck | required | yes | True |

## Why no upload happened

The gate is not close. Teacher non-inferiority needs a one-sided 95% lower bound of 0.47; the package-feasible best agent measures 0.318. On the same untouched final panel the frozen teacher scores 0.549 on the strategic field against the candidate's 0.360.

The contract authorises a Kaggle upload **when and only when** `SUBMISSION_G = SUBMIT`. It does not, so nothing was packaged, uploaded, or submitted, and the conditional Kaggle artifacts are deliberately absent rather than stubbed.

## Replacement of the c012 incumbent (§30)

All seven §30 conditions are evaluated; none is assumed.

| condition | passes |
|---|---|
| reliability_passes | yes |
| teacher_score_not_lower | yes |
| strategic_field_not_lower | yes |
| at_least_one_primary_gain_p_gt_0_ge_90pct | yes |
| no_iono_or_abomasnow_major_regression | yes |
| no_major_worst_matchup_regression | yes |
| runtime_package_feasibility_passes | yes |

The condition that decides this is the ≥90% bootstrap probability, and it passes **narrowly**: the teacher gain is +0.040 with P(gain>0) = 0.9044 against a 0.90 threshold, and its 95% CI [-0.020, +0.100] still spans zero. The strategic field gain is +0.006 at P = 0.6012, which is not resolvable at this panel size. `replaces_c012_incumbent` should be read as *the registered condition is met*, not as a comfortable margin.

`SOUP13_SOUP+P1_822` vs `C012_SOUP_622_633` on the final panel: teacher 0.360 vs 0.320, field 0.360 vs 0.354. Replaces incumbent: **True**.

