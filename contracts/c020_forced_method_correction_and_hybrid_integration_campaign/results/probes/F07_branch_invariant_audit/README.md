# F07 — Branch invariant audit

31 invariants across corrected MCTS, corrected ByteRL and the hybrid, all holding.

This pass asks a different question from the inertness audit that preceded it. That one asked *does this mechanism do anything?* and found three dead (B2 option references, the A8 end-turn veto, four A6 line features). This one asks *given that it runs, does it obey its own rules?*

Highlights:

- **Native id accounting is exact.** 252 `search_begin` + 18,963 successful `search_step` = 19,215 `search_release`. A leak would still play legal games and pass every gameplay check.
- **Every override cleared every registered threshold** -- the gate is not merely consulted, its verdict is honoured.
- **Action visits never exceed info-set visits** across 939 shared info sets, so the shared table's bookkeeping is internally consistent under concurrent determinizations.
- **Bootstrap value is zero exactly when the unroll ends an episode**, and only the first unroll starts from zero recurrent state.
- **Sibling hybrid states are unaliased** -- mutating a clone leaves the parent and the other sibling untouched, which is what C1 requires and what c019 could not have had.

No new defect was found. That is weaker than 'there are no bugs' and is worth exactly as much as the invariants chosen.
