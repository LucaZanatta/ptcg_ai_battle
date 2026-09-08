# P12 — Freshness and identity

**Self-play opponents are fresh.** `rl_env._build_opponent` caches `RLPolicy` objects **by
path**, so writing every snapshot to one filename would serve the first snapshot forever while
the report happily claimed self-play had advanced — the same defect shape as c012's cached
per-path file hash. Each block therefore writes `..._lagged_bNN.npz`:
80 snapshots, 80 distinct paths,
80 distinct contents.

**No game-zero promotion.** 0 blocks completed zero games; all are marked
promotion-ineligible.

**Panel identity.** Every raw panel row carries its own `candidate_id`, `opponent_id`, `seat` and
`seed`, and aggregates are recomputed from those fields — worker results are never positionally
zipped back onto the job list, which is how a panel silently credits one agent with another's
wins.

**Status: PASS.**
