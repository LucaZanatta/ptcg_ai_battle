# c021 — summary

Generated 2026-07-29T11:23:41. Statuses are computed in `tools/c021_report.py` from evidence on disk; a missing input yields FAIL or PARTIAL with a reason, never a pass by default.

| Status | Value |
|---|---|
| `SOURCE_FIDELITY` | **PASS** |
| `EXECUTION` | **PASS** |
| `MCGS_COMPETITIVE` | **FAIL** |
| `BYTERL_METHOD` | **PARTIAL** |
| `BYTERL_SCALE` | **COMPUTE_LIMITED** |
| `TRANSFER` | **FAIL** |
| `PACKAGE` | **NOT_BUILT** |
| `SUBMISSION` | **PENDING** |
| `OVERALL` | **PARTIAL** |

## What was built

- **MCGS_2019_OFFICIAL_SOURCE_PORT** — the 2019 winner's graph search: UCB1 (not PUCT), edge statistics, a transposition DAG with dummy edges, damped sampling, the inert UCD recursion reproduced rather than fixed, and a uniform-random rollout to a real terminal.
- **MCGS_2019_PTCG_LEGAL_CORRECTED** — separately named; multi-select actions as SETS, a structural category filter, obliged-action collapse.
- **ByteRL** from fresh random weights — V-trace, UPGO, OSFP with period-local payoffs and immutable history, autoregressive masked multi-select, distinct active/bench slot tokens, and end-to-end deck construction plus battle.
- **Transfer lab** — one component per arm, no uncontrolled hybrid, no third method.
- **Semantic validator** — 17 checks, each proven to detect its own injected defect.

## The load-bearing findings

1. **The PTCG search API fixes hidden information at `search_begin`** and offers no way to re-determinize an interior node, so the source's interior chance types have no counterpart. Established by probe, not assumed.
2. **`yourIndex` lives on `observation.current`.** Reading it from the top level made `is_opponent` False at every node, so the search never flipped the reward sign and assumed a cooperating opponent.
3. **The only chance surface is `SelectContext.COIN_HEAD = 46`.** Two behavioural probes wrongly indicted contexts 4 and 5 (`TO_ACTIVE`, `TO_BENCH`); the engine's enum settled it. Where the engine publishes an enum, the enum is the authority.
4. **A latency-bounded search must be measured alone.** Orphaned pool workers were measured stealing seven cores at 99% CPU each, silently depressing simulation counts.
5. **At this scale no ByteRL rung separates from the uniform-random floor.** That is the honest compute-limited reading, reported as such.

