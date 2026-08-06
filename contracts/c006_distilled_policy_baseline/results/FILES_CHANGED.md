# c006 — Files Changed

## Committed source (25 files, on branch `contract/c006_distilled_policy_baseline`)

### `starter_kit/` (runtime + library modules; importable as `cg.*`)
- `micrograd.py` — batched numpy reverse-mode autograd (gradient-checked).
- `card_vocab.py` — full 1,267-legal-card vocabulary + 52 structured features.
- `obs_norm.py` — documented observation normalization for ambiguity analysis.
- `decision_taxonomy.py` — FORCED/ROUTINE/TACTICAL/HIGH_IMPACT + semantic typing.
- `decoders.py` — single / fixed-k / variable-cardinality (ordered→safe-fallback).
- `policy_features.py` — the ONE featurizer (dataset + runtime), option→card resolution.
- `policy_model.py` — S1 stateless + S2 recurrent (GRU) scorers; numpy inference; policy loss.
- `policy_data.py` — featurize/collate + form-aware labels + agreement evaluator.
- `student_agent.py` — safety-wrapped cabt runtime agent (forced bypass, fallback, per-game reset).
- `control_agent.py` — deterministic engineering control on the frozen deck.
- `gameplay.py` — parallel (spawn) cabt game runner + per-seat reliability/latency/fallback.
- `noninf_stats.py` — one-sided 95% lower-bound non-inferiority statistic.

### `tools/`
- `c006_verify_deps.py` — AC-01 dependency/freeze verification.
- `build_sequence_dataset.py` — AC-02 ordered rebuild (no game regeneration).
- `stateless_ambiguity.py` — AC-03 exact/near aliasing on train+val.
- `c006_build_vocab.py` — AC-04 vocabulary build + validation.
- `c006_taxonomy_decoders.py` — AC-05 taxonomy/samples/decoder coverage + checks.
- `c006_register_experiment.py` — §6 experiment registration (pre-training freeze).
- `train_student.py` — AC-06 registered reproducible training (Adam, early stopping).
- `offline_eval.py` — AC-07 frozen test evaluation + memory ablation.
- `c006_gameplay.py` — AC-08/09/10 smoke, non-inferiority, gauntlet.
- `analyze_student_gauntlet.py` — AC-10 ranking / BT / worst / regression from captures.
- `build_submission_b.py` — §16/AC-12 package build + extracted-archive validation.
- `c006_decide.py` — AC-11/12/13 registered gate decisions + Kaggle-skip artifacts.

### `tests/`
- `test_c006_models.py` — autograd + full S1/S2 gradient checks, forward parity, param
  bounds, decoder legality, checkpoint round-trip (9 tests, all pass).

## Not committed (review evidence under `results/`)
- `artifacts/` reports, `sequence_dataset/`, `checkpoints/` (S1/S2 × 3 seeds + selected),
  game captures (`*.jsonl.gz`), diagnostic archive
  (`submission_B_student_NOT_FOR_SUBMISSION.tar.gz`), Kaggle evidence, decisions.
- `artifacts/source_snapshot/` — copies of the 25 committed source files.
- `artifacts/c006.patch` — full diff vs c005 final HEAD.

## Not modified
- Anything under `contracts/c005_teacher_import_submission_and_dataset/` (frozen teacher,
  deck, dataset, earlier results) — read-only.
