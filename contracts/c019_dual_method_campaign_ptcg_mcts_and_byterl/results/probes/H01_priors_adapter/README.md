# H01 — Priors adapter

`ByteRLPriorProvider` maps ByteRL option probabilities onto canonical MCTS children BY KEY, not by index, and normalizes over the legal set. It is a constructor argument defaulting to `None`.

**Competitively evaluated, and ablated.** The combined hybrid injects two adapters at once, so a delta against pure MCTS could not be attributed to either. Each was therefore isolated against the same search at the same configuration, 320 games, 0 incomplete.

| arm | field | 95% CI | vs pure MCTS |
|---|---|---|---|
| baseline | 0.6 | — | — |
| pure MCTS | 0.375 | [0.2769, 0.4845] | — |
| + leaf value only | 0.35 | [0.2545, 0.4592] | -2.5 |
| + priors only | 0.0875 | [0.043, 0.1698] | -28.7 |

The priors adapter is responsible. Replacing the search's priors with the ByteRL policy costs -28.7 field points against pure MCTS, while the calibrated leaf value costs -2.5 points with heavily overlapping confidence intervals ([0.2545, 0.4592] vs [0.2769, 0.4845]) -- indistinguishable from no change at this sample size. A value head that beats the hand-written heuristic on held-out leaves is roughly neutral inside the search; a policy scoring 0.066 on its own is catastrophic as a PUCT prior, because a confidently wrong prior distorts selection at every node while a leaf value only perturbs backups.

**Status: PASS** — implemented, switchable, and measured rather than asserted. The adapter is NOT enabled in any submitted package: it makes the search decisively worse.
