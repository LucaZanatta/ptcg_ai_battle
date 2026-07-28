# Reproduction notes — official_mega_lucario

**Fidelity: EXACT.** This is an exact copy, not a reimplementation.

`main.py` is 509 lines with 5 functions. The copied file hashes identically to the c005 source (`ab8563b67b88b366…`), so nothing was rewritten, trimmed, or simplified.

## Semantic features present

- **planning_or_sequencing**: 27 references
- **prize_resource_tracking**: 11 references
- **damage_calculation**: 13 references
- **matchup_rules**: 5 references
- **energy_management**: 58 references
- **evolution_logic**: 5 references
- **bench_management**: 7 references
- **retreat_switch_logic**: 15 references
- **search_targeting**: 30 references

## Compatibility adapters

One adapter, applied outside the agent source: `cg.teachers.make_fresh` loads `main.py` as a fresh uniquely-named module per game and per seat, with the working directory temporarily set to the agent's folder so its relative `deck.csv` read resolves. These agents keep module-level state and would leak it across games otherwise. **The agent source is not modified** — proven by the identical hash above.

## Known deviations

None.

## Smoke

6 games vs Dragapult, both seats: all completed = True, invalid selections = 0.
