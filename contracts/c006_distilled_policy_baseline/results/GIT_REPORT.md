# c006 — Git Report

- **Branch**: `contract/c006_distilled_policy_baseline` (created from accepted c005 final HEAD).
- **Initial HEAD (c005 final)**: `4137d983c6a05c0eea8332718d3e7f3acc7b7830`
- **Final HEAD**: `08ebac88385444a69d0615b7976dea9dbddeb79a`

## Implementation commits (all prefixed `c006:`)
```
b970f88 c006: add c005 dependency/freeze verification tool
476b453 c006: add ordered sequence dataset rebuild and stateless ambiguity analysis
ae43c98 c006: add card vocabulary, decision taxonomy, and action decoders
fb728ed c006: add numpy autograd, shared featurizer, and S1/S2 policy models
641f2a5 c006: add experiment registration and reproducible training harness
35ba071 c006: add runtime student agent, gameplay harness, offline+gameplay eval
2c920b6 c006: add strategic-gauntlet analysis (ranking, BT, worst, regression)
08ebac8 c006: add submission-B packaging and decision artifacts
```

## Compliance
- Only c006 **source** is committed (25 files, `starter_kit/*.py`, `tools/*.py`,
  `tests/test_c006_models.py`) — see `artifacts/c006.patch` and `artifacts/source_snapshot/`.
- **0** files under `contracts/c005_teacher_import_submission_and_dataset/` modified or
  committed; the frozen teacher/deck and all earlier contract results are untouched
  (c005 hashes re-verified in `artifacts/c005_dependency_verification.json`).
- **0** `.so` files committed (`libcg.so` is gitignored; never staged).
- Pre-existing untracked work (`tmp.txt`, `check.py`, `cg`, `starter_kit/` runtime assets,
  `pokemon-tcg-ai-battle-challenge-strategy/`) left untracked and untouched.
- The `results/` package (reports, datasets, checkpoints, game captures, archives,
  Kaggle evidence) is review evidence and is **intentionally uncommitted**.
- No push / force-push / rebase / amend. No credentials committed or exposed.

See `test_logs/final_git_status.txt` for the captured status/log.
