# c017 — end-to-end search, learning and curriculum campaign

**STATUS = PARTIAL** · mode `OFFLINE_TEACHER_MODE`

## What was achieved

The full vertical ran end to end: baseline → search teacher → labelled trajectories → CUDA policy/value distillation → baseline-anchored curriculum → common final panel. The c016 Mega Lucario baseline was reverified, packaged, validated from clean extraction and **submitted (ref 55011215, COMPLETE)**.

## The finding that shapes everything else

**Forward simulation is impossible in this simulator.** `env.clone()` copies the Python wrapper but both wrappers address the same native `libcg.so` state, so advancing a clone core-dumps the process and truncates the parent episode. Probe P10 records it. The consequence is honest and unavoidable: the 'search teacher' is a **depth-0 heuristic ranker**, not lookahead, and nothing downstream supports a claim about search depth.

## Final panel

| candidate | Dragapult | Iono | Abomasnow | safe control | field mean | invalid | p99 ms |
|---|---|---|---|---|---|---|---|
| `baseline_package` | 0.575 | 0.8 | 0.4 | 0.7 | **0.5917** | 0 | 1.219 |
| `distilled_policy` | 0.1 | 0.2 | 0.1 | 0.45 | **0.1333** | 0 | 4.635 |

## Selection

no post-baseline candidate is both TRUSTED and package-safe, and the distilled policy does not meaningfully improve the baseline, so §36 does not authorise a second upload and §45 forbids forcing a weak or tainted stage to win.

Uploads used: **1 of 3**.

## Pipeline results, stage by stage

- **Search teacher**: 60 games, 3616 decisions, 1619 searched, action changed on 0.2038 of searched decisions. Redaction verified clean; zero invalid actions.
- **Distillation** (CUDA): test top-1 agreement **0.526** against a teacher-equals-baseline rate of **0.9087** — the model is weaker than trivially copying the baseline.
- **Curriculum**: 2000 games, final stage S0, **0 performance promotions**. Every transition was `FALLBACK_SCHEDULE`, which is not evidence of curriculum success and is not reported as such.

## Probes

- `P00_baseline_submission`: **PASS**
- `P10_forward_simulation`: **FAIL_TAINTED**
- `P11_search_integration`: **PASS**
- `P19_transition_fixtures`: **PASS**
- `P20_checkpoint_freshness`: **PASS**
- `P21_opponent_mixture_audit`: **PASS**
- `P22_exact_continuation`: **NOT_EXERCISED**
- `P23_promotion_arithmetic`: **PASS**
- `P24_policy_diversity`: **NOT_EXERCISED**
- `P20_distillation`: **PASS**
- `P30_end_to_end_smoke`: **PASS**
- `P40_guided_search`: **NOT_EXERCISED**
- `P50_heuristic_search_package`: **NOT_EXERCISED**

## Known limitations

- forward simulation is impossible in this simulator: env.clone() shares native libcg.so state and advancing a clone core-dumps the process (probe P10). The 'search teacher' is therefore a depth-0 heuristic ranker, and no result here supports any claim about lookahead.
- campaign scale was reduced to roughly 1-5% of the contract's caps, registered in advance in REGISTERED_MODE_AND_SCALE.md. Every training result is underpowered.
- the distilled policy reaches 0.526 top-1 agreement where trivially copying the baseline scores 0.909, so it is weaker than the agent it distils from.
- no post-baseline candidate is TRUSTED and package-safe, so only one of the three permitted uploads was used.
- the public score is a live ladder rating; the recorded value is a timestamped snapshot, not a settled result.

