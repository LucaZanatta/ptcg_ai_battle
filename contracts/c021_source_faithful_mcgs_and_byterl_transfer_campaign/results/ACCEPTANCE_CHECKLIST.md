# Acceptance checklist

| # | Requirement | Met | Evidence |
|---|---|---|---|
| A1 | official 2019 archive retrieved and hashed | yes | fidelity/mcgs_official_source_inventory.json |
| A2 | state/action abstraction with the source's hash combiner | yes | c021_mcgs_abstraction.py; test_source_constants_match_the_shipped_config |
| A3 | non-root selection, expansion, rollout, backup | yes | c021_mcgs.py; EXECUTION counters |
| A4 | chance nodes with damped sampling and sample merging | yes | fidelity/A4_chance_node_api_constraint.md; MCGS_A4_COIN_NEVER_UCB_SELECTED |
| A5 | graph reuse / re-rooting across atomic decisions | yes | graph_reuse_reroots > 0; statistics keyed by abstraction survive each decision, since the API invalidates engine states at search_end |
| A6 | category filters and obliged actions | yes | c021_mcgs_legal.py (A10 branch): the source's Hearthstone card-ID sets do not transfer, so the filter is rebuilt structurally from SelectContext valence and playerIndex |
| A7 | uniform-random rollout to a real terminal, no leaf evaluator | yes | c021_mcgs.py::_play_until_terminal |
| A8 | transposition DAG with dummy edges and sample merging | yes | transposition_merges / dummy_edges counters; MCGS_DUMMY_EDGE_LOSES_TO_TWIN |
| A9 | known-defect reproduction test | yes | tools/c021_validate.py — 17/17 detect their injected defect |
| A10 | separately named legality-corrected branch | yes | c021_mcgs_legal.py; mcgs/legal_corrected/change_manifest.json |
| B1 | ByteRL from fresh random weights | yes | BYTERL_FRESH_RANDOM_WEIGHTS |
| B2 | end-to-end deck construction plus battle | yes | byterl/meta_environment/deck_construction.json |
| B3 | cumulative B0->B3 ladder | yes | byterl/stages/*; fidelity/BYTERL_STAGE_LEDGER.md |
| B4 | autoregressive masked multi-select | yes | BYTERL_AUTOREGRESSIVE_MULTISELECT |
| B5 | V-trace and UPGO against exact numerical probes | yes | byterl/numerical_fixtures/objective_probes.json |
| B6 | OSFP with period-local payoffs and immutable history | yes | BYTERL_OSFP_PERIOD_LOCAL; byterl/osfp/promotion_history.jsonl |
| B7 | recurrent actor-learner execution | **no** | NOT MET — synchronous execution; declared deviation, BYTERL_METHOD=PARTIAL |
| T | one-at-a-time transfer, no uncontrolled hybrid | yes | transfer/registered_hypotheses.json |
| R | mandated results tree | yes | tools/c021_finalize.py |

Unmet items are listed rather than omitted. B7 is the single named requirement not met, and it is the reason `BYTERL_METHOD` is PARTIAL rather than PASS.

