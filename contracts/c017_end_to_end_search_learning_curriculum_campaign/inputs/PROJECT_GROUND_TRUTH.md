# Project ground truth for c017

## Strategic state

- c005–c013 established a working simulator, package pipeline, evaluation infrastructure, and custom CUDA PPO stack, but the frozen Dragapult/teacher-centric path did not reach winning strength.
- c014 submitted a shallow custom Archaludon agent and demonstrated rapid package/submission execution, but the agent was weak.
- c015 submitted a custom Iono anti-meta agent whose thesis was falsified and whose reporting contained integrity defects.
- c016 faithfully reproduced exact official agents and found official Mega Lucario to be the strongest practical candidate: approximately 52% versus Dragapult and 61.42% across the official-sample field on confirmation, with zero reliability violations. c016 did not upload it because of poor proxy gates; that no-upload decision is not carried forward.
- c016 final status is PARTIAL. The expected final HEAD is eefc06aa9d7583e45a58836ce836ac9da0d8c252.

## Frozen c017 baseline

Candidate: `official_mega_lucario`

- source hash: `ab8563b67b88b3666c2ff9c308505085a84fdac676c194c5b484d8544478c3b2`
- deck hash: `406e2e9bd6ae82b8008b16ee64ffcbb58e4a50cd6bc36e33ae655456c6b9afee`
- fidelity: EXACT
- c016 permission class: SUBMISSION_REUSE_ALLOWED
- role: external calibration baseline, deterministic fallback, curriculum anchor

Reverify every fact from raw c016 artifacts before use.

## Hardware

- Ubuntu 24.04
- Ryzen 9 7900X, 12C/24T
- 61 GiB RAM
- RTX 5070, roughly 12 GiB VRAM
- custom PyTorch/CUDA PPO previously reached approximately 39,000 training games/hour
- CPU simulator throughput is usually the bottleneck

## User workflow

- Claude Code executes contracts.
- ChatGPT and user make strategic decisions.
- Earlier contracts are immutable.
- Automatic Kaggle upload is authorized when the contract requires it.
- Results must contain complete source and raw evidence so ChatGPT can audit/debug the implementation.
