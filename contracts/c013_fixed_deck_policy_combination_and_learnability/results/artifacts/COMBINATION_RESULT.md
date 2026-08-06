# AC-05 / AC-06 — combination families on the registered panels

**COMBINATION_RESULT = WEIGHT_SOUP_WINS** (winner `SOUP13_SOUP+P1_822`, family `weight_soup`)

Every number below is recomputed from the raw per-game records with bootstrap seed 90210, which is not the seed the evaluator used. The panel summary files are cross-checked against this recount rather than quoted: **0** disagreements found.

## Why the two families are reported separately

A weight soup evaluates ONE network at averaged parameters; an online ensemble evaluates every component and combines their outputs. For a non-linear network these are different functions — `tests/test_c013_ensemble_math.py` demonstrates it numerically — so §2 forbids treating them as interchangeable. All weights are equal and were never tuned after results.

## Final panel — untouched, reports but never selects

| rank | candidate | family | teacher | field | composite |
|---|---|---|---|---|---|
| 1 | SOUP13_SOUP+P1_822 | weight_soup | 0.360 | 0.360 | 0.368 |
| 2 | P0_711 | single | 0.352 | 0.373 | 0.366 |
| 3 | LOGIT_S611+S622 | online_ensemble | 0.336 | 0.360 | 0.357 |
| 4 | PROB_SOUP+P0_711+P1_822+P1_833 | online_ensemble | 0.320 | 0.363 | 0.352 |
| 5 | C012_SOUP_622_633 | weight_soup | 0.320 | 0.354 | 0.345 |

## Q3 gate (§16), read from the **confirmation** panel

`online ensemble must beat EVERY trainable single/soup candidate by >=0.03 teacher gain or >=0.03 strategic-field gain (§16)`

Best trainable single/soup on confirmation: teacher 0.36333333333333334, field 0.3977777777777778. Ensembles evaluated: 22.

| ensemble | teacher | field | teacher gain | field gain | passes |
|---|---|---|---|---|---|
| LOGIT_S611+S622+S633 | 0.347 | 0.344 | -0.017 | -0.053 | False |
| LOGIT_S622+S633 | 0.347 | 0.347 | -0.017 | -0.051 | False |
| LOGIT_SOUP+P0_711+P1_822+P1_833 | 0.347 | 0.391 | -0.017 | -0.007 | False |
| PROB_SOUP+P0_711 | 0.343 | 0.396 | -0.020 | -0.002 | False |
| PROB_SOUP+P0_711+P1_833 | 0.330 | 0.336 | -0.033 | -0.062 | False |
| LOGIT_SOUP+P0_711+P1_833 | 0.323 | 0.381 | -0.040 | -0.017 | False |
| PROB_S622+S633 | 0.323 | 0.353 | -0.040 | -0.044 | False |
| PROB_SOUP+P1_822 | 0.317 | 0.368 | -0.047 | -0.030 | False |
| LOGIT_SOUP+P0_711 | 0.313 | 0.362 | -0.050 | -0.036 | False |
| LOGIT_SOUP+P1_833 | 0.313 | 0.379 | -0.050 | -0.019 | False |
| PROB_SOUP+P1_833 | 0.313 | 0.354 | -0.050 | -0.043 | False |
| LOGIT_S611+S633 | 0.310 | 0.398 | -0.053 | +0.000 | False |
| LOGIT_SOUP+P0_711+P1_822 | 0.310 | 0.387 | -0.053 | -0.011 | False |
| PROB_S611+S622 | 0.307 | 0.368 | -0.057 | -0.030 | False |
| PROB_S611+S633 | 0.307 | 0.320 | -0.057 | -0.078 | False |
| Q2_LOGIT_recombined | 0.307 | 0.344 | -0.057 | -0.053 | False |
| Q2_PROB_recombined | 0.307 | 0.353 | -0.057 | -0.044 | False |
| LOGIT_SOUP+P1_822 | 0.292 | 0.340 | -0.072 | -0.058 | False |
| PROB_S611+S622+S633 | 0.290 | 0.349 | -0.073 | -0.049 | False |
| PROB_SOUP+P0_711+P1_822+P1_833 | 0.290 | 0.391 | -0.073 | -0.007 | False |
| PROB_SOUP+P0_711+P1_822 | 0.273 | 0.356 | -0.090 | -0.042 | False |
| LOGIT_S611+S622 | 0.363 | 0.358 | +0.000 | -0.040 | False |

**GATE = FAIL → Q3 = SKIPPED_BY_GATE**

