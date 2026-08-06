# Evaluation protocol (§15) — frozen before any candidate result

This file is written and committed **before** the gauntlet runs. §15 forbids changing the panel or the ranking rule after scores are seen; any change would require a written amendment before rerunning.

## Panel

| opponent | role |
|---|---|
| `dragapult` | frozen Dragapult control (official sample) |
| `iono` | official Iono sample agent |
| `mega_lucario` | official Mega Lucario control |
| `mega_abomasnow` | official Mega Abomasnow control |
| `__c014__` | c014 custom Archaludon package (exact archive) |
| `__c015__` | c015 custom Iono package (exact archive) |
| `__safe__` | deterministic safe control |

## Seeds

Stage A/B use the fixed block starting at 160000; confirmation uses a disjoint block starting at 970000. **The same seed list is replayed for every candidate**, so no candidate can draw easier games.

## Game minimums

Stage A: 40 vs safe control, 80 vs Dragapult, seats balanced.

Stage B per finalist: 200 vs dragapult, 100 vs iono, 100 vs mega_lucario, 100 vs mega_abomasnow, 100 vs __c014__, 100 vs __c015__, 160000 vs seed_block.

Confirmation (independent seeds): 200 vs Dragapult, 300 across the official field. Cross-play: 300 games between the top two.

## Lexicographic ranking

1 passes reproduction fidelity (EXACT or FAITHFUL_CLEAN_ROOM)
2 passes all reliability and package-feasibility hard gates
3 score rate vs Dragapult on independent confirmation
4 mean score rate across official Iono, Mega Lucario, Mega Abomasnow on independent confirmation
5 direct cross-play vs the other finalist
6 lower p99 latency
7 stronger current public evidence quality

## Base conditions and strength paths

```json
{
  "base_conditions": {
    "safe_control_min": 0.9,
    "vs_c014_min": 0.65,
    "vs_c014_min_games": 100,
    "vs_c015_min": 0.65,
    "vs_c015_min_games": 100,
    "reliability_violations": 0,
    "fidelity_in": [
      "EXACT",
      "FAITHFUL_CLEAN_ROOM"
    ]
  },
  "strength_paths": {
    "A": {
      "vs_dragapult_min": 0.55,
      "min_games": 400,
      "wilson_lb_above": 0.5
    },
    "B": {
      "vs_dragapult_min": 0.48,
      "min_games": 400,
      "field_mean_min": 0.55,
      "field_min_games": 600,
      "max_deficit_vs_dragapult_on_two_opponents": 0.1
    },
    "C": {
      "requires": "EXACT + >=900-equivalent PUBLIC_CLAIM + source benchmark match within 10pp over >=200 games + (>=0.50 vs Dragapult or >=0.55 field mean) + explicit evidence-quality approval"
    }
  }
}
```

## Aggregation

identity-safe: every record carries candidate_id/opponent_id/seat/seed and is aggregated by those fields; results are never zipped positionally.

