# Failures

No failures, invalid selections, malformed records, or semantic-replay mismatches
for c003.

- 84/84 tests passed.
- 30/30 validation games completed; 0 invalid selections; 0 structural errors.
- 966/966 safe-agent decisions reproduced by true semantic replay (0 mismatches),
  on both jsonl and gzip.
- 0 `game_seed` occurrences; `engine_rng_controlled` always false.

The engine's non-reproducible trajectory (std::random_device seeding) is a known,
honestly-recorded platform property — not a c003 failure, and c003 does not claim
engine replay. This file satisfies the mandatory `failures/` directory.
