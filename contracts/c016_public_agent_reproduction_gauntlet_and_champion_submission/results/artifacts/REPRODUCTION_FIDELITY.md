# Reproduction fidelity (§14)

3 candidates advanced, **3 classified `EXACT`**, 0 clean-room.

Every candidate is a byte-for-byte copy of an official sample source. c016 does not reimplement them, because §3's central rule forbids replacing a rich public implementation with a smaller from-scratch priority table — the exact error c014 and c015 made.

| candidate | archetype | fidelity | source lines | functions | checks | smoke vs Dragapult |
|---|---|---|---|---|---|---|
| `official_iono` | Iono's deck | **EXACT** | 416 | 2 | 9/9 | 0.3333 |
| `official_mega_lucario` | Mega Lucario ex | **EXACT** | 509 | 5 | 9/9 | 0.5 |
| `official_mega_abomasnow` | Mega Abomasnow ex | **EXACT** | 268 | 2 | 9/9 | 0.6667 |

For contrast, c014's from-scratch Archaludon expert and c015's Iono expert are priority tables of a few hundred lines with no planning, no damage calculation and no matchup overrides. That is why they lost to these same agents locally.

## Compatibility adapters

One adapter, identical for all three, applied **outside** the agent source: `cg.teachers.make_fresh` imports `main.py` as a fresh uniquely-named module per game and per seat with the cwd set to the agent's own directory. The agents keep module-level state and read a relative `deck.csv` at import. Source hashes are unchanged, which is checked rather than claimed.

