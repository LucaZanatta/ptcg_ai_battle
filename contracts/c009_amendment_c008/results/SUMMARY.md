# c009 — Amendment to c008: Evaluation Repair and RL Evidence Recalibration

**Status: PASS (16/16 acceptance criteria; content-aware validator 39/39).** The c008
evaluation defect is reproduced, the corrupted artifacts are enumerated, and every strategic
conclusion is re-derived from 4,100 identity-safe games. No policy was trained, no checkpoint
was altered, and the frozen deck was used for every game.

## Decisions
```
C008_EVALUATION                 = REPAIRED
RL_IMPROVED_OVER_INITIALIZATION = YES
BEST_SAVED_CHECKPOINT           = R1_101_ckpt_g10040
TEACHER_NONINFERIORITY          = FAIL
RL_FEASIBILITY_RECALIBRATED     = INCONCLUSIVE
SUBMISSION_D_AMENDED            = DO_NOT_SUBMIT
PROMOTION_DECISION              = NO_RL_SUBMISSION
NEXT_STEP                       = FIXED_DECK_SELECTIVE_SEARCH
```

## 1. c008 defects reproduced

`tools/c008_final_eval.py::strategic()` collected results with `imap_unordered` (completion
order) and then re-attached the policy-arm label by positional `zip`. Reproduced three ways:

| line of evidence | result |
|---|---|
| deterministic synthetic permutation (boundary-crossing) | 12/160 mislabeled by the c008 pattern, 0 by the c009 protocol |
| real spawn `imap_unordered` + deterministic delays | 24/80 (30%) mislabeled, 0 by the c009 protocol |
| forensic on the shipped c008 raw games | 8 of 20 `(arm,opponent)` cells have impossible counts (77/78/82/83 instead of 80); ≥10 games provably mislabeled; the same cells are seat-imbalanced |

Corruption is concentrated at arm-block boundaries (`mega_lucario` first, `__control__` last in
each 400-job block) — reordering must cross a block boundary to mislabel. Opponent and seat were
returned by the worker and are sound; only arm attribution was corrupt.

## 2. c008 artifacts invalidated

`rl_strategic_games.jsonl.gz` (arm field), `rl_matchup_matrix.csv`, `rl_global_ranking.json`,
`rl_holdout_report.json`, `rl_improvement_report.json`, `rl_regression_report.json`, and the
strategic/held-out/regression/best-arm sections of `rl_arm_selection.json`, `RL_FEASIBILITY.md`
and the c008 summary. **Not** affected: the teacher head-to-head and reliability artifacts (each
candidate ran in its own pool call with worker-returned fields) and all training evidence.
Details and the additional §2.2–§2.4 defects are in `artifacts/c008_invalid_artifacts.md`.

## 3. Candidate checkpoints (frozen registry, all hashed)

9 entries: **B0_v2a** (untouched c007 V2-A, `7066841e3329…`), the frozen teacher reference
(`ef8936859fd2…`), and all seven c008 validation-selected checkpoints — R0 101/202, R1 101/202,
R2 101/202/303. c008 designated the **median** seed as each arm's representative while its final
evaluation used the **best-by-validation** checkpoint; c009 removes the ambiguity by evaluating
every selected checkpoint.

## 4. Corrected results (4,100 games, 0 defects, seat-balanced, identity-asserted)

### Teacher head-to-head (Phase A+B, frozen teacher only, rule unchanged at LB ≥ 0.47)

| candidate | point | one-sided LB95 | n | non-inferior |
|---|---|---|---|---|
| **R1_101** | **0.220** | 0.1875 | 400 | no |
| R1_202 | 0.170 | 0.1100 | 100 | no |
| **B0_v2a** (untouched init) | **0.160** | 0.1300 | 400 | no |
| R2_101 | 0.160 | 0.1000 | 100 | no |
| R2_303 | 0.158 | 0.1275 | 400 | no |
| R2_202 | 0.120 | 0.0700 | 100 | no |
| R0_202 | 0.030 | 0.0100 | 100 | no |
| R0_101 | 0.010 | 0.0000 | 100 | no |

### Corrected strategic field (Phase C, 100 games per cell)

| arm | Mega Lucario | Iono | **Abomasnow (held-out)** | Dragapult mirror | field |
|---|---|---|---|---|---|
| T (frozen teacher) | 0.490 | 0.680 | **0.560** | 0.550 | **0.570** |
| R1_101 | 0.360 | 0.240 | **0.270** | 0.150 | 0.255 |
| R2_303 | 0.320 | 0.200 | **0.150** | 0.240 | 0.228 |
| R2_101 | 0.260 | 0.190 | **0.160** | 0.130 | 0.185 |
| B0_v2a | 0.170 | 0.170 | **0.120** | 0.150 | 0.152 |
| R0_202 | 0.300 | 0.010 | **0.070** | 0.020 | 0.100 |

Corrected best within arm (§11.1): **R1 → R1_101**, **R2 → R2_303** (teacher scores were
statistically tied with R2_101, broken on strategic field per §11.1 #2 — a supplementary
identity-safe batch was run so the tie-break used evidence rather than a sample-size artifact),
**R0 → R0_202**.

## 5. RL improvement over initialization — the question c008 never asked

**RL_IMPROVED_OVER_INITIALIZATION = YES**, via R1_101, which satisfies all four §11.2 criteria:

- teacher score **0.160 → 0.220** (difference 90% CI [0.013, 0.105], P(better) = 0.98)
- strategic field **0.152 → 0.255** (difference 90% CI [0.060, 0.148], P(better) = 1.00)
- no major regression versus B0

R2 (the c008 primary hypothesis) improved on the strategic field (0.152 → 0.228, P = 1.00) but
its teacher score is statistically indistinguishable from B0 (0.158 vs 0.160, P = 0.44), so it
fails the §11.2 rule. The evaluated R0 checkpoints (random init) are materially **worse** than B0
on both dimensions — supervised initialization is what makes this RL setup viable at all.

**This is improvement over the initialization, not over the teacher.** The teacher scores 0.570
on the same field against the best RL checkpoint's 0.255.

## 6. Teacher non-inferiority, improvement, regressions

No candidate is teacher-non-inferior: the best one-sided 95% LB is **0.1875** against the
unchanged 0.47 requirement. No candidate shows a reproducible improvement over the teacher
(no global improvement; no +5pp matchup at ≥90%). Among the five candidates that received
strategic games, major regressions versus the teacher exist for all of them: R1_101 on iono,
Abomasnow and the mirror; B0_v2a, R0_202, R2_101 and R2_303 on all four. (R1_202 and R2_202 were
screened against the teacher only and received no strategic games, so no regression claim is made
about them.)

## 7. Submission, Kaggle, promotion

`SUBMISSION_D_AMENDED = DO_NOT_SUBMIT` — the amended gate needs reliability **and** teacher
non-inferiority **and** reproducible improvement over the teacher **and** no major regression;
non-inferiority and improvement both fail. No archive was built (correctly absent).
**KAGGLE_UPLOAD = SKIPPED_BY_GATE**, no credentials exposed. Teacher submission `54948560`
refreshed read-only in the same run: **709.1** (read from the `publicScore` column by index).
`PROMOTION_DECISION = NO_RL_SUBMISSION` — the frozen teacher remains the standing submission.

## 8. Recalibrated feasibility and next step

`RL_FEASIBILITY_RECALIBRATED = INCONCLUSIVE` (§14): a saved RL checkpoint clearly improves over
B0 but remains below the teacher.

`NEXT_STEP = FIXED_DECK_SELECTIVE_SEARCH`. §15's REDESIGN conditions (a) improves over B0,
(b) ≥2 seeds show the signal, and (d) one clear addressable blocker are met, but (c) "best
checkpoint not catastrophically below teacher" fails under the pre-stated criterion (teacher
score < 0.25 **and** major regressions on a majority of field matchups: R1_101 scores 0.220 with
3/4). Independently, §15's expected-value clause points the same way: c008 spent 95,666 training
games to move the teacher score 0.160 → 0.220, leaving 0.25 to the 0.47 bound — about four times
the total gain achieved so far.

**Highest-leverage blocker (exactly one):** sparse terminal-reward credit assignment cannot close
the teacher gap at the measured learning rate; teacher-anchored PPO on the fixed deck improves
its own initialization but is the wrong instrument for closing a >2× strength gap.

**Most valuable algorithmic finding for anyone revisiting RL:** c008 registered a replay decay to
0.05 and a reference-KL decay to 0.01, but every R2 seed early-stopped at 10k–20k of its 50k
budget, so the replay coefficient never fell below ~0.27 and the KL never below ~0.030. **R2
spent its entire life in the high-anchor regime**, which is consistent with its teacher score
sitting on top of B0's. R2's result is therefore a budget/schedule artifact, not proof that
anchoring cannot work (§2.5).

## 9. Evidence integrity

The content-aware validator runs **39 checks** and recomputes every aggregate from raw games with
a bootstrap seed different from the aggregator's; all pass. Fourteen tests prove it is not
existence-based: a pristine copy passes while 13 distinct corruptions — tampered scores, counts
and non-inferiority flags, dropped/duplicated/mislabeled games, a wrong checkpoint hash, an
unjustified SUBMIT, a stray archive — are each detected. Identity is enforced by 9 assertions on
every batch (17 further tests cover reordering, including direct rejection of the c008
positional-zip pattern).

**Immutability:** c005–c008 re-hashed and unchanged; no checkpoint created or modified; 2 `c009:`
source-only commits covering all 13 c009 source files (matching `c009.patch` and
`source_snapshot/`); no `tools/c008_*` modified; no `.so`; no credentials.

## 10. Known limitations

- Evaluation games are engine `random_device`-seeded and not bit-reproducible; conclusions are
  stated with bootstrap intervals over the 4,100 recorded games, and the raw records ship so any
  aggregate can be recomputed exactly.
- Strategic cells hold 100 games; differences below roughly 10 percentage points are inside noise.
- R2's conclusion is limited by the anchor-schedule finding above; additionally the reference KL
  anchored to V2-A rather than to the rule teacher, the replay term was strong relative to PPO,
  and the multi-select reference KL covered only the first sub-selection.
- No retraining was permitted, so only already-saved checkpoints could be assessed.
