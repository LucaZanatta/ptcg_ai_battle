# Clean checkout & run (c011)

Branch `contract/c011_fixed_deck_cuda_ppo_scale`, final HEAD `a3dcdd6456f54717d0b6a5d40d1e659f9b214d35`, repo root, `.venv/bin/python`.

Deterministic: dependency/hardware/immutability verification, the c010 enumeration and incumbent selection, every parity and round-trip test (which pin `torch.use_deterministic_algorithms` and one thread), the content-aware validator, the source-bundle validator, and all decision rules.

Not bit-reproducible: the games themselves (the cabt engine seeds from `std::random_device`), so training trajectories and evaluation point estimates vary between runs. All conclusions are stated with bootstrap intervals and the raw per-game records ship so every aggregate can be recomputed exactly.

Hardware: RTX 5070 (12,227 MiB), Ryzen 9 7900X, 61 GiB. CUDA PyTorch required for FP32_CUDA; a NumPy fallback path exists and is ~2.9x slower end to end.

Externally provided (gitignored): cabt SDK + libcg.so, kaggle-environments, torch, numpy/scipy, the c005 teacher sources, and the c007-c010 artifacts. No file under c005-c010 is written.
