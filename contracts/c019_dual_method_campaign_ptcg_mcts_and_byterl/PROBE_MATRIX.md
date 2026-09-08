# c019 probe matrix

Probes run alongside both branches. Most failures taint the affected branch and do not stop the other branch or shared pipeline smoke.

## Submission blockers

Only these block submission of the affected candidate:

- hidden-information leakage;
- illegal actions or corrupted action serialization;
- crash/timeout risk;
- package/source/hash mismatch;
- evaluation identity corruption;
- unresolved code/data permission.

## Common probes

### P00 — Git and c018 parent resolution
Record candidate commits, selected parent, dirty work, initial branch/head.

### P01 — Canonical action round trip
Every option type/context in fixtures round-trips API option → canonical key → submission payload.

### P02 — Shared observation legality
Encoder/view never reads opponent hidden hand, deck order, or unrevealed prize IDs.

### P03 — Same-deck/base freeze
Verify both branches use identical registered deck and source snapshot.

## MCTS probes

### M01 — Baseline memory parity
Refactored branch-local rollout policy with zero search budget matches original baseline actions and outcome distribution.

### M02 — Legal determinization multiset
Exact hidden-zone counts, no duplicate filler, no negative card counts, no true hidden-state access.

### M03 — Non-root expansion
Runtime trace contains at least one non-root node with two or more real `search_step` children.

### M04 — PUCT numerical fixture
Selection matches hand-calculated Q/P/N fixture; `c_puct` changes selected child in a registered sensitivity fixture.

### M05 — Backup sign/value
Known two-ply zero-sum fixture updates visits/value sums correctly.

### M06 — Revisit evidence
Root visits greatly exceed root child count; existing children receive repeated updates.

### M07 — Rollout policy evidence
Successor decisions call branch-local baseline/stochastic policy; no repeated hardcoded option-index continuation.

### M08 — Chance outcome handling
Repeated stochastic successor calls are recorded/aggregated rather than overwritten.

### M09 — Multi-determinization aggregation
Canonical root actions aggregate visits/values across at least two legal determinizations.

### M10 — Lifecycle and memory
All native states released; no leaked `searchId`; bounded RSS growth.

### M11 — Match-clock safety
Median/p95/p99 decision and cumulative match search times; fallback counts.

### M12 — Package parity
Repository and clean-extracted MCTS package select identical actions on fixed states.

## ByteRL probes

### B01 — Dynamic option-mask correctness
Unavailable actions have zero probability; legal options sum to one; action index maps to correct canonical option.

### B02 — Recurrent state
LSTM hidden/cell shapes, reset at game boundary, preserved across atomic decisions, detached between unrolls.

### B03 — Actor version/staleness
Behavior policy version, learner version, queue residence, and importance ratios are logged.

### B04 — V-trace numerical reference
Optimized target matches a small independent Python/NumPy fixture.

### B05 — UPGO numerical reference
UPGO returns/loss match hand-calculated fixture and contribute nonzero gradients.

### B06 — Combined loss evidence
Separate policy-Vtrace, UPGO, value, entropy losses and gradient norms; finite updates and changed hashes.

### B07 — Queue/sample reuse
FIFO queue used; actual sample reuse approximately registered value; no uncontrolled replay.

### B08 — OSFP sampling
Observed current-self-play frequency approximates `p`; historical sample frequencies match registered `f`.

### B09 — Payoff table identity
Every G/C cell maps to correct current/historical IDs, seats, and real games.

### B10 — Promotion logic
Synthetic fixtures cover performance promotion, no promotion, and forced max-LP addition; live transitions cite real games.

### B11 — Historical immutability
Promoted checkpoint hashes never change and reload exactly.

### B12 — Training continuation
Report both resume functionality and exact stochastic continuation; do not call unequal hashes exact.

### B13 — Package recurrent parity
Clean package reproduces repository logits/actions/hidden-state transition on fixed sequences.

## Hybrid probes

### H01 — Priors adapter
ByteRL probabilities map to exact canonical MCTS children and normalize correctly.

### H02 — Value calibration
ByteRL value is compared with constant and heuristic evaluators on held-out MCTS leaves.

### H03 — Switchability
Pure MCTS output is unchanged when hybrid adapters are disabled.

## Final/evidence probes

### F01 — Common-panel identity safety
Candidate/opponent/seat/seed mapping is explicit and raw-game-derived.

### F02 — Submission package/source identity
Package manifest references exact source snapshot and hashes.

### F03 — Method-fidelity validator
Rejects c018-style root-only search, option-0 continuation, ordinary PPO-only training, scheduled self-play ramp, unchanged historical checkpoints, fake/virtual games.

### F04 — Complete source bundle
Full final repository and focused branch source open cleanly and contain all entrypoints/configs/tests.
