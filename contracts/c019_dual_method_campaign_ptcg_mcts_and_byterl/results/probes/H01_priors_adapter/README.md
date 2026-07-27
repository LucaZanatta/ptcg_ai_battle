# H01 — Priors adapter

`ByteRLPriorProvider` maps ByteRL option probabilities onto canonical MCTS children BY KEY, not by index, and normalizes over the legal set. It is a constructor argument defaulting to `None`.

Not evaluated on the panel: §10 caps hybrid work at 15% and forbids delaying pure submissions, and the pure MCTS branch did not clear its gate, so a hybrid built on it had no path to promotion.

**Status: WARN** — implemented and switchable, not competitively evaluated.
