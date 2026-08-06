# c019 Audit Findings — Must Be Detected and Corrected

## MCTS

1. c019 used one independent PUCT tree per determinization and aggregated at the root; this is PIMC-like, not shared-statistics ISMCTS.
2. c019 leaf evaluation overvalued prizes/aggregate HP/energy/bench count and omitted lethal, attack legality/readiness, typed energy, targets, and resources.
3. More search made performance worse because it optimized the wrong objective.
4. A small number of overrides caused large performance loss; many sampled changed actions selected end turn over productive baseline card play.
5. Unknown archetypes silently defaulted to Dragapult.
6. Search needed conservative confidence-based override/veto logic.

## ByteRL

7. Active and bench Pokémon were pooled, destroying slot/instance identity.
8. Energy type, status/tool identity, and option-to-target relationships were insufficiently encoded.
9. Multi-select execution stored/trained only the first selection/probability rather than complete joint action.
10. Actor carried recurrent state, but learner reset state at mid-game unroll boundaries.
11. V-trace ratios therefore compared target and behavior probabilities under different recurrent contexts.
12. OSFP G/C accumulated across learning periods and changing learner policies.
13. Promotion evidence was not a clean frozen-checkpoint evaluation.

## Hybrid and validation

14. Hybrid called recurrent ByteRL with `state=None` at search nodes.
15. Bad priors severely damaged MCTS; weak value was not admitted rigorously.
16. c019 validator passed despite these semantic defects.
17. Method names/file existence and optimizer counts are insufficient fidelity evidence.
