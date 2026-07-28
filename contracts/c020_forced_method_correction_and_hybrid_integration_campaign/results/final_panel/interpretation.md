# Final panel interpretation

## Every candidate, against the frozen baseline

| candidate | field | delta vs baseline (pts) |
|---|---|---|
| C019_PIMC_PUCT_CONTROL | None | None |
| C019_BYTERL_CONTROL | None | None |
| C020_CORRECTED_MCTS | None | None |
| C020_CORRECTED_BYTERL | None | None |
| C020_H0 | None | None |
| C020_H1 | None | None |
| C020_H2 | None | None |
| C020_H3 | None | None |
| C020_H4 | None | None |

## 1. Did corrected MCTS improve over the baseline and over c019 MCTS?

Against the baseline: **did NOT improve** (None points; the gate requires +3).
Against `C019_PIMC_PUCT_CONTROL`: **did NOT improve**
(None versus None).

## 2. Did corrected ByteRL improve over fresh init and over c019 ByteRL?

Against `C019_BYTERL_CONTROL`: **did NOT improve**
(None versus None).

Against its own fresh initialization, measured internally rather than on the panel: the OSFP
promotion history is the record. [{'lp': 0, 'reason': 'FIRST_HISTORICAL', 'add': True}, {'lp': 1, 'reason': 'PERFORMANCE_PROMOTION', 'add': True}, {'lp': 2, 'reason': 'PERFORMANCE_PROMOTION', 'add': True}, {'lp': 3, 'reason': 'PERFORMANCE_PROMOTION', 'add': True}, {'lp': 4, 'reason': 'NO_PROMOTION', 'add': False}, {'lp': 5, 'reason': 'PERFORMANCE_PROMOTION', 'add': True}]

Every promotion is decided from a dedicated frozen-checkpoint evaluation against the historical
population, so "beats its own past" is a measurement here rather than an inference from training
curves.

## 3. Which correction mattered most in each pure branch?

**MCTS — the conservative override gate, and it mattered by NOT firing.** The M09 ablation:

| arm | field | override rate |
|---|---|---|
| ablation_no_veto | 0.3217 | 0.05309 |
| ablation_no_overrides | 0.5583 | 0.0 |
| postrepair_scaled | 0.3038 | 0.06114 |

The corrected machinery with overrides disabled reproduces the baseline. Everything the search
adds — shared information-set statistics across determinizations, four legal worlds per decision,
branch-local baseline memory, an eighteen-feature tactical evaluator over real card metadata — is
neutral until an override executes, and then it is expensive. R1 (the search could not step any
multi-select context) was a genuine correctness defect worth 1,318,265 failed steps, and repairing
it moved the field score by 1.3 points; it was not the binding constraint.

**ByteRL — period-correct OSFP with frozen-checkpoint promotion.** It is the correction that turns
"the loss went down" into a measurement: five promotions and one refusal, each decided from games
played by one frozen checkpoint against a fixed population. c019's accumulate-across-periods
accounting could not have produced that refusal, because the evidence pooled six policies.

## 4. Did H1, H2, H3 or H4 improve over H0 and over the best pure parent?

Better than H0 (None): **none**.
Better than the best corrected pure parent (0): **none**.

Prior admission: False. Value admission: False.
A mode using an unadmitted adapter executes and is reported, but is not promotable.

## 5. Which packages were submitted?

None. No c020 candidate cleared its registered gate. DECISION_RULES forbids uploading a known-weak candidate merely to complete the contract, and CONTRACT §10 forbids substituting an unrelated official agent.

## Reading the numbers honestly

`make("cabt")` exposes no environment seed, so shuffles and coin flips are not paired across
candidates. Differences smaller than the reported Wilson interval are not attributable to the
candidate. Per-candidate intervals are in `confidence_intervals.json` and every number here is
derived from `raw_games.jsonl.gz`, paired by `game_id`.
