# The panel's ceiling is below the target, and that explains five branches of null results

`LADDER_CALIBRATION.md` is this project's central methodological claim: the local 13-player panel
predicts Kaggle rating with **R² = 0.9872**, via `rating = 347.5 + 646.7 × field`. It was fit on
four agents, all of which were **in** the fit. Nothing had ever tested it out of sample.

c024 provides the test — a new archetype, an agent we wrote, that did not exist when the line was
drawn — and adds a converged rating for the anchor point.

## First, the panel reproduces itself exactly

| | `LADDER_CALIBRATION` (2026-08-03) | c024 re-measurement (2026-08-13) |
|---|---:|---:|
| `official_dragapult`, 13-panel field | **0.5708** | **0.5710** |
| games | 2,400 | 2,400 |

Ten days, two contracts, two independently-assembled evaluation runs, and the same agent scores
the same field to within **0.0002**. The instrument is *precise*. That is worth stating plainly
before everything below, because what follows is not a claim that the panel is noisy.

## Then it fails out of sample by 102 rating points

| agent | 13-panel field | episodes | rating | predicted | residual |
|---|---:|---:|---:|---:|---:|
| `official_dragapult` | 0.5710 | 200 | 688.5 | 716.6 | −28.1 |
| `official_mega_lucario` | 0.3952 | 273 | 595.1 | 603.0 | −7.9 |
| c014 Archaludon | 0.1583 | 33 | 471.4 | 449.8 | +21.6 |
| c015 anti-meta | 0.0900 | 119 | 393.2 | 405.7 | −12.5 |
| **c024 Alakazam (ours)** | **0.4177** | **24** | **497.6** | **617.5** | **−119.9** |

The four fitted points sit within ±22. **The one point that was not in the fit misses by −120** —
five times the worst in-sample residual.

Two qualifications, both real:

- **24 episodes is not a converged rating.** The other points have 119–273. But the direction is
  not reassuring: its score rate is 0.360 and falling, so the residual is more likely to grow than
  to shrink.
- **The original fit used under-converged ratings.** `official_dragapult` was entered at **719.7**
  on 83 games; over 200 games the same agent settles at **688.5**. Refitting on the three points
  with 100+ episodes gives `rating = 340.9 + 619.2 × field`, which moves the prediction only to
  599.6 — so the miss is not an artifact of the old fit.

**What survives is the ordering.** The panel ranked our Alakazam agent below the champion
(0.4177 against 0.5710) and the ladder agrees (497.6 against 688.5). Every archetype-level
decision this campaign made on panel evidence was directionally right. What does not survive is
the *level*: the panel cannot say how much rating a local point is worth for an agent unlike the
ones it was fitted on.

## The finding that matters more: the instrument is bounded below the goal

Field score is a mean over per-opponent score rates, so it **cannot exceed 1.0**. Under the refit:

| local field | predicted rating |
|---:|---:|
| 0.5710 (our champion) | 694.5 |
| 0.75 | 805.3 |
| 0.90 | 898.2 |
| **1.00 — beat all twelve opponents in every game** | **960.1** |
| | |
| leaderboard P99 | 1026.0 |
| **leaderboard top** | **1230.3** |

**A perfect score on this panel predicts ~960, and the top of the leaderboard is 1230.** The
instrument's maximum reading sits below the target — not near it, *below* it, by more than the
entire distance from our champion to a flawless panel score.

That is the mechanism behind c023's negative result, and it is a better explanation than any of
the five branch-level ones. Five branches, 28 candidates and 392,792 games optimised a quantity
whose ceiling is roughly the 93rd percentile. No amount of search over that objective reaches the
top of this leaderboard, because the objective saturates first.

It also reframes what the panel is *for*. It is an excellent **screening** instrument — precise to
0.0002, ordering agents correctly across a 300-point rating range — and it is not a **target**.
A campaign that wants the top of this leaderboard has to optimise against opponents stronger than
any on this panel, which in practice means the ladder itself, at five submissions a day, with a
day of latency per reading.

## What should have been done differently

The panel was built in c016 and extended in c023 from official samples plus the most-voted
community kernels. Nothing in its construction targeted the *top* of the ladder — and
`S0_PUBLIC_AGENT_SCREEN.md` later found public agents advertising 1050–1300 that were never on it.
Had the ceiling been computed at the time — one line of arithmetic on the fitted slope — it would
have been clear before c023 spent 392,792 games that the instrument could not measure the thing
the contract was asking for.
