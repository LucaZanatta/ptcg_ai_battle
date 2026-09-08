# Forced change map — every mandatory correction to concrete code

Each row maps a `MANDATORY_CHANGES.md` item to the c019 defect it corrects
(`references/C019_AUDIT_FINDINGS.md`), the c020 file and symbol that implements it, the probe that
proves it at runtime, and the validator check that rejects the c019 behaviour. Status is updated
as implementation lands.

`FAILED_IMPLEMENTATION` is the only permitted alternative to implementing an item.

## A — Corrected information-set MCTS

| id | c019 defect | c020 file / symbol | probe | validator check |
|---|---|---|---|---|
| A1 | #1 one independent tree per determinization, root-only aggregation | `cg/c020_infoset.py` — `InfoSetKey`, `SharedActionStats`, `SharedInfoSetStats`, `InfoSetTable` | M01, M02, M03 | `shared_stats_not_per_determinization` |
| A2 | c019 wrapper adequate but not deep-copyable per branch | `cg/c020_baseline_memory.py` — `BaselineMemory`, `recommend`, `advance_after_executed`, `clone_memory` | M04 | `no_mutable_globals_in_branch` |
| A3 | #1 root-only branching | `cg/c020_ismcts.py` — `_expand`, `_credible_actions` | M05 | `nonroot_expansion_observed` |
| A4 | — (c019 PUCT mechanics were real; perspective must stay correct) | `cg/c020_ismcts.py` — `select_puct`, `backup` | M05 | `backup_is_root_perspective` |
| A5 | #4 option-zero / static continuation | `cg/c020_ismcts.py` — `_rollout` | M05, M07 | `rollout_is_baseline_guided` |
| A6 | #2, #3 shallow 4-feature objective | `cg/c020_tactical_leaf.py` — `LeafFeatures`, `evaluate`, `WEIGHTS` | M06, M07 | `leaf_has_tactical_features` |
| A7 | #5 silent Dragapult default | `cg/c020_determinize.py` — `ARCHETYPE_PRIOR`, `sample_archetype` | M08 | `unknown_archetype_is_a_mixture` |
| A8 | #4, #6 unsafe overrides | `cg/c020_override.py` — `OverrideDecision`, `decide_override` | M07, M09 | `override_gate_is_conservative` |

## B — Corrected ByteRL / OSFP

| id | c019 defect | c020 file / symbol | probe | validator check |
|---|---|---|---|---|
| B1 | #7 active/bench pooled | `cg/c020_byterl_encode.py` — `encode`, `BOARD_SLOTS`, slot position ids | B01 | `board_slots_not_pooled` |
| B2 | #8 missing energy type / status / tool / target refs | `cg/c020_byterl_encode.py` — `OptionRef`, `encode_options` | B02, B03, B04 | `option_carries_source_and_target` |
| B3 | #9 only first pick stored/trained | `cg/c020_byterl_model.py` — `select_autoregressive`; `cg/c020_byterl_actor.py` — `MultiSelectRecord` | B05 | `multiselect_stores_full_joint` |
| B4 | #10 learner reset state at mid-game unrolls | `cg/c020_byterl_actor.py` — `Unroll(h0, c0, episode_start)`; `tools/c020_byterl_train.py` learner replay | B06, B07 | `learner_replays_from_stored_state` |
| B5 | #11 ratios compared across different recurrent contexts | `cg/c020_vtrace.py` — `vtrace`, `upgo`, joint-logp ratios | B08, B09 | `rho_uses_joint_logp_same_state` |
| B6 | #12, #13 G/C accumulated across periods; promotion not frozen-checkpoint | `cg/c020_osfp.py` — `PeriodLocalPayoff`, `evaluate_frozen_checkpoint`, `decide_promotion` | B11, B12 | `osfp_gc_resets_each_period` |
| B7 | #12 mixture not payoff-derived | `cg/c020_osfp.py` — `HistoricalPopulation`, `mixture_from_payoff` | B12, B13 | `historical_hashes_immutable` |
| B8 | — fresh weights mandated by §2 | `tools/c020_byterl_train.py` — `FRESH_RANDOM` init | B10, B14 | `no_c019_weight_load` |

## C — Mandatory corrected hybrid

| id | c019 defect | c020 file / symbol | probe | validator check |
|---|---|---|---|---|
| C1 | #14 `state=None` at every search node | `cg/c020_hybrid.py` — `HybridNodeState`, `advance_neural` | H01 | `no_state_none_at_nonroot` |
| C2 | #15 modes never enumerated | `cg/c020_hybrid.py` — `MODES` H0–H4; `results/hybrid/configs/H*.json` | H06 | `all_five_modes_present` |
| C3 | #15 priors admitted without alignment evidence | `cg/c020_hybrid.py` — `prior_admission` | H02, H04 | `prior_admission_runs` |
| C4 | #15 value not rigorously admitted | `cg/c020_hybrid.py` — `value_admission` | H03, H05 | `value_admission_has_four_controls` |
| C5 | — comparison discipline | `tools/c020_panel.py` — identical budgets/seeds per contrast | H04, H05 | `ablation_uses_identical_budget` |

## Cross-cutting — validator

c019 defect #16 (validator passed despite semantic defects) and #17 (names/file existence are not
evidence) are corrected by `tools/c020_validate.py`, which **injects** each c019 defect as a live
fixture and requires the corresponding check to reject it. A check that cannot be made to fail is
not evidence, so every semantic check ships with its own negative control (probe F05).

## Explicitly retained, not corrected

`C019_PIMC_PUCT_CONTROL` keeps the separate-tree PIMC path deliberately (`MANDATORY_CHANGES A1`
last line). It is labelled PIMC-like rather than ISMCTS in `controls/control_manifest.json`, since
`CONTRACT §5` permits the `ISMCTS` label only when determinizations share information-set
statistics.
