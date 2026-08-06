# c018 Project Ground Truth

- c018 is a new execution contract, not an amendment to c017.
- c017 remains immutable and is classified as partial/failed competitively.
- The frozen baseline is the exact official Mega Lucario package submitted in c017, expected reference `55011215`.
- c017 did not implement real forward search: it used `env.clone()` and then a depth-zero heuristic ranker.
- The official starter-kit search interface exposes `search_begin`, `search_step`, `search_release`, and `search_end`; c018 must use these calls for every claimed search successor.
- c017 did not implement actual PPO curriculum training: virtual opponent draws and unchanged checkpoints are not training.
- c018 must run real simulator games, nonzero optimizer steps, changed checkpoint hashes, and real policy/value-guided search.
- Probes are primarily diagnostic and non-blocking. Failures taint downstream artifacts unless they make execution impossible.
- The strongest trustworthy stage must be packaged and submitted; it need not be the most sophisticated final stage.
- Historical contracts and results c005–c017 are read-only.
