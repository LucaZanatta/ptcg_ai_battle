# c008 artifacts and conclusions invalidated by the identity defect (AC-02)

## The defect

`tools/c008_final_eval.py :: strategic()` collected results with
`multiprocessing.Pool.imap_unordered` (which yields **completion** order) and then assigned
the policy-arm label by **position**:

```python
res = _run([...], nproc)                 # imap_unordered -> completion order
for j, r in zip(jobs, res):
    r["arm"] = j["arm"]                  # positional reattachment -> wrong identity
```

The c008 source comment on that line (*"attach arm label (imap loses it otherwise)"*) shows
the label was known to be lost and was then re-attached by the one mechanism that is invalid
under unordered completion. Opponent and seat were returned by the worker and are therefore
sound; **only the arm attribution is corrupt**.

## Reproduction (three independent lines)

| line | result |
|---|---|
| deterministic synthetic permutation (boundary-crossing) | 12/160 games mislabeled by the c008 pattern; 0 by the c009 protocol |
| real spawn `imap_unordered` + deterministic delays | 24/80 (30%) mislabeled by the c008 pattern; 0 by the c009 protocol |
| forensic analysis of the shipped c008 raw games | 8 of 20 `(arm, opponent)` cells have impossible counts; ≥10 games provably mislabeled |

Reordering must **cross an arm-block boundary** to mislabel. c008 submitted jobs arm-major
(4 arms × 400 contiguous jobs), so corruption concentrates at the boundaries — which is
exactly the observed signature.

## Forensic detail

Every `(arm, opponent)` cell must contain exactly 80 games (40 per seat × 2 seats). Observed:

| cell | count | seats (0/1) |
|---|---|---|
| teacher \| mega_lucario | **83** | 43/40 |
| teacher \| __control__ | **77** | 40/37 |
| R0 \| mega_lucario | **77** | 37/40 |
| R0 \| __control__ | **83** | 40/43 |
| R1 \| mega_lucario | **82** | 42/40 |
| R1 \| __control__ | **78** | 40/38 |
| R2 \| mega_lucario | **78** | 38/40 |
| R2 \| __control__ | **82** | 40/42 |

All other cells (iono, mega_abomasnow, dragapult) are exactly 80/40/40. The affected cells
are precisely the first opponent (`mega_lucario`) and last opponent (`__control__`) of each
arm block. The mislabeled games also **break seat balance** in those cells, so their
seat-balanced scores are computed over unequal seat counts — a second, independent error.

## Artifacts INVALIDATED (must not be relied on)

- `rl_strategic_games.jsonl.gz` — the `arm` field is corrupt (opponent/seat/score are sound).
- `rl_matchup_matrix.csv`
- `rl_global_ranking.json` (mean-vs-field per arm)
- `rl_holdout_report.json` (held-out Mega Abomasnow)
- `rl_improvement_report.json`
- `rl_regression_report.json`
- The strategic/held-out/regression sections of `rl_arm_selection.json`, `RL_FEASIBILITY.md`,
  `SUMMARY.md`, and the c008 §27 final response.

## Artifacts NOT affected by this defect

- `rl_teacher_noninferiority.json` and `rl_teacher_games.jsonl.gz` — each candidate ran in its
  own pool call and every aggregate field came from worker-returned values, so no positional
  reattachment occurred.
- `final_reliability.json` / `final_latency.json` — per-candidate pool calls; count/sum only.
- Training evidence: `training_curves.*`, per-arm summaries, `checkpoint_registry.json`,
  `teacher_anchor_report.json` (no multiprocessing relabeling involved).

These are re-derived in c009 anyway, from identity-safe raw games, so no c008 number is
carried forward.

## Additional c008 defects recorded (contract §2.2–§2.4)

1. **Median representative vs "best" (§2.2).** `checkpoint_selection.json.per_arm` designates
   the **median** seed as each arm's representative (R1→seed 202 blend 0.3375, R2→seed 202
   blend 0.31125) and copies it to `{arm}_representative.npz`. The c008 *final evaluation*
   however used the **best-by-validation** checkpoint per arm (R1 seed 101 blend 0.405, R2
   seed 303 blend 0.335, R0 seed 101 blend 0.205), described in the c008 summary as "best
   checkpoint per arm". The two artifacts are therefore internally inconsistent about which
   checkpoint each arm's result refers to. c009 removes the ambiguity by evaluating **every**
   validation-selected checkpoint per seed and reporting all of them.
2. **No untouched V2-A game-zero baseline (§2.3).** c008 never evaluated the exact c007 V2-A
   initialization under the final protocol, so "RL improved" was never established against
   the policy RL actually started from. c009 evaluates B0 explicitly.
3. **Content-blind acceptance (§2.4).** The c008 acceptance checklist tested *file existence*
   (and, late in the run, a few scalar assertions), which is why corrupted-but-present
   aggregates still produced a 16/16 PASS. c009 adds a content-aware validator that
   recomputes every aggregate from raw games and fails on any mismatch.

## Consequence for the c008 conclusions

The c008 *direction* of conclusion (no RL checkpoint was submittable) rested mainly on the
teacher head-to-head, which is structurally sound. But every **strategic-field, held-out,
regression, best-arm, and improvement-over-initialization** statement in c008 is unsupported
and is re-derived from scratch in c009.
