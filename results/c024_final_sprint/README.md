# c024 — final competition sprint

Ten days of work on one question: **can this project put an agent on the Kaggle ladder that beats
the official Dragapult sample it has been carrying since c005?**

**No.** The sample is the entry. What the contract produced instead is an explanation of *why*
eleven contracts of local optimisation never moved the number, and it is a measurement rather than
an opinion.

## Read in this order

| file | what it settles |
|---|---|
| **`EXECUTIVE_DECISION.md`** | the competitive call and the four findings behind it |
| **`CALIBRATION_RETEST.md`** | the local panel's ceiling is ~960 predicted rating; the leaderboard top is 1233.7 |
| `S0_PUBLIC_AGENT_SCREEN.md` | nine rating-advertising public agents measured on one panel; the panel does not predict a *matchup* (Spearman −0.20) |
| `EXCHANGE_RATE_CORRECTION.md` | c023 ranked the format's best exchange rate 16th of 22 by scoring a printed `0` |
| `S2B_ALAKAZAM_BUILD.md` | our own archetype agent, three defects found by mirror-deck diagnostics, and why it still loses |
| `S2A_FINISH_MODE.md` | a prize tracker that is exactly right, and an override with nothing to correct |
| `LADDER_LOG.md` | every ladder reading, D11, and the open decision left to the user |
| `AUTONOMOUS_PLAN.md` | the standing rules the unattended run executed |
| `STATUS.json` | all of the above recomputed from artifacts by `tools/c024_status.py` |

## The three numbers

| | value | basis |
|---|---:|---|
| champion, converged | **688.5** | 200 episodes — **the honest strength estimate** |
| leaderboard number | 813.9 | a redeployed copy, 36 episodes, still falling from 947.9 |
| our own agent | 505.8 | 26 episodes; the panel predicted 617.5 |

Three byte-identical copies of one agent have read 719.7, 688.5 and 947.9→813.9. **Quote 690.**

## What was built and kept

- `starter_kit/c024_prizes.py` — prize-pile deduction. **0 violations over 233 real prize reveals
  across 83 ladder replays**; the pile is known from turn 2 in 95.2% of decisions.
- `starter_kit/c024_alakazam.py` — a complete from-scratch policy for a 60-card list, 13 select
  contexts, zero illegal actions in 14,432 games.
- `starter_kit/c024_finish.py` — win-this-turn override, correct and measurably inert.
- `tools/c024_prize_oracle.py` — an exact correctness oracle over real replays.
- `tools/c024_handsize.py`, `tools/c024_status.py`, `tools/c024_extract_kernels.py`.
- `tools/c023_package.py::raw_python_check` — **the check that would have caught D11**: runs a
  package by file path, agent against itself, the way the competition actually does.

## The defects this contract found

| | |
|---|---|
| **D8** | the notebook flattener lost cell boundaries, costing four kernel extractions |
| **D9** | a kernel whose entry point is not called `agent`; six errored games read as a weak player |
| **D10** | Kaggle replays record both seats every step and the inactive seat carries stale logs — c023's replay mining counted them as decisions, inflating its per-game counts ~60% |
| **D11** | `kaggle_environments` execs `main.py` with no `__file__`, so **every candidate this project ever packaged was unsubmittable** — and a source fix does not repair candidates already built |

## The finding that outranks the rest

Field score is bounded by 1.0, and the fitted calibration is `rating ≈ 341 + 619 × field`. **A
perfect score on our own panel predicts ~960 against a leaderboard top of 1233.7.** The instrument
saturates below the goal. c023 spent 392,792 games optimising it, and one line of arithmetic on
the fitted slope would have shown the ceiling before any of them were played.

The panel is not broken — it reproduced its own anchor to **0.0002** across ten days and two
contracts, and it ordered every agent correctly. It is a screening instrument that was used as a
target.
