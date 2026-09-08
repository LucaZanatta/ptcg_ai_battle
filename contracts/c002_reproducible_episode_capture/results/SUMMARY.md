# c002 — Summary

## Objective
Turn the c001 deterministic safe agent into a reproducible, inspectable platform:
a runtime-asset manifest + verifier, side-effect-free tests, versioned JSONL
episode capture, a streaming round-trip validator, seed/seat discipline, and a
context/latency coverage report — with executed evidence.

## Status
**PARTIAL (7/8).** All platform capabilities are implemented and verified;
AC-04's reproducibility clause is only partially satisfiable because of an
external engine limitation (below).

## Implemented capabilities
- **Runtime asset manifest** (`runtime_assets.json`) + **verifier**
  (`tools/verify_runtime_assets.py`): presence/type/symlink/sha256, PASS/FAIL
  table, JSON mode, nonzero exit on missing required assets.
- **Reproducibility docs** (`REPRODUCIBILITY.md`): exact verify/test/one-game/
  capture commands; tracked vs external vs generated asset split.
- **Side-effect-free tests**: c001 tests no longer write into contract results;
  running the suite twice changes no tracked/historical file.
- **Versioned episode capture** (`starter_kit/episode_capture.py`, schema v1):
  `game_start` / `decision` / `game_terminal` JSONL, JSON-safe observation
  normalization, deterministic per-game seed derivation, behaviour-preserving
  capture wrapper. Runner `tools/capture_episodes.py` (3 cohorts, seed/seat
  discipline, replay-check mode).
- **Streaming validator** (`tools/validate_episode_jsonl.py`): schema, ordering,
  index bounds, terminal-vs-decision counts, record-level policy determinism.
- **Coverage report** (`tools/context_coverage_report.py`): enum vs runtime
  context coverage, per-seat/fallback/invalid counts, per-context latency.

## Runtime asset policy
Git-tracked: my source/config/tests/tools (integrity via Git). External
(untracked, declared with sha256 in the manifest): the starter-kit files
`api.py`, `sim.py`, `game.py`, `utils.py`, `__init__.py`, `deck.csv`, the native
`libcg.so` (also `.gitignore`d as `*.so`), the `cg`/`starter_kit/cg` symlinks,
and the `kaggle-environments` `cabt` env. A clean checkout obtains the externals
per `REPRODUCIBILITY.md` and confirms them with the verifier.

## Episode schema overview (v1)
Per game: one `game_start` (game_id, cohort, seed, seat assignment, agents,
decks) → N `decision` records → one `game_terminal` (winner, terminal reason,
per-player decision counts, invalid count, duration). Each `decision` carries
schema_version, game_id, decision_index, player_index, seat, game_seed,
agent_name, deck_identifier, monotonic timestamp, full normalized observation
(+ omitted-field list), context name/value, legal option count + metadata,
min/max count, selected indices, policy latency (ns), used_fallback, and
validation status. Deck-selection calls are captured at game level, not as
bounded decision records. JSON only — no pickle; UTF-8.

## Integration results
60/60 games completed, 0 failed, **0 invalid safe selections**, 60 unique seeds,
2,553 JSONL records (2,433 decisions). Cohorts: safe-vs-safe 20/20,
safe-p0-vs-random 20/20, random-p0-vs-safe 20/20. Round-trip validation: 0
errors. All 2,433 decision records serialized the full observation with **0
omitted fields**, and `legal_option_count == len(legal_option_metadata)` in
**2,433/2,433** records (so record-level policy replay from recorded bounds is
equivalent to replay from the observation). (Win rates are not treated as
strategic evidence, per the review.)

## Context coverage result
Enum-defined contexts: 49 (all present in the report, 38 zero-count). Runtime
observed: 11 (22.4%) — MAIN, SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON,
TO_ACTIVE, TO_HAND, ATTACH_FROM, ATTACH_TO, DRAW_COUNT, IS_FIRST, and two more.
Enum vs runtime coverage are reported as distinct, per the c001 review.

## Known limitations
- **AC-04 reproducibility (engine, external):** decision counts and winners do
  not reproduce across runs because `libcg.so` seeds `std::mt19937` from
  `std::random_device` (no seed API; `configuration.seed` ignored). Seeds, seat
  schedule, and record-level safe decisions (157/157) DO reproduce. See
  `failures/AC04_engine_nondeterminism.md`.
- Runtime context coverage is a subset (11/49) — expected for sampled games.
- Starter-kit runtime files remain external assets (declared, not committed).

## Recommended next contract
**c003 — narrow AC-04 repair**: redefine reproducibility as record-level
determinism (seeds + seat schedule + per-observation policy), which is fully
achieved, decoupling it from the unseedable engine trajectory. Then proceed to
episode-driven analysis (e.g., context-conditioned statistics) built on this
captured dataset.
