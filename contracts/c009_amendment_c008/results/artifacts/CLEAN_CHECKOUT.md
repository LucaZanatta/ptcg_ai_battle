# Clean Checkout & Run (c009)

Reproduce from branch `contract/c009_amendment_c008` (final HEAD `e868dfbbeefc30bcf246cd60e0f51bf6d0043eb8`), repo root, `.venv/bin/python`.

Deterministic: dependency/immutability verification, the c008 defect reproduction (synthetic + forensic), the identity-safe evaluator's assertions, the registry, all aggregate recomputation from raw games, the content-aware validator, and the decisions. Not bit-reproducible: the evaluation games themselves (the cabt engine seeds from `std::random_device`), so point estimates move by sampling noise between runs; every conclusion here is stated with bootstrap intervals over 4,100 recorded games and the raw records are shipped so any aggregate can be recomputed exactly.

Externally provided (gitignored): the cabt SDK + `libcg.so`, the `cg` symlinks, `kaggle-environments`, numpy/scipy, the c005 teacher sources, the c007 V2-A checkpoint and the c008 checkpoints/artifacts. No training is performed and no checkpoint is written.

`results/` is review evidence and is intentionally uncommitted.
