# c003 — Summary

## Final status
**PASS** — all 9 mandatory acceptance criteria verified. The schema-v2 dataset is
trustworthy for downstream policy evaluation / training-data work.

## What was implemented
- **`starter_kit/episode_schema.py`** — schema-v2 lineage (git/env/engine
  collectors, `implementation_sha256`), order-independent canonical deck registry,
  honest `seed_metadata` (engine RNG never claimed controlled), and
  `classify_terminal` (pure, final-state).
- **`starter_kit/agents.py`** — `AgentDefinition` with policy-owned decision
  provenance (`classify_decision`); safe agent and random baseline identities.
- **`starter_kit/episode_capture_v2.py`** — mutation-safe snapshot **before** the
  policy call, structured provenance, gzip **tee** writer (jsonl + jsonl.gz carry
  a byte-identical stream), final-state terminal records.
- **`starter_kit/episode_compat.py`** — schema-aware streaming reader (v1/v2,
  `.jsonl`/`.jsonl.gz`), rejects unsupported versions, marks v1 provenance
  `legacy_unavailable` without inventing it.
- **`tools/capture_episodes_v2.py`** — lineage-complete 30-game runner (refuses a
  dirty tree for the acceptance dataset).
- **`tools/validate_episodes_v2.py`** — streaming structural + cross-field
  validation and **true semantic replay** (`to_observation_class(obs)` +
  `safe_agent(obs)`), plus context/latency reports.
- **`tools/environment_report.py`** — Python/package/platform/engine verification.

## Tests
**84/84 passed, 0 failed** (`c003` adds 32 tests across 8 modules; c001/c002
tests still pass). Categories: lineage (incl. every-player run-metadata lineage),
deck registry, provenance, semantic replay + 5 corrupt-fixture failures,
mutation-safe snapshot, terminal classification
(normal_win/draw/agent_error/timeout/…), compression, v1 compat.

## Validation dataset
- **30/30 games** completed (10 safe_p0_vs_random, 10 random_p0_vs_safe, 10
  safe_vs_safe; both seats; varying seeds), **1382 decisions**, 0 invalid, 0
  structural errors, all `normal_win`.
- Decision provenance: fallback 966, random_baseline 416. **0 `game_seed`**
  occurrences; `engine_rng_controlled` always false.
- `run_metadata.agents` carries full lineage for **both** players (`safe_agent`
  and `random_baseline`) — no policy identity is a bare display string (§7.3).

## Semantic replay
**966 / 966 safe-agent decisions reproduced exactly** (0 mismatches) on both the
plain and gzip captures, by reconstructing each serialized observation and
invoking the actual safe agent — not by re-checking duplicated bounds.

## Schema-v1 compatibility
The real c002 dataset is detected as **schema 1**; 8 v2-only provenance fields
(`run_id`, `agent_id`, `decision_source`, `fallback_reason`, `record_id`,
`select_context`, plus untrusted `used_fallback`/`game_seed`) are marked
`legacy_unavailable`. A `schema_version:99` record is rejected with a clear error.

## Environment and engine identifiers
- Python 3.13.13 (CPython), platform x86-64, kaggle-environments 1.30.1.
- Engine `starter_kit/libcg.so` sha256 `75d7d619b56e…`, size 1,338,304 bytes.
- Capture git commit `afe52db`, clean (`dirty=false`); implementation_sha256 `84cf87e6a6aa…`.

## Known limitations
- Engine trajectories remain non-reproducible (std::random_device seeding);
  schema v2 records this honestly and never claims deterministic engine replay.
- Runtime context coverage is a subset of the 49 enum contexts (expected).
- draw/timeout/error terminal types are proven via synthetic fixtures (the 30
  real games were all normal_win); classification is a pure function of final state.

## Recommended next contract (c004)
**c004 — schema-v2 decision dataset statistics & context-conditioned baselines**:
build offline analysis over the semantically-replayable v2 episodes
(per-`SelectContext` decision distributions, legal-action structure, latency),
producing the feature/label views a first *strategic* policy (rule or imitation)
would consume — now safe to do because provenance and replayability are trustworthy.
