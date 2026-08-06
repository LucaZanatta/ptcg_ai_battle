# Clean Checkout & Run (c010)

Reproduce from branch `contract/c010_fixed_deck_rl_loop_v2` (final HEAD `6530fe8b313a026561cce51be6b541796ac5846a`), repo root, `.venv/bin/python`, `OMP_NUM_THREADS=1` (each rollout worker is a separate process; letting BLAS also thread inside every worker oversubscribes the machine and costs ~3x throughput).

Deterministic: dependency/immutability verification, baseline+arm registration and the configuration diff, PPO/environment validation (toy positive control, GAE, masking, initialisation fidelity), identity assertions, all aggregate recomputation from raw games, the content-aware validator, and every decision rule.

Not bit-reproducible: the games themselves (the cabt engine seeds from `std::random_device`), so training trajectories and evaluation point estimates vary between runs; all conclusions are stated with bootstrap intervals and the raw per-game records ship so every aggregate can be recomputed exactly.

Externally provided (gitignored): the cabt SDK + `libcg.so`, `cg` symlinks, kaggle-environments, numpy/scipy, the c005 teacher sources, the c007 V2-A checkpoint and the c008/c009 artifacts. No file under c005-c009 is written; B0 and I0 are read-only.

`results/` is review evidence and is intentionally uncommitted.
