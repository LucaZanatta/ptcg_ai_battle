# AC-12 — opponent overlap on identical visible states

**OPPONENT_OVERLAP = INCONCLUSIVE**

The decision rule was committed before any number here was computed (`OVERLAP_DECISION_RULE.md`, and `DECISION_RULE` in `tools/c013_overlap_analysis.py`).

## How the states were produced

A shadow-query loop: one acting policy drives a real game and every other policy is queried on the *same* `obs`, its answer recorded and discarded. Each shadow policy keeps a **persistent per-game instance**, because `cg/teachers.py` documents that these rule agents hold turn counters and attack plans that never reset — a fresh instance at a mid-game state would evaluate turn-conditioned branches with counters at zero, and would damage the four rule agents asymmetrically in exactly the contrast §24 turns on.

**Limitation, stated rather than worked around:** the trajectory is the acting policy's. A shadow agent answers *what would you do here*, not *what position would you have reached*. That is inherent to any identical-state comparison.

## Applicability — the measurement that decides the answer

Every agent hard-codes its own deck's card IDs. Handed a state from another deck its specific branches cannot fire and it falls through to its generic skeleton, often to the first legal option. Counting that as agreement would manufacture overlap out of two policies independently defaulting to index 0. A permutation test (4 reorderings, seed 20260726) separates the two: if the chosen *content* is invariant the rules chose it; if the choice follows the index it was positional. The test never reads the agents' source, so it cannot be tuned.

| policy | content-driven | positional | invalid | error | rate |
|---|---|---|---|---|---|
| C012_SOUP_622_633 | 3436 | 591 | 0 | 0 | 0.836 |
| P0_711 | 3400 | 617 | 0 | 0 | 0.827 |
| S611 | 3396 | 603 | 0 | 0 | 0.826 |
| S622 | 3338 | 651 | 0 | 0 | 0.812 |
| S633 | 3448 | 559 | 0 | 0 | 0.839 |
| dragapult | 3102 | 955 | 0 | 0 | 0.755 |
| iono | 1738 | 2372 | 0 | 0 | 0.423 |
| mega_abomasnow | 986 | 3124 | 0 | 0 | 0.240 |
| mega_lucario | 1633 | 2477 | 0 | 0 | 0.397 |

Primary population (teacher **and all three** officials content-driven): **611** of 4110 states. Per-pair-maximal subsets are secondary because teacher–Lucario and teacher–Iono computed on different state populations would differ by subset composition rather than policy similarity.

## Registered measures

| measure | n | teacher–Lucario | teacher–Iono | teacher–Abomasnow | L−I 95% CI | L−A 95% CI | discriminates |
|---|---|---|---|---|---|---|---|
| top1_agreement | 611 | 0.440 | 0.401 | 0.381 | [-0.011, +0.092] | [+0.025, +0.092] | no |
| action_type_agreement | 611 | 0.561 | 0.538 | 0.499 | [-0.016, +0.064] | [+0.028, +0.095] | no |
| set_jaccard | 611 | 0.444 | 0.405 | 0.385 | [-0.011, +0.092] | [+0.025, +0.092] | no |
| target_agreement | 124 | 0.710 | 0.637 | 0.621 | [-0.040, +0.185] | [-0.024, +0.202] | no |
| energy_commitment_agreement | 93 | 0.581 | 0.559 | 0.570 | [-0.108, +0.151] | [-0.129, +0.151] | no |
| attack_pass_timing_agreement | 299 | 0.645 | 0.672 | 0.625 | [-0.080, +0.027] | [-0.007, +0.047] | no |
| promotion_agreement | 98 | 0.622 | 0.429 | 0.622 | [+0.010, +0.367] | [+0.000, +0.000] | no |
| phase_conditioned_top1 | 611 | 0.440 | 0.401 | 0.381 | [-0.011, +0.092] | [+0.025, +0.092] | no |

Discriminating for Lucario: **0/8**; opposite: **0/8**; Lucario highest: **7/8**; computable: 8/8.

## What this shows

Lucario has the highest point estimate on 7 of the 8 measures, so there *is* a consistent directional tendency. But no measure clears the pre-registered bar, which requires the teacher–Lucario advantage to hold over **both** Iono and Abomasnow with a paired 95% CI excluding zero. Against Abomasnow several differences are significant; against Iono none are. The verdict is therefore `INCONCLUSIVE` under the rule as registered, and the rule was not adjusted after these numbers were visible.

The more striking result is one §24 did not ask about: **the three official opponents resemble each other far more than any of them resembles the frozen teacher.** Every opponent–opponent pair agrees on at least 0.514 of primary decisions, while the teacher's closest opponent reaches only 0.435. Mega Lucario and Mega Abomasnow choose **identically on all 98 promotion decisions**, and Iono and Abomasnow agree on 0.871 of energy commitments. So a shared rule skeleton is clearly present among the official sample agents — it simply is not shared with the teacher in the Lucario-specific way the hypothesis predicted.

## §22 final bullet — operationalisation, not a pre-registered set

states arising in games whose opponent seat is Mega Lucario; no such set is registered in c010-c012. n = 193, teacher–Lucario top-1 = 0.409.

## Exact-choice identity between pairs (§23)

Two policies that pick the identical option on every decision of a family share that routine outright — a stronger and more legible statement than a similarity score. Measured on the primary subset.

| pair | all decisions | promotion | energy | attack/pass |
|---|---|---|---|---|
| mega_lucario|mega_abomasnow | 0.763 (n=611) | 1.000 (n=98) | 0.419 (n=93) | 0.676 (n=299) |
| iono|mega_abomasnow | 0.642 (n=611) | 0.010 (n=98) | 0.871 (n=93) | 0.716 (n=299) |
| mega_lucario|iono | 0.514 (n=611) | 0.010 (n=98) | 0.473 (n=93) | 0.525 (n=299) |
| dragapult|mega_lucario | 0.435 (n=611) | 0.622 (n=98) | 0.570 (n=93) | 0.398 (n=299) |
| dragapult|iono | 0.396 (n=611) | 0.357 (n=98) | 0.484 (n=93) | 0.431 (n=299) |
| dragapult|mega_abomasnow | 0.376 (n=611) | 0.622 (n=98) | 0.495 (n=93) | 0.334 (n=299) |

## Behavioural fingerprints (§23)

Jensen–Shannon distance between action-type distributions:

| pair | JS |
|---|---|
| P0_711|S611 | 0.0002 |
| C012_SOUP_622_633|P0_711 | 0.0003 |
| C012_SOUP_622_633|S622 | 0.0004 |
| S611|S633 | 0.0004 |
| C012_SOUP_622_633|S611 | 0.0004 |
| P0_711|S633 | 0.0005 |
| P0_711|S622 | 0.0006 |
| C012_SOUP_622_633|S633 | 0.0007 |
| S611|S622 | 0.0010 |
| S622|S633 | 0.0017 |
| S622|dragapult | 0.0080 |
| iono|mega_abomasnow | 0.0086 |
| C012_SOUP_622_633|dragapult | 0.0096 |
| P0_711|dragapult | 0.0106 |
| S611|dragapult | 0.0108 |
| S633|dragapult | 0.0131 |
| dragapult|mega_lucario | 0.0911 |
| S622|mega_lucario | 0.1092 |
| iono|mega_lucario | 0.1130 |
| C012_SOUP_622_633|mega_lucario | 0.1144 |
| dragapult|iono | 0.1173 |
| P0_711|mega_lucario | 0.1196 |
| S611|mega_lucario | 0.1208 |
| S633|mega_lucario | 0.1210 |
| mega_abomasnow|mega_lucario | 0.1221 |
| dragapult|mega_abomasnow | 0.1311 |
| S622|iono | 0.1383 |
| C012_SOUP_622_633|iono | 0.1393 |
| S611|iono | 0.1421 |
| C012_SOUP_622_633|mega_abomasnow | 0.1445 |
| S622|mega_abomasnow | 0.1447 |
| P0_711|iono | 0.1450 |
| S633|iono | 0.1454 |
| S611|mega_abomasnow | 0.1475 |
| S633|mega_abomasnow | 0.1490 |
| P0_711|mega_abomasnow | 0.1500 |

## Deck composition — context, excluded from the verdict

Shared distinct cards with the frozen Dragapult deck: mega_lucario 3, iono 5, mega_abomasnow 2. This is *deck* similarity; §24 asks about *policy* similarity, so the registered rule excludes it from the verdict.

