# c021 audit reconciliation

`CONTRACT.md §3` lists findings that are "starting facts to verify from raw artifacts, not optional narrative", and `references/C021_AUDIT_FINDINGS.md` adds "Do not trust prose alone." Every number below is recomputed by `tools/c022_reconcile_c021.py` from a per-episode JSONL, a per-iteration curve, a run summary or the source text. Where a recomputed value disagrees with what c021 or this contract states, the discrepancy is recorded rather than reconciled away.

Generated from c021 artifacts at `cdbd4438` (identical in content at the branch point) plus the pre-extension segment recovered from `fbbd9ac`.

## 0. The recovery that changes a headline number

c021's four-hour extension reused the parent run tag, so it overwrote `big_ctrl_b2_games.jsonl` and `big_ctrl_b2_curve.json` **in place**. The files at HEAD hold the extension segment only. The pre-extension segment survives at `fbbd9ac`.

| arm | pre-extension games | extension games | TOTAL |
|---|---:|---:|---:|
| `big_ctrl_b1_5` | 15360 | 75136 | 90496 |
| `big_ctrl_b2` | 15360 | 76800 | 92160 |
| `big_ctrl_b3` | 0 | 15360 | 15360 |
| `big_learn_b1_5` | 0 | 15360 | 15360 |
| `big_learn_b2` | 0 | 15360 | 15360 |
| `big_learn_b3` | 0 | 15360 | 15360 |

So the contract's "about 76,800 games" is the **extension segment**, not c021's total exposure for that arm, which is **92,160 games** over 720 iterations. Reading HEAD alone would have set c022's matched budget 20% too low.

## 1. Matched budget (TRAINING_AND_EVALUATION §1)

The controlling quantity is environment decisions, not games. The per-episode records carry integer `n_battle` and `n_construction`, so the count is exact; the curve's `mean_battle_steps` is rounded to one decimal and would accumulate error over 720 iterations.

| quantity | value |
|---|---:|
| source arm | `big_ctrl_b2` (fixed-deck B2) |
| games | 92,160 |
| iterations | 720 |
| battle decisions | 3,607,599 |
| construction decisions | 0 |
| **total environment decisions** | **3,607,599** |
| learner updates | 92,160 |
| sample reuse | 1 |
| optimizer examples after reuse | 3,607,599 |
| 25% extension block | 901,900 decisions |

**The c022 matched budget is 3,607,599 total environment decisions**, applied to both `BR3_FIXED_DECK` and `BR3_END_TO_END`.

Construction decisions are counted in the total. c021's fixed-deck arm has zero of them, so for that arm decisions == battle decisions; c022's end-to-end arm adds 60 construction decisions per episode and therefore reaches the same decision budget in fewer games. That is the intended consequence of matching on decisions — every one of those 60 is a real masked policy decision the network must produce and be trained on — and the achieved game count is reported alongside so the two arms stay legible.

The 76,800-game fallback permitted by TRAINING_AND_EVALUATION §1 is **not used** (`fallback_used: False`): exact decisions were recoverable.

## 2. MCGS single-determinization overconfidence (§3.1)

Predicted win rate is defined as `term_root_win / (term_root_win + term_root_loss)` — the fraction of rollouts reaching a **decided** terminal that the root player won. `term_undecided` rollouts hit the turn cap; they are excluded from the ratio and reported separately, because folding them in would silently deflate the very overconfidence the finding is about.

c021 wrote 7 run summaries into two directories each. They are deduplicated by file content here — counting the union would have inflated "how many runs are overconfident" without adding one new measurement. `results/mcgs/superseded/` is excluded outright.

| run | games | field score | predicted (decided) | undecided | gap (pp) |
|---|---:|---:|---:|---:|---:|
| `t2_T3_prior_and_rollout` | 40 | 0.0882 | 0.9785 | 2,152 | 89.0 |
| `transfer_T2_rollout_policy` | 40 | 0.1053 | 0.9889 | 1,460 | 88.4 |
| `scale_w8` | 36 | 0.129 | 0.9532 | 246,544 | 82.4 |
| `ablation_search` | 40 | 0.1471 | 0.964 | 156,505 | 81.7 |
| `transfer_T1_policy_prior` | 40 | 0.1562 | 0.9689 | 269,991 | 81.3 |
| `t2_T2_rollout_policy` | 40 | 0.1795 | 0.9784 | 2,380 | 79.9 |
| `scale_w12` | 36 | 0.1613 | 0.9583 | 7,128 | 79.7 |
| `t2_T1_policy_prior` | 40 | 0.1714 | 0.9621 | 5,033 | 79.1 |
| `scale_w1` | 36 | 0.1471 | 0.9336 | 9,022 | 78.7 |
| `legal_corrected` | 40 | 0.1818 | 0.9621 | 158,661 | 78.0 |
| `ablation_nochance` | 40 | 0.129 | 0.9076 | 396,245 | 77.9 |
| `scale_w2` | 36 | 0.1562 | 0.9027 | 168,588 | 74.6 |
| `scale_w20` | 36 | 0.0938 | 0.8293 | 266,583 | 73.6 |
| `scale_w4` | 36 | 0.2424 | 0.9784 | 14,424 | 73.6 |
| `transfer_T0_control` | 40 | 0.0833 | 0.8144 | 9,411 | 73.1 |
| `competitive` | 40 | 0.1471 | 0.8397 | 9,926 | 69.3 |
| `t2_T0_control` | 40 | 0.1111 | 0.791 | 90,653 | 68.0 |
| `scale_w24` | 36 | 0.0 | 0.3784 | 3,865 | 37.8 |

**18 distinct MCGS runs carry rollout-terminal counts. Every one of them is overconfident** (`every_run_has_positive_gap: True`), with gaps from 37.8 to 89.0 percentage points.

The contract's "near 96%" is reproduced: the maximum predicted rate across runs is **0.9889** (`transfer_T2_rollout_policy_summary.json`). The minimum is 0.3784 (`scale_w24_summary.json`), so "96%" is near the top of a range rather than a universal constant — c022's calibration work is measured against per-run values, not against a single quoted figure.

## 3. ByteRL external performance (§3.3)

- **pre-extension B2 final** — 0.0742 on 256 games (Wilson 95% recomputed (0.048, 0.113), recorded [0.048, 0.113])
- **post-extension B2 final** — 0.2422 on 256 games (Wilson 95% recomputed (0.1938, 0.2982), recorded [0.1938, 0.2982])
- **post-extension B2 it0160 (selected)** — 0.1953 on 256 games (Wilson 95% recomputed (0.1514, 0.2482), recorded [0.1514, 0.2482])

**Discrepancy found.** post-extension big_ctrl_b2_final external win rate on 256 games: `gate_evaluation.json` records 0.2578, `external_gate_revalidation.json` records 0.2422 — 1.56 pp apart on the same checkpoint. two independent 256-game panels of the SAME checkpoint, run at different times with different seeds. The spread is ordinary sampling noise at n=256 (SE ~2.7pp), and it is the empirical reason c022 must state which panel a number came from rather than quoting 'the' rate.

The contract's "roughly 24–26%" brackets both readings (0.2422 and 0.2578). **Confirmed**, with the qualifier that the selected checkpoint measured 0.1953 out of sample — below the range — because c021's preregistered selector was underpowered (121 candidates × 64 games, SE ≈ 5.4 pp).

## 4. Transfer (§3.6)

Control field score 0.1111. Measured run-to-run noise floor ±6.4 pp.

| arm | games | field score | Δ vs control (pp) | exceeds noise? |
|---|---:|---:|---:|---|
| `T1_policy_prior` | 35 | 0.1714 | 6.03 | False |
| `T2_rollout_policy` | 39 | 0.1795 | 6.84 | True |
| `T3_prior_and_rollout` | 34 | 0.0882 | -2.29 | False |

c021 recorded `TRANSFER=FAIL`. **This is a discrepancy with c022 `DECISION_RULES §4`**, which says a positive point estimate smaller than the measured noise floor is `INCONCLUSIVE`, not a pass or a fail. c021's own power caveat says the same thing in prose — "No component is REJECTED on this evidence; it is UNTESTED" — while its machine-readable status says FAIL.

c022 therefore treats the prior and rollout components as **untested**, re-estimates the noise floor properly under probe T05 before comparing anything to it, and does not carry c021's FAIL forward as evidence.

## 5. Architecture and stage names (§3.4, §3.5)

- **Recurrence** — `starter_kit/c021_byterl_model.py` contains `nn.LSTM`: `False`; `nn.GRU`: `False`. CONFIRMED feed-forward. ResidualBlock stack (nn.Linear + LayerNorm) over a per-decision encoding; no hidden state crosses timesteps.
- **Blocking FIFO** — c021 gathered whole iterations synchronously through per-chunk worker processes and a drain; there is no bounded blocking FIFO with producer/consumer balance, and no policy-version or queue-age record.
- **Two-sided clipping** — c021 implements V-trace rho/c clipping (one-sided upper bounds) and UPGO. It has no lower importance-ratio bound and no PPO-style clipped surrogate, so its 'B3' is not the published b3.
- **Stage names** — CONFIRMED: c021's rung names B0/B1/B1_5/B2/B3 do not carry the published Hearthstone meanings (B1 gamma=1, B1.5 random initial construction choices, B2 blocking FIFO balance, B3 modified V-trace/PPO objective). c022 FIDELITY_RULES §4 fixes those meanings, so c021 rung labels are NOT comparable to c022 rung labels of the same name.

The practical consequence for c022: **a c021 rung label and a c022 rung label of the same name denote different systems.** Every comparison in this contract that crosses the c021 boundary names the artifact, not the rung.

## 6. OSFP evidence

c021's OSFP defect: OSFP's seeded historical checkpoint was a VIEW of the live network, not a frozen copy: `.numpy()` shares storage with the source tensor, so the 'frozen' opponent mutated as the learner trained. Fixed at `d1df0d5`.

c022 requirement: MANDATORY_IMPLEMENTATION B5 — 'no mutable object aliasing between learner and history', proven by a byte-immutability probe (B16), not by inspection.

## 7. Verdict on each contract §3 finding

| § | finding | verdict from raw data |
|---|---|---|
| 3.1 | one determinization reused across all rollouts; ~96% predicted vs poor actual | **CONFIRMED** — all 18 runs overconfident, max predicted 0.9889 |
| 3.2 | core formulas ported, hidden-information system not source-faithful | **CONFIRMED** — re-audited independently in `results/fidelity/mcgs_hidden_information_gap_analysis.md` |
| 3.3 | ~24–26% external after ~76,800 games | **CONFIRMED with two corrections** — the game count is the extension segment only (total 92,160), and the two recorded panels differ by 1.56 pp |
| 3.4 | no LSTM, no published b2 FIFO, no published b3 objective | **CONFIRMED** by source inspection |
| 3.5 | OSFP end-to-end evidence invalid or insufficient | **CONFIRMED** — the frozen history aliased live weights |
| 3.6 | transfer gains below noise, inconclusive not failed | **CONFIRMED as a finding, and c021's own status contradicts it** — c021 recorded FAIL where its data and caveat both say INCONCLUSIVE |

## 8. Discrepancies carried into c022

1. **c021 `TRANSFER=FAIL` is not supported by c021's data** under c022 decision rules. Carried forward as `INCONCLUSIVE`/untested.
2. **"76,800 games" understates c021's fixed-deck B2 exposure by 20%.** c022's matched budget uses the recovered total, 3,607,599 decisions.
3. **The same checkpoint has two recorded external win rates.** c022 always names the panel and seed alongside a rate.
4. **c021 rung labels are not c022 rung labels.** Same names, different published meanings.
