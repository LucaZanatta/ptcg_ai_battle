# Failures

No blocking failures for c005. All 13 acceptance criteria passed.

- 119/119 tests passed.
- 4 real strategic teachers acquired (official reusable samples) + 1 public
  benchmark (no license, classified LOCAL_BENCHMARK_ONLY, not admitted).
- Smoke: 80 games, 0 defects; Gauntlet: 720 games, **0 reliability defects**.
- Submission A archive built + validated from the extracted archive (20 games,
  0 invalid, 0 non-terminal) → decision SUBMIT (upload gated behind absent flag).
- Dataset: 240 games / 19,050 teacher decisions, 0 excluded, no leakage, unique ids.
- No third-party code or credentials committed.

## Recorded caveats (not failures)
- Competition rules text was not machine-retrievable (JS-rendered page); handled
  conservatively (official-sample provenance basis; upload gated behind the absent
  `PTCG_ALLOW_KAGGLE_SUBMIT` flag). See `rules_and_reuse_audit.md`.
- Engine trajectories are non-reproducible (`std::random_device`); the analysis
  and dataset splits are reproducible from fixed captures.

This file satisfies the mandatory `failures/` directory.
