# Reproduction notes — official_mega_abomasnow

**Fidelity: EXACT.** This is an exact copy, not a reimplementation.

`main.py` is 268 lines with 2 functions. The copied file hashes identically to the c005 source (`d1ef4a86413b7f54…`), so nothing was rewritten, trimmed, or simplified.

## Semantic features present

- **planning_or_sequencing**: 1 references
- **prize_resource_tracking**: 6 references
- **damage_calculation**: 3 references
- **matchup_rules**: 2 references
- **energy_management**: 29 references
- **evolution_logic**: 1 references
- **bench_management**: 22 references
- **retreat_switch_logic**: 13 references
- **search_targeting**: 24 references

## Compatibility adapters

One adapter, applied outside the agent source: `cg.teachers.make_fresh` loads `main.py` as a fresh uniquely-named module per game and per seat, with the working directory temporarily set to the agent's folder so its relative `deck.csv` read resolves. These agents keep module-level state and would leak it across games otherwise. **The agent source is not modified** — proven by the identical hash above.

## Known deviations

None.

## Smoke

6 games vs Dragapult, both seats: all completed = True, invalid selections = 0.
