# Clean Checkout & Run (c007)

Reproduce from branch `contract/c007_hybrid_teacher_residual_and_state_encoder_v2` (final HEAD `1f3fc63aaa36be0a45ffce8481c563c89ffa0577`), from repo root with `.venv/bin/python` and `OMP_NUM_THREADS=1`.

Deterministic & reproducible: dependency verify, context census, encoder audit + tests, instrumentation parity (replay), experiment registration, v2 dataset rebuild, model training (seed + OMP=1), offline eval, admission, decisions. Not bit-reproducible (engine `random_device`): the games themselves; the statistical conclusions are stable across the large samples and fixed bootstrap seeds.

External (gitignored / provided): the cabt SDK + `libcg.so`, `cg` symlinks, `kaggle-environments==1.30.1`, numpy/scipy, and the c005 `teacher_sources/` + `frozen_teacher/`.

Results package (dataset, checkpoints, games, reports, Kaggle evidence) is review evidence and is not committed; only c007 source is on the branch.
