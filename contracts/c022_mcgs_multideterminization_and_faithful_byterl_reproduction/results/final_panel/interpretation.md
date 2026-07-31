# The final panel — candidates and the frozen bar, on one panel

60 games per candidate, 180 total, all scored. Same opponents, same seats, same seeds, same
count-budgeted configuration. `DECISION_RULES §2` requires `MCGS_COMPETITIVE=PASS` to show a
candidate that "credibly beats the strongest frozen local champion on the broad panel".

| candidate | field score | Wilson 95% | dragapult | mega_lucario | iono | mega_abomasnow |
|---|---:|---|---:|---:|---:|---:|
| `baseline` (frozen bar) | **0.5833** | [0.457, 0.699] | 0.533 | 0.467 | 0.867 | 0.467 |
| `mcgs_k1` | 0.1333 | [0.069, 0.242] | **0.000** | 0.533 | **0.000** | **0.000** |
| `mcgs_k8` | 0.1167 | [0.058, 0.222] | **0.000** | 0.467 | **0.000** | **0.000** |

## The bar re-run agrees with its own record to 0.04 pp

`BASELINE_OFFICIAL_MEGA_LUCARIO` is recorded in `control_manifest.json` at **0.5837** on the c020
panel. Re-run here over c022's four opponents it scores **0.5833**.

That agreement is the reason the bar was re-run instead of quoted. Two field scores from
different panels are not comparable — putting c020's 0.5837 beside c022's 0.1650 would have been
the position-pairing defect family in a new costume — and the only way to know the panels agree
is to measure it. They do, which means the 45-point gap below is a real gap and not an artifact
of two different measuring sticks.

## `MCGS_COMPETITIVE` = PARTIAL, and there is no submission

The gap is **45.0 pp** with intervals nowhere near touching. `DECISION_RULES §2` offers a second
route to PASS — "a strong complementary matchup profile with no unacceptable broad-field
regression" — and this is its opposite:

**The corrected search wins zero of 45 games against three of the four opponents.** Its entire
score comes from the `mega_lucario` mirror, where it plays the same archetype as its opponent.
That is not a complementary profile; it is a single matchup carrying an agent that has no answer
to the rest of the field. `DECISION_RULES §5` therefore forbids a submission, and none is made.

## K=8 does not beat K=1 here either

`mcgs_k1` scores 0.1333 and `mcgs_k8` scores 0.1167 — the ensemble is nominally *behind*, well
inside the measured 5.0 pp replication floor. Consistent with
`FINDING_the_calibration_gain_is_compute.md`: at equal simulations the eight-world ensemble
contributes 1.2% of the calibration improvement and nothing detectable in field strength.

Note this panel is count-budgeted at 12 simulations per world, so `mcgs_k8` spends 8x the
simulations of `mcgs_k1` and still does not lead. That is a stronger statement than the paired
arms made, and it points the same way.

## What this panel does not settle

- It is **count-budgeted**, so it does not measure deployment strength. That is
  `M12_DEPLOY.md`, which runs alone under c021's 90 s clock and finds the same ordering with the
  opposite sign on K (`deploy_k8` 0.233 balanced against `deploy_k1` 0.125) — an inconsistency
  between the two regimes that 40 and 60 games cannot resolve and that is recorded rather than
  explained away.
- 60 games per candidate gives a ~12 pp interval. It is ample for a 45 pp gap and useless for
  the 1.7 pp between the two candidates.
- The MCGS agent plays one fixed archetype. Whether its 0-for-45 record reflects the search or
  the decklist is not separated by this panel, and the deck was held fixed precisely so that K
  would be the only difference between the two candidates.
