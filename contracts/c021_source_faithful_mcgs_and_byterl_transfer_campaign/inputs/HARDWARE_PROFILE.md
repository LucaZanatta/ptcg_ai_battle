# Local Hardware Profile — Scheduling Input Only

Captured 2026-07-28.

- OS: Ubuntu 24.04.4 LTS
- CPU: AMD Ryzen 9 7900X, 12 physical cores / 24 logical CPUs
- RAM: 61 GiB physical, approximately 39 GiB available at capture
- GPU: NVIDIA GeForce RTX 5070, 12,227 MiB total / approximately 11.48 GiB visible to PyTorch
- PyTorch: 2.12.1+cu130, CUDA available
- CUDA toolkit: 13.3
- Storage: root NVMe has approximately 172 GiB free; additional 1.8 TB ext4 volumes exist but may require mounting
- Open-file limit at capture: 1024

## Policy

Use this profile only to schedule workers, batching, storage, and elapsed run time.

It must not justify replacing:

- MCGS graph search with shallow enumeration;
- MCGS rollouts with an invented leaf evaluator;
- modified UCD with PUCT;
- ByteRL recurrent actor–learner with transition replay;
- FIFO with a replay ring;
- V-trace/UPGO with ordinary PPO;
- OSFP with ordinary self-play;
- complete autoregressive actions with first-selection-only training;
- end-to-end deck construction plus battle with a fixed-deck-only reference.

Recommended operational preparation:

- raise `ulimit -n` for actor/search processes when required;
- use a Python 3.11 or 3.12 project environment if dependencies fail under Python 3.13;
- place large checkpoints and logs on a large ext4 data volume when available;
- keep swap inactive during performance-critical runs;
- close unnecessary GPU-heavy desktop applications for long learner runs.
