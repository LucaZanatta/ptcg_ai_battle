# Field scores, and where the excluded games went

The pooled rate `wins / scored` assumes exclusions are independent of the opponent. `D15` established that abandonment in this environment IS the stalemate rate, and a stalemate is a property of the MATCHUP — so that assumption is precisely the one this environment breaks.

| arm | games | scored | excluded | pooled | opponent-balanced | Δ | worst opponent excluded | exclusions on one opponent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `depth/k1_s384` | 20 | 19 | 1 | 0.4211 | 0.4375 | 1.64 pp | 0.2 | 1.0 |
| `depth/k8_s384` | 40 | 39 | 1 | 0.2051 | 0.2028 | -0.24 pp | 0.1 | 1.0 |
| `external_evaluations/br3_end_to_end` | 128 | 128 | 0 | 0.0547 | 0.0547 | 0.0 pp | 0.0 | — |
| `external_evaluations/br3_fixed_deck` | 128 | 128 | 0 | 0.0703 | 0.0703 | 0.0 pp | 0.0 | — |
| `external_evaluations/br3_fixed_deck_long` | 128 | 128 | 0 | 0.125 | 0.125 | 0.0 pp | 0.0 | — |
| `external_evaluations/ctrl_BR0` | 128 | 128 | 0 | 0.0547 | 0.0547 | 0.0 pp | 0.0 | — |
| `external_evaluations/ctrl_BR1` | 128 | 128 | 0 | 0.0625 | 0.0625 | 0.0 pp | 0.0 | — |
| `external_evaluations/ctrl_BR1_5` | 128 | 128 | 0 | 0.0781 | 0.0781 | 0.0 pp | 0.0 | — |
| `external_evaluations/ctrl_BR2` | 128 | 128 | 0 | 0.0781 | 0.0781 | 0.0 pp | 0.0 | — |
| `external_evaluations/ctrl_BR3` | 128 | 128 | 0 | 0.0859 | 0.0859 | 0.0 pp | 0.0 | — |
| `external_evaluations/floor_end_to_end` | 128 | 128 | 0 | 0.0625 | 0.0625 | 0.0 pp | 0.0 | — |
| `external_evaluations/floor_fixed_deck` | 128 | 128 | 0 | 0.0234 | 0.0234 | 0.0 pp | 0.0 | — |
| `external_evaluations/smoke_floor` | 8 | 8 | 0 | 0.0 | 0.0 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_end_to_end_u008800` | 128 | 128 | 0 | 0.0469 | 0.0469 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_end_to_end_u017600` | 128 | 128 | 0 | 0.0781 | 0.0781 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_end_to_end_u026400` | 128 | 128 | 0 | 0.0391 | 0.0391 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_fixed_deck_u008800` | 128 | 128 | 0 | 0.0703 | 0.0703 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_fixed_deck_u017600` | 128 | 128 | 0 | 0.0625 | 0.0625 | 0.0 pp | 0.0 | — |
| `external_evaluations/traj_br3_fixed_deck_u026400` | 128 | 128 | 0 | 0.0547 | 0.0547 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u012000` | 128 | 128 | 0 | 0.0547 | 0.0547 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u036000` | 128 | 128 | 0 | 0.0859 | 0.0859 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u060000` | 128 | 128 | 0 | 0.1328 | 0.1328 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u086000` | 128 | 128 | 0 | 0.0547 | 0.0547 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u110000` | 128 | 128 | 0 | 0.1328 | 0.1328 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u134000` | 128 | 128 | 0 | 0.1328 | 0.1328 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u150000` | 128 | 128 | 0 | 0.1328 | 0.1328 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u174000` | 128 | 128 | 0 | 0.125 | 0.125 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u198000` | 128 | 128 | 0 | 0.125 | 0.125 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u222000` | 128 | 128 | 0 | 0.1797 | 0.1797 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u244000` | 128 | 128 | 0 | 0.1602 | 0.1602 | 0.0 pp | 0.0 | — |
| `external_evaluations/trajlong_u268000` | 128 | 128 | 0 | 0.1641 | 0.1641 | 0.0 pp | 0.0 | — |
| `final_panel/panel` | 180 | 180 | 0 | 0.2778 | 0.2778 | 0.0 pp | 0.0 | — |
| `final_panel/raw` | 180 | 180 | 0 | 0.2778 | 0.2778 | 0.0 pp | 0.0 | — |
| `fixed_simulations_per_world/fpw_k1` | 32 | 32 | 0 | 0.1562 | 0.1562 | 0.0 pp | 0.0 | — |
| `fixed_simulations_per_world/fpw_k2` | 32 | 32 | 0 | 0.25 | 0.25 | 0.0 pp | 0.0 | — |
| `fixed_simulations_per_world/fpw_k4` | 32 | 32 | 0 | 0.2188 | 0.2188 | 0.0 pp | 0.0 | — |
| `fixed_simulations_per_world/fpw_k8` | 32 | 32 | 0 | 0.2188 | 0.2188 | 0.0 pp | 0.0 | — |
| `fixed_total_simulations/ft_k1` | 32 | 32 | 0 | 0.125 | 0.125 | 0.0 pp | 0.0 | — |
| `fixed_total_simulations/ft_k2` | 32 | 32 | 0 | 0.1875 | 0.1875 | 0.0 pp | 0.0 | — |
| `fixed_total_simulations/ft_k4` | 32 | 32 | 0 | 0.0938 | 0.0938 | 0.0 pp | 0.0 | — |
| `fixed_total_simulations/ft_k8` | 32 | 32 | 0 | 0.0938 | 0.0938 | 0.0 pp | 0.0 | — |
| `k1_control/m04_k1_reuse` | 60 | 52 | 8 | 0.1538 | 0.1641 | 1.03 pp | 0.2667 | 0.5 |
| `kaggle_deploy/deploy_k1` | 40 | 35 | 5 | 0.0857 | 0.125 | 3.93 pp | 0.5 | 1.0 |
| `kaggle_deploy/deploy_k8` | 40 | 33 | 7 | 0.1818 | 0.2333 | 5.15 pp | 0.5 | 0.7143 |
| `noise_floor/noise_k1_s40031` | 200 | 200 | 0 | 0.135 | 0.135 | 0.0 pp | 0.0 | — |
| `noise_floor/noise_k1_s71877` | 200 | 200 | 0 | 0.085 | 0.085 | -0.0 pp | 0.0 | — |
| `noise_floor/noise_k1_s90210` | 200 | 200 | 0 | 0.125 | 0.125 | 0.0 pp | 0.0 | — |
| `paired/paired_k1` | 200 | 199 | 1 | 0.1156 | 0.115 | -0.06 pp | 0.02 | 1.0 |
| `paired/paired_k1_c96` | 200 | 195 | 5 | 0.1231 | 0.13 | 0.69 pp | 0.1 | 1.0 |
| `paired/paired_k8` | 200 | 200 | 0 | 0.165 | 0.165 | 0.0 pp | 0.0 | — |
| `prior_only/T1_policy_prior` | 200 | 200 | 0 | 0.13 | 0.13 | 0.0 pp | 0.0 | — |
| `rollout_only/T2_rollout_policy` | 200 | 200 | 0 | 0.12 | 0.12 | 0.0 pp | 0.0 | — |
| `unrestricted_reference/m11_probe_parallel` | 6 | 5 | 1 | 0.0 | 0.0 | 0.0 pp | 0.5 | 1.0 |
| `unrestricted_reference/m11_probe_serial` | 2 | 2 | 0 | 0.5 | 0.5 | 0.0 pp | 0.0 | — |

A `Δ` near zero means the exclusions were spread evenly and the pooled rate is safe. A large `Δ` with exclusions concentrated on one opponent means the pooled rate is an average over a panel that is missing part of itself.

## Arms where the panel is unbalanced by exclusion

### `k1_control/m04_k1_reuse`

8 of 60 games excluded, 50% of them against `mega_lucario`, which lost 27% of its games.

| opponent | played | scored | excluded | rate |
|---|---:|---:|---:|---:|
| dragapult | 15 | 15 | 0 | 0.0667 |
| iono | 15 | 12 | 3 | 0.0833 |
| mega_abomasnow | 15 | 14 | 1 | 0.1429 |
| mega_lucario | 15 | 11 | 4 | 0.3636 |

Pooled **0.1538**, opponent-balanced **0.1641** (1.03 pp). The balanced figure is the one to read.

### `kaggle_deploy/deploy_k1`

5 of 40 games excluded, 100% of them against `mega_lucario`, which lost 50% of its games.

| opponent | played | scored | excluded | rate |
|---|---:|---:|---:|---:|
| dragapult | 10 | 10 | 0 | 0.0 |
| iono | 10 | 10 | 0 | 0.0 |
| mega_abomasnow | 10 | 10 | 0 | 0.1 |
| mega_lucario | 10 | 5 | 5 | 0.4 |

Pooled **0.0857**, opponent-balanced **0.125** (3.93 pp). The balanced figure is the one to read.

### `kaggle_deploy/deploy_k8`

7 of 40 games excluded, 71% of them against `mega_lucario`, which lost 50% of its games.

| opponent | played | scored | excluded | rate |
|---|---:|---:|---:|---:|
| dragapult | 10 | 10 | 0 | 0.0 |
| iono | 10 | 9 | 1 | 0.3333 |
| mega_abomasnow | 10 | 9 | 1 | 0.0 |
| mega_lucario | 10 | 5 | 5 | 0.6 |

Pooled **0.1818**, opponent-balanced **0.2333** (5.15 pp). The balanced figure is the one to read.

