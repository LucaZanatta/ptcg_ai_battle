# c004 — Summary

## Final status
**PASS** — 10/10 acceptance criteria. A primary and backup competitive baseline
were selected by a predefined, code-implemented rule over a reproducible gauntlet.

## c003 amendment status
All three Phase-0 amendments applied with regression tests (10 tests), existing
c003 suite still green (113 total), and the frozen c003 dataset re-validates 0
errors / 966-of-966 replay under hash-verification:
1. terminal error extraction from the **final** step (not step 0);
2. `legal_option_metadata == observation.select.option` equality check;
3. replay registry verifying agent id/version/source-hash before invoking.

## Candidates
Discovered/admitted **4** (a policy × deck factorial — the only complete
baselines available locally; no strategic agents exist here):

| candidate | policy | deck | admitted |
|---|---|---|---|
| det_starter | deterministic first-`maxCount` | starter | ✅ |
| det_cabt | deterministic first-`maxCount` | cabt built-in | ✅ |
| random_starter | uniform random legal | starter | ✅ |
| random_cabt | uniform random legal | cabt built-in | ✅ |

Rejected (post-gauntlet, by rule): `random_starter` and `random_cabt` →
`REJECTED_STRENGTH`.

## Games
- Smoke: **40** (10/candidate, seat-balanced) — all completed, 0 defects.
- Gauntlet: **400** across 6 unordered pairs, both seat orders, sequential
  stratified-bootstrap stopping (4 pairs stopped at 40; the two close pairs ran
  further, det/det to the 200 cap).

## Ranking & uncertainty (regularized Bradley-Terry, 2000-resample bootstrap)
| rank | candidate | BT strength | 95% CI | P(rank 1) |
|---|---|---|---|---|
| 1 | det_cabt | 2.426 | [1.93, 3.20] | 0.54 |
| 2 | det_starter | 2.415 | [1.91, 3.19] | 0.46 |
| 3 | random_starter | 0.610 | [0.44, 0.81] | 0.00 |
| 4 | random_cabt | 0.280 | [0.18, 0.39] | 0.00 |

Deterministic ≫ random (balanced 0.78–0.90). The two deterministic candidates are
statistically tied (head-to-head 0.495, CI [0.43, 0.56]).

## Selected baselines
- **Primary: `det_starter`** (deck `sha256:7e7bca6783…`, agent `c004.1`).
- **Backup: `det_cabt`** (deck `sha256:53ada9d42d…`, agent `c004.1`).

`det_cabt` has the marginal BT-point lead, but the leaders' intervals overlap, so
the predefined tiebreak (higher conservative worst-matchup lower bound:
`det_starter` 0.435 > `det_cabt` 0.425) selects `det_starter` as primary.

## Worst matchups
Primary `det_starter`'s only non-dominant matchup is the backup `det_cabt`
(balanced 0.505, LB 0.435 — essentially even). It beats both random candidates
decisively and has no reliability defect against any opponent.

## Reliability defects
**Zero** across all four candidates over 400 gauntlet games — 0 invalid actions,
0 attributable agent exceptions, 0 timeouts. All four are reliability-eligible.

## Latency
P99 decision latency ≈ **0.003 ms** (deterministic), ≈ **0.01 ms** (random). All
negligible; well within any budget.

## c005 policy hypothesis
For the unchanged `det_starter`: it **declines a legally-available ATTACK in 3,122
of 5,774 MAIN decisions (54%)** because it takes the first option positionally.
Proposed c005: a minimal MAIN-context attack-preference scorer (choose the
best legal attack when available), evaluated against the frozen c004 field, kept
only if its win rate vs the unchanged baseline has a 95% bootstrap CI above 0.55
with zero new reliability defects. Not implemented in c004.

## Known limitations
- No strategic agents exist locally; primary and backup are both deterministic
  (no policy diversity) — the factorial is over the only complete baselines.
- Primary/backup order is within statistical noise, resolved by the predefined
  tiebreak.
- Engine trajectories are non-reproducible (recorded honestly); the *analysis*
  is reproducible from the fixed capture.

## Recommended next contract
**c005** — implement and evaluate the MAIN attack-preference hypothesis above
against the frozen c004 baseline, under the c004 gauntlet protocol.
