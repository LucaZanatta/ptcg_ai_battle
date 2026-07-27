# c018 audit findings that c019 must enforce

1. A real search API call count does not prove a real MCTS algorithm.
2. Non-root nodes must branch. Hardcoded option-index continuation is forbidden.
3. Search must preserve branch-local state for any stateful rollout/baseline policy.
4. Determinization must sample a legal multiset without replacement; filler duplication is forbidden.
5. A configured parameter such as `beam_width` or `c_puct` must affect runtime behavior and be proven by traces.
6. A policy/value model may not enter MCTS merely because it exists. Policy priors and leaf values must be calibrated independently.
7. Real optimizer steps do not prove ByteRL. V-trace, UPGO, actor staleness correction, historical policy mixture, and OSFP promotion must be implemented and exercised.
8. Self-play percentage changing with block number is not OSFP.
9. `PASS` probes must validate their actual claim. Resume success is not exact stochastic continuation.
10. Candidate labels such as CHALLENGER must follow competitive evidence, not package existence.
