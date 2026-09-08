# c019 Contract Package — Dual Method Campaign

## Purpose

Implement and evaluate two independent, method-faithful PTCG agents:

1. **PTCG-ISMCTS** — a clean-room PTCG adaptation of Hearthstone-style imperfect-information Monte Carlo Tree Search.
2. **PTCG-ByteRL** — a clean-room PTCG adaptation of the ByteRL end-to-end recurrent policy, V-trace/UPGO learner, and Optimistic Smooth Fictitious Play.

The existing c018 pipeline remains the shared simulator/evaluation/package/evidence harness. It is **not** a third competing research program. Only small switchable adapters may connect proven MCTS or ByteRL blocks into that pipeline.

## Run

Extract at repository root, read every file in this directory, then run `CLAUDE_COMMAND.txt`.

## Authoritative files

- `CONTRACT.md` — complete execution mandate.
- `METHOD_FIDELITY.md` — properties required before a branch may be called MCTS or ByteRL.
- `IMPLEMENTATION_GUIDE.md` — implementation sketches and PTCG adaptations.
- `PROBE_MATRIX.md` — runtime and numerical diagnostics.
- `DECISION_RULES.md` — promotion, submission, and kill decisions.
- `RESULTS_SCHEMA.md` — mandatory code and evidence bundle.
- `references/` — primary sources and reuse constraints.
- `inputs/` — fixed user decisions and c018 ground truth.
