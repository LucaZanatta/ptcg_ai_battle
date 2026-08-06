# Failures

No blocking failures for c004. All 10 acceptance criteria passed.

- 113/113 tests passed (incl. 10 c003-amendment regression tests).
- 4/4 candidates admitted; smoke 40/40 games, 0 defects.
- Gauntlet 400 games; **0 reliability defects** across all candidates (0 invalid
  actions, 0 attributable agent exceptions, 0 timeouts).
- Every unordered pair played in both seat orders; no matchup omitted.
- Bradley-Terry strengths finite under lopsided matchups (regularization).
- Primary/backup selected by the predefined rule; c005 hypothesis grounded in
  3,122 real captured tactical failures.

**Not a failure (recorded honestly):** engine trajectories are non-reproducible
(`std::random_device`); the analysis is reproducible from the fixed capture. And
no strategic agents exist locally, so the candidate pool is a deck×policy
factorial over trivial baselines — the reason the c005 hypothesis proposes the
first strategic step. This file satisfies the mandatory `failures/` directory.
