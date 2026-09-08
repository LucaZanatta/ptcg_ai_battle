# c018 results

Status: **PARTIAL**. See `STATUS.md` for the verdict and `../DECISION_RULES.md` for the
rules that were fixed before any result existed.

## Layout

| path | contents |
|---|---|
| `search/` | per-run search summaries: real `search_begin`/`search_step`/release/end counters, sampled successor traces |
| `trajectories/` | trusted real-search decisions (JSONL + feature NPZ) |
| `training/` | distillation and curriculum reports, per-epoch and per-block |
| `rollouts/` | raw per-game and per-update rows from the PPO curriculum |
| `checkpoints/` | torch checkpoints and exported runtime NPZ policies, one snapshot per block |
| `final_panel/` | raw identity-carrying panel games and recomputed aggregates |
| `packages/` | submission archives, manifests, clean-extraction validation |
| `submissions/` | Kaggle upload records and polling snapshots |
| `probes/` | P01–P17, P30, P90, each with probe.json, README, manifests, raw references |
| `artifacts/` | parent resolution, immutability baseline, export round-trip, diagnostics |
| `source/` | bundles, uncompressed inspection copies, milestones M00–M05, hashes, environment |

## Reproduction

```bash
python tools/c018_trajectories.py --games 220 --prefix scaled     # M01
python tools/c018_export_check.py                                 # gate before M03
python tools/c018_distill.py --prefix scaled --epochs 60           # M02
python tools/c018_curriculum.py --blocks 40 --games-per-block 1024 # M03
python tools/c018_diagnostics.py                                   # M04 / P15 / P16
python tools/c018_panel.py --games-per-pair 40                     # P17
python tools/c018_probes.py && python tools/c018_probes_train.py
python tools/c018_validate.py --final                              # P90
python tools/c018_tree.py && python tools/c018_reports.py
```

## Reading the evidence

Start with `artifacts/evidence_validation.json`. It re-derives every search and training claim
from raw rows rather than reading the reports that assert them, and it fails on absence in
`--final` mode so a skipped milestone cannot be counted as a pass.
