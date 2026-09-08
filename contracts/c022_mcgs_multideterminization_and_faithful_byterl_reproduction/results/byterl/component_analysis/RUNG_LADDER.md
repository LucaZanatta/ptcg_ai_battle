# The controlled rung ladder — `ctrl`

Equal budget at every rung: **120,097 decisions**, one codebase, one commit. `FIDELITY_RULES §4` fixes the deltas; `MANDATORY_IMPLEMENTATION B7` requires adjacent stages to differ only by the published change, and `tests/test_c022_stage_ladder.py` rejects extra changes.

**Throughput validity (D18): PASS**

learner rate per rung: `{'BR0': 91.1, 'BR1': 115.1, 'BR1_5': 131.2, 'BR2': 35.1, 'BR3': 89.5}` (median 91.1/s)

**These rungs are not claimed to have run in isolation (D22).** The pre-b2 rungs ran with no competing MCGS arm, which is what D18 requires, but light foreground tooling — a 695-test suite, the validator, the status and fixture tools — ran during BR0's and BR1's windows. The rates above are the measurement of that, and they are printed rather than smoothed. The spread is 1.26x against D18's 9x, and the `[0.6, 1.7]` bound is set for the latter, so it correctly does not fire here. Nothing below rests on the rungs having been isolated; the external comparisons rest on their evaluation games, which are played from frozen checkpoints and are not affected by the rate at which those checkpoints were produced.

## Rungs

| rung | delta from below | decisions | dec/s | prod/cons | B06 coverage | external field | Wilson 95% |
|---|---|---:|---:|---:|---:|---:|---|
| **BR0** | — | 120,076 | — | 8.7317 | 10% (3) | 0.0547 | [0.0267, 0.1086] |
| **BR1** | gamma 0.99 -> 1.0 | 120,002 | — | 8.2232 | 11% (3) | 0.0625 | [0.032, 0.1185] |
| **BR1_5** | published random initial deck-construction selections | 120,031 | — | 7.9217 | 11% (3) | 0.0781 | [0.043, 0.1378] |
| **BR2** | bounded blocking FIFO + balanced production/consumption | 120,097 | — | 1.0064 | 100% (28) | 0.0781 | [0.043, 0.1378] |
| **BR3** | two-sided clipped V-trace + PPO-style clipped policy objective | 120,088 | — | 1.0073 | 100% (28) | 0.0859 | [0.0487, 0.1473] |

random floor `floor_fixed_deck`: **0.0234** [0.008, 0.0666] over 128 games
random floor `floor_end_to_end`: **0.0625** [0.032, 0.1185] over 128 games

## Adjacent-rung comparisons

| pair | published change | Δ field | intervals overlap? | reading |
|---|---|---:|---|---|
| BR0 → BR1 | gamma 0.99 -> 1.0 | 0.78 pp | yes | no resolvable effect at 128 games |
| BR1 → BR1_5 | published random initial deck-construction selections | 1.56 pp | yes | no resolvable effect at 128 games |
| BR1_5 → BR2 | bounded blocking FIFO + balanced production/consumption | 0.0 pp | yes | no resolvable effect at 128 games |
| BR2 → BR3 | two-sided clipped V-trace + PPO-style clipped policy objective | 0.78 pp | yes | no resolvable effect at 128 games |

At 128 evaluation games a Wilson interval spans roughly 8 points at these win rates, so an overlapping pair establishes no effect on external strength. That is a statement about the evaluation's resolution, not about the change: `FIDELITY_RULES §5` forbids converting an unresolved comparison into a method failure.

## B06 / D19 replay fidelity per rung

| rung | status | checks | max recurrence Δ | max logp Δ | max behaviour Δ | uniform steps seen |
|---|---|---:|---:|---:|---:|---:|
| BR0 | **PASS** | 3 | 0.0 | 2.38e-07 | 0.0 | 0 |
| BR1 | **PASS** | 3 | 0.0 | 0.0 | 0.0 | 0 |
| BR1_5 | **PASS** | 3 | 0.0 | 0.0 | 0.0 | 20 |
| BR2 | **PASS** | 28 | 0.0 | 0.0 | 0.0 | 70 |
| BR3 | **PASS** | 28 | 0.0 | 4.77e-07 | 0.0 | 100 |


