# Selected Baselines — c004

The selection rule (§8) is implemented as code in `tools/analyze_gauntlet.py`
(`select_baselines`) and applied deterministically to the gauntlet statistics, so
it is fixed before results are inspected.

## Decision

- **Primary baseline: `det_starter`** — deterministic first-`maxCount` policy on
  the starter deck (`deck_id sha256:7e7bca6783…`, agent `c004.1`).
- **Backup baseline: `det_cabt`** — deterministic first-`maxCount` policy on the
  cabt built-in deck (`deck_id sha256:53ada9d42d…`, agent `c004.1`).

## Ranking (regularized Bradley–Terry, 400 gauntlet games)

| rank | candidate | BT strength | bootstrap 95% CI | P(rank 1) | reliability | worst-matchup LB |
|---|---|---|---|---|---|---|
| 1 | det_cabt | 2.426 | [1.93, 3.20] | 0.54 | eligible (0 defects) | 0.425 (vs det_starter) |
| 2 | det_starter | 2.415 | [1.91, 3.19] | 0.46 | eligible (0 defects) | 0.435 (vs det_cabt) |
| 3 | random_starter | 0.610 | [0.44, 0.81] | 0.00 | eligible (0 defects) | — |
| 4 | random_cabt | 0.280 | [0.18, 0.39] | 0.00 | eligible (0 defects) | — |

## Why det_starter is primary (not the nominal BT #1)

`det_cabt` has the marginally higher BT point estimate, but the two deterministic
candidates are **statistically tied**: their bootstrap strength intervals overlap
almost entirely and their head-to-head over 200 games is `0.495` (95% CI
`[0.43, 0.56]`, i.e. a coin flip). Per the predefined rule, when the leaders'
95% intervals substantially overlap, the tiebreak is the **higher conservative
worst-matchup lower bound**: `det_starter` = **0.435** > `det_cabt` = **0.425**.
(P99 latency and determinism were the next tiebreakers but were not needed.)
`det_cabt` is therefore the backup. Both are deterministic, so the pair also
provides no policy diversity — noted as a limitation.

## Evidence
- Strength: `bradley_terry_ranking.json`, `bootstrap_ranking.json` (2000 resamples).
- Robustness: `worst_matchups.json`, `pairwise_intervals.json`.
- Reliability: `reliability_report.json` — **all four candidates 0 defects** (0
  invalid actions, 0 attributable agent exceptions, 0 timeouts across 400 games).
- Latency: `latency_report.json` — P99 ≈ 0.003 ms (deterministic), ≈ 0.01 ms (random).
- Seat effect: overall seat-0 win rate `0.54` (mild first-player advantage);
  `seat_effects.csv`.
- Uncertainty: strengths are point estimates with bootstrap 95% intervals; the
  primary/backup gap over the field (det ≫ random: balanced 0.78–0.90) is large
  and stable, while the primary/backup order itself is within noise.

## Weak matchups
`det_starter`'s only non-dominant matchup is the backup `det_cabt` (balanced
`0.505`, essentially even). Against both random candidates it wins decisively
(`0.775` vs random_starter, `0.900` vs random_cabt). It has **no** reliability
defect against any opponent.

## Rejections
- `random_starter` — `REJECTED_STRENGTH` (BT strength 0.610; loses to both det candidates).
- `random_cabt` — `REJECTED_STRENGTH` (BT strength 0.280; weakest overall).

## Frozen identities (for c005)
- Primary: `det_starter` / deck `sha256:7e7bca6783…` / adapter `starter_kit/candidates.py`.
- Backup: `det_cabt` / deck `sha256:53ada9d42d…` / adapter `starter_kit/candidates.py`.
