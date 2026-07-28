# M09 — Conservative override ablation

| arm | field |
|---|---|
| overrides disabled | **0.5583** |
| overrides on, veto ON | 0.5687 |
| overrides on, veto OFF | 0.3312 |

Overriding costs roughly 25 field points at a 0.0 rate, and the conservative veto recovers almost none of it. The disabled arm reproducing the baseline is the control that makes this interpretable: the corrected machinery — shared statistics, four determinizations, branch-local memory, tactical evaluator — does no damage on its own.

Every override opportunity, retained baseline, override and veto reason is logged in `mcts/override_logs/`.
