# Phase 1 — what the measurements imply for scheduling

Scheduling input only. No algorithm below is chosen by these numbers.

## Native primitive costs (single worker, real positions)

| primitive | mean | p50 | p95 |
|---|---|---|---|
| `search_step` | **83.9 µs** | 74.7 µs | 135.2 µs |
| `search_begin` | 201.6 µs | 145.0 µs | 215.6 µs |
| `search_release` | 1.1 µs | 0.9 µs | 1.3 µs |
| `observation_hash` | 37.5 µs | 38.0 µs | 45.8 µs |
| `canonical_options` | 12.4 µs | 13.1 µs | 19.0 µs |

`search_step` is **cheap** — 84 µs, not milliseconds. Zero step errors across 286 calls.

`observation_hash` at 37.5 µs is the number that matters most for MCGS specifically: the
transposition table hashes a state abstraction on **every** node visit, so at ~45% of a step's
cost it is a first-class expense rather than a rounding error. A naive re-hash per lookup would
roughly halve throughput.

## Process scaling

| workers | steps/s | per worker | efficiency |
|---|---|---|---|
| 1 | 120.5 | 120.5 | 1.000 |
| 2 | 235.2 | 117.6 | 0.976 |
| 4 | 400.5 | 100.1 | 0.831 |
| 8 | 789.4 | 98.7 | 0.819 |
| 12 | 1,102.6 | 91.9 | **0.763** |

Twelve physical cores retain 76% per-worker efficiency. Scheduling target: **12 workers** for
throughput runs, and **strict isolation** for any timed measurement — c020 established that
contention charged against a per-decision wall-clock budget can invert a ranking.

## The finding that matters for MCGS fidelity

The official source allocates **15 s for a first move and 10 s for continuing moves**. At 83.9 µs
per step, a 10 s budget affords roughly **119,000 native `search_step` calls on one worker**.

For contrast, c020's PUCT search ran **891 steps and 74.6 simulations per decision** inside a
700 ms budget. The official MCGS time allocation is ~14× larger in wall clock and buys ~130× more
forward steps.

This is a genuinely important result for the campaign: **c020's search was budget-starved by a
configuration choice, not by the environment.** A faithful MCGS port can afford a deep graph
search with real rollouts, which is the regime the published method was tuned for.

## The tension that follows, and where it belongs

PTCG imposes a **cumulative ten-minute match clock**. A game runs roughly 50-60 decisions. At the
source's 10 s per continuing move that is 500-600 s of search per match — at or beyond the entire
match budget, before accounting for the opponent.

Per `MANDATORY_IMPLEMENTATION`:

- **A8** requires the reference branch to preserve the source's time allocation and per-deck
  parameters. So `MCGS_2019_OFFICIAL_SOURCE_PORT` keeps 15 s / 10 s and will exceed the PTCG match
  clock. That is a real, documented consequence of fidelity, not an oversight.
- **A10** lists "deployment scheduling/time budget" as an allowed correction in
  `MCGS_2019_PTCG_LEGAL_CORRECTED`. The clock-fitting adjustment belongs there and nowhere else.

Recording the split now, before either branch exists, so the eventual budget difference cannot be
mistaken for a tuning decision made after seeing results.

## Consequences adopted

1. Reference branch: source parameters verbatim — `UCTConstant 0.285`, `SampleWidth 24`,
   `DampingParameter 2`, 15 s / 10 s, `UCDParams (1, 0)`.
2. Reference evaluation runs under a registered per-decision cap for measurement feasibility,
   recorded as a `MECHANICAL_ADAPTER` with every activation logged, never as a semantic change.
3. Corrected branch: match-clock-aware allocation, registered separately.
4. Transposition hashing is computed once per node and cached on the node, since re-hashing is
   ~45% of a forward step.
