# P01 — Canonical action round trip

200 live selects covering 1,467 options, 12 distinct select contexts and 11 option types: every option round-trips API → `CanonicalOption` → submission payload, with zero duplicate keys.

Identity is by KEY, not by index. Index identity would break the moment the engine ordered options differently between a search successor and the live game — exactly where MCTS root aggregation and package execution have to agree.

**Status: PASS.**
