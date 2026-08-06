# c002 Review Findings

These findings define the defects c003 must correct.

## Accepted c002 capabilities

- Runtime asset manifest and verifier
- Side-effect-free unit tests
- Streaming JSONL capture
- Structural validation
- Context and latency reports
- 60-game integration capture
- Honest PARTIAL status
- Improved Git evidence

## Required corrections

1. `game_seed` is misleading because it does not control the cabt engine trajectory.
2. Replay validation must reconstruct the serialized observation and invoke the safe agent.
3. Captures need immutable run, Git, agent, engine, environment, and source lineage.
4. Deck IDs must be order-independent and include the full canonical card multiset.
5. `used_fallback` must describe actual fallback invocation rather than agent identity.
6. Terminal classification must use final state, errors, rewards, and exceptions.
7. Runtime verification must check actual package/runtime versions and architecture.
8. Capture must support `.jsonl.gz`.
9. Schema v1 must remain readable without invented provenance.
10. Observation must be snapshotted before policy invocation.
11. Future policy and deck comparisons require self-describing data.
12. Historical c001/c002 results must not be modified.

## Important platform limitation

Repeated exposed seeds did not reproduce identical cabt trajectories.

c003 must record this honestly and must not claim deterministic engine replay.
