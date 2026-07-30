# M12 — the Kaggle deployment arm, at c021's measured clock

`PROBE_MATRIX M12`: *"Kaggle budget changes do not modify reference branch."* The deploy arm is a
separately named branch, `MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY`, and `FIDELITY_RULES §2`
forbids judging source transfer by it.

## The clock is not invented

Every timing parameter is read off the frozen `C021_MCGS_K1_CONTROL` config in
`results/controls/control_manifest.json`:

```json
"match_clock_seconds": 90.0,      // the cumulative Kaggle budget c021 played under
"first_move_seconds": 0.9,        // the source's 15 s, scaled ~16.7x to fit it
"continuing_move_seconds": 0.7    // the source's 10 s, same scaling
```

An earlier draft of this arm used `--decision-cap 5` and a count-budgeted protocol. Both were
invented, and c021's deploy agent was time-budgeted, so a count-budgeted arm would not have been
the same question. Replaced before either arm ran; recorded in `UNRESOLVED_REFERENCE_CHOICES.md`.

## Result

| | `deploy_k1` | `deploy_k8` |
|---|---:|---:|
| field score, pooled | 0.0857 | 0.1818 |
| **field score, opponent-balanced** | **0.1250** | **0.2333** |
| Wilson 95% (pooled) | [0.030, 0.224] | [0.086, 0.344] |
| completed / games | 35 / 40 | 33 / 40 |
| **median simulations per decision (total, all worlds)** | **44** | **42** |
| p75 / max | 68 / 169,223 | 69 / 140,848 |
| match-clock exhausted decisions | 0 | 0 |
| wall clock | 1320 s | 1850 s |

**Read the balanced column.** Both arms lost half of their `mega_lucario` games to the 900 s
per-game guard, and `mega_lucario` is the one matchup either arm wins — so the pooled rate is a
panel average over a panel missing part of itself. `FIELD_BALANCE.md` recomputes both from raw
per-game records; the correction is +3.9 pp for K=1 and +5.2 pp for K=8.

## What the deployment clock actually buys

**42 simulations per decision at K=8, against 44 at K=1.** The clock is the budget, so K does not
buy more search — it divides the same search eight ways. Each of the eight worlds receives about
**five simulations**.

That is the interesting part of this arm. Five simulations per world is severe starvation by any
standard, and the K=8 arm still scores higher on both the pooled and the balanced figure. It is
consistent with what the 200-game paired arms found in calibration: at these budgets the binding
constraint is not depth, it is that depth is spent inside a single world that may be wrong.

## What is NOT claimed

- **No credible improvement.** The Wilson intervals overlap substantially
  ([0.030, 0.224] against [0.086, 0.344]), 40 games is far below the 200 the paired arms needed,
  and the measured run-to-run floor is 5.0 pp at 200 games — wider here. `DECISION_RULES §2`:
  "A small noisy improvement over c021 MCGS is not a competitive pass."
- **No submission rationale.** The frozen competitive bar is
  `BASELINE_OFFICIAL_MEGA_LUCARIO`, and neither arm is near it. The like-for-like comparison is
  the final panel, which re-runs the bar over these same opponents rather than quoting its c020
  figure.
- **Nothing about source fidelity.** `FIDELITY_RULES §2` forbids it, and the median of 42
  simulations per decision is about 7% of what the source's own schedule buys
  (`M11_SOURCE_TIMING.md`: median ~600). This arm measures a deployment budget, not a method.

## The guard, and the exclusions it caused

The 900 s per-game guard cut 5 and 7 games respectively, concentrated in `mega_lucario` (half its
games in both arms). Per `D15`, abandonment here is the stalemate rate rather than slowness, and
a mirror-ish matchup stalemating more often is a property of the matchup. The consequence is
handled by reporting the opponent-balanced score rather than by raising the guard, because
raising it would lengthen the arm without changing which games stalemate.
