# Selection decision and competitive gate (§18)

**competitive_gate = FAIL**

**No candidate qualifies.** Best candidate: `official_mega_lucario`. No upload is performed — §2 and §7 forbid submitting a weak package merely to complete the contract.

Exact failed gates:

- base condition safe_control_ge_0.90
- base condition vs_c014_ge_0.65

## Ranking (lexicographic, exactly as pre-registered)

1 passes reproduction fidelity (EXACT or FAITHFUL_CLEAN_ROOM)
2 passes all reliability and package-feasibility hard gates
3 score rate vs Dragapult on independent confirmation
4 mean score rate across official Iono, Mega Lucario, Mega Abomasnow on independent confirmation
5 direct cross-play vs the other finalist
6 lower p99 latency
7 stronger current public evidence quality

| rank | candidate | fidelity | vs Dragapult (confirm) | field mean | vs c014 | vs c015 | safe | base | path |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `official_mega_lucario` | EXACT | 0.52 | 0.6142 | 0.625 | 0.91 | 0.8333 | NO | B |
| 2 | `official_mega_abomasnow` | EXACT | 0.5025 | 0.4067 | 0.69 | 0.93 | 0.9111 | yes | — |
| 3 | `official_iono` | EXACT | 0.29 | 0.49 | 0.9 | 0.92 | 0.9778 | yes | — |

## Base conditions per candidate

**`official_mega_lucario`** — fidelity_ok: pass, safe_control_ge_0.90: **FAIL**, vs_c014_ge_0.65: **FAIL**, vs_c015_ge_0.65: pass, zero_reliability_violations: pass

**`official_mega_abomasnow`** — fidelity_ok: pass, safe_control_ge_0.90: pass, vs_c014_ge_0.65: pass, vs_c015_ge_0.65: pass, zero_reliability_violations: pass

**`official_iono`** — fidelity_ok: pass, safe_control_ge_0.90: pass, vs_c014_ge_0.65: pass, vs_c015_ge_0.65: pass, zero_reliability_violations: pass

## Strength paths

### `official_mega_lucario`

- **A** (>= 0.55 over >= 400 games, Wilson LB > 0.5): vs Dragapult 0.52 over 400 games, Wilson LB 0.4711 → **FAIL**
- **B** (>= 0.48 vs Dragapult over >= 400, field mean >= 0.55 over >= 600, not worse than 0.1 on two official opponents): vs Dragapult 0.52, field mean 0.6142 → **PASS**
- **C**: no >=900-equivalent published score or matchup benchmark exists for the official sample agents; the LB-950 public claim belongs to a different, LOCAL_BENCHMARK_ONLY notebook and cannot be transferred to this candidate. Path C is not available rather than stretched to fit. → **FAIL**

### `official_mega_abomasnow`

- **A** (>= 0.55 over >= 400 games, Wilson LB > 0.5): vs Dragapult 0.5025 over 400 games, Wilson LB 0.4537 → **FAIL**
- **B** (>= 0.48 vs Dragapult over >= 400, field mean >= 0.55 over >= 600, not worse than 0.1 on two official opponents): vs Dragapult 0.5025, field mean 0.4067 → **FAIL**
- **C**: no >=900-equivalent published score or matchup benchmark exists for the official sample agents; the LB-950 public claim belongs to a different, LOCAL_BENCHMARK_ONLY notebook and cannot be transferred to this candidate. Path C is not available rather than stretched to fit. → **FAIL**

### `official_iono`

- **A** (>= 0.55 over >= 400 games, Wilson LB > 0.5): vs Dragapult 0.29 over 200 games, Wilson LB None → **FAIL**
- **B** (>= 0.48 vs Dragapult over >= 400, field mean >= 0.55 over >= 600, not worse than 0.1 on two official opponents): vs Dragapult 0.29, field mean 0.49 → **FAIL**
- **C**: no >=900-equivalent published score or matchup benchmark exists for the official sample agents; the LB-950 public claim belongs to a different, LOCAL_BENCHMARK_ONLY notebook and cannot be transferred to this candidate. Path C is not available rather than stretched to fit. → **FAIL**

## Cross-play

`official_mega_abomasnow` vs `official_mega_lucario`: 0.53 over 300 games (Wilson [0.4735, 0.5857]).

