# What we did, what failed, and why

Twenty-four contracts, **407,224 measured games**, eight Kaggle submissions, two months. The best
agent this project ever produced is **the official sample it was given on day one**.

This document is the honest account of why. It is organised by failure, because the failures are
what the evidence actually supports and because a list of things that were built would be a
misleading record of a campaign that did not achieve its objective.

---

## The result, stated plainly

| | |
|---|---|
| objective | beat the official Dragapult sample on the Kaggle ladder |
| agents built | ~30 across c014–c024 |
| agents that beat the sample | **0** |
| final standing | **1,414th of 6,841** (79th percentile) |
| gap to the top | **526 rating points** |
| champion's converged strength | **688.5** over 200 episodes |
| the champion | `official_dragapult`, byte-for-byte, unmodified |

Every rating point this project holds came from **choosing which sample to submit**, not from
anything it built.

---

## Failure 1 — We optimised an objective that cannot reach the goal

**This is the one that explains the other four.**

Eleven contracts measured strength as a *field score* against a local panel of opponents. c023
fitted that to Kaggle rating and got `rating ≈ 341 + 619 × field`, R² = 0.987 — and treated the
fit as a licence to optimise field score.

Field score is a mean of win rates. **It cannot exceed 1.0.** So:

| local field | predicted rating |
|---:|---:|
| 0.571 (our champion) | 694 |
| 0.90 | 898 |
| **1.00 — beat every opponent, every game** | **960** |
| **leaderboard top** | **1,268** |

**A perfect score on our own instrument lands 308 points below the target.** c023 spent 392,792
games searching for a maximum of a quantity that saturates around the 93rd percentile.

The arithmetic is one line on the fitted slope. It was computable the day the calibration was
written and nobody computed it — because the calibration was treated as a *validation* of the
panel rather than as a *description of its range*.

**Why it happened:** every contract inherited the objective from the previous one. No contract
ever asked "is this quantity capable of expressing the answer?"

---

## Failure 2 — We maximised the mean when the ladder rewards the minimum

Found on the last day, and it retires the whole search framing.

A matchup matrix defines a zero-sum game. Solving ours for its Nash equilibrium (10 agents, both
orientations pooled, ≥30 games per cell):

| agent | equilibrium weight | **worst matchup** |
|---|---:|---:|
| `pub_tetsutani_grimmsnarl` | **0.714** | **−0.062** |
| `official_mega_abomasnow` | 0.184 | −0.725 |
| `official_iono` | 0.102 | −0.688 |
| **`official_dragapult` (ours)** | **0.000** | −0.426 |
| `official_mega_lucario` | 0.000 | −0.811 |

Grimmsnarl's *worst* matchup on the entire panel is −0.062 — 46.9% against its own best counter.
**It is the only deck measured here that cannot be counter-picked.** Our champion scores −0.271
against the equilibrium mixture, third-worst of ten.

That is why Marnie's Grimmsnarl is 58.8% of the 1100+ band: **not because it beats everything, but
because nothing beats it badly.** On a ladder where you submit one fixed agent and meet whatever
arrives, the binding quantity is the worst cell, not the average. A field score averages exactly
that information away — two agents with identical means can differ by 40 points in worst case, and
c023's search could not distinguish them.

**Why it happened:** the technique is standard in the collectible-card-game literature and takes
twenty lines of `scipy.optimize.linprog` over a matrix we had already measured. It was never
applied because no one asked what *shape* of objective the environment rewards.

---

## Failure 3 — Everything we built was unsubmittable, and nothing could have told us

`kaggle_environments` does not import `main.py`. It reads the source and `exec`s it in a namespace
with **no `__file__`**. Any module-level `os.path.abspath(__file__)` raises before the agent
function exists.

**All 28 c023 candidates carried that line.** Every one would have died on its Kaggle validation
episode having played zero cards. We discovered it only because c024 actually submitted one
(`55466460` — status ERROR, zero games played).

Two independent gaps let it through:

- **Our loader used `spec_from_file_location`, which *does* set `__file__`.** ~400,000 games of
  local measurement ran agents through a loading path the competition does not use. Correct for
  comparing agents to each other; useless for predicting whether one starts.
- **No evaluation ever played a candidate against itself** — which is exactly what Kaggle's
  validation episode is. Every run used `--skip-self`.

It has a second layer: the wrapper is copied into each candidate at *build* time, so fixing the
source repaired nothing already built. A source fix is not an artifact fix.

**Why it happened:** c023 reported that candidates were "packaged and validated for submission."
They were validated against our own harness, which differs from the deployment target in exactly
the way that mattered. **Nothing was ever validated end-to-end against the real thing until we
submitted one.**

---

## Failure 4 — We read the competition's own metadata and missed the prize

`competitions_list(search='pokemon')` returns two competitions:

| | entered | not entered |
|---|---|---|
| `pokemon-tcg-ai-battle` | ✅ 8 submissions | |
| `...-challenge-strategy` | | ❌ **0 submissions**, reward **$240,000**, 388 teams |

This campaign called that exact endpoint on 2026-08-13 to read a deadline, and read only the
deadline. The `reward` field was in the same response.

**Why it happened:** the same reason as Failure 1. No contract in twenty-four ever asked *what
exactly are we scored on, and is that the thing with the reward attached?* The objective was
inherited, never audited.

---

## Failure 5 — Two methods were pursued far past the point their own evidence closed them

- **MCGS / ISMCTS (c019–c022).** Measured field 0.13 against the sample's 0.58. Eight times the
  simulations bought **+0.75 points**. The reference design assumes ~600 simulations per decision;
  the Kaggle clock buys **44**. c022 also showed the proposed hidden-information fix contributed
  **1.2%** of the calibration gain it claimed — simulations in a single world delivered the rest.
- **ByteRL (c019–c022).** Reached ~10% of matched training compute and never separated from its
  floor.

Both were carried across four contracts. The numbers that closed them were available in the first.

**Why it happened:** contracts were written to *implement a method faithfully* and report fidelity
separately from strength. That is good discipline for a research record and it is a poor stopping
rule — fidelity kept passing while strength kept failing, and the campaign read the passing status.

---

## What actually worked

Short list, honestly scoped:

- **The evaluation harness.** Fork-per-game, identity-carrying records, 407,224 games with 10
  accounted errors. When the engine aborts, it becomes a recorded outcome instead of a hung pool.
- **The prize tracker** (`c024_prizes.py`). Deduces the prize pile exactly, refuses when ambiguous.
  Validated by an exact oracle over 83 real ladder replays: **0 violations in 233 real prize
  reveals**, pile known from turn 2 in **95.2%** of decisions.
- **Measured elimination of whole hypothesis classes.** "We miss lethal lines" — finish-mode search
  found 8 winnable lines in 60 games and the expert was already taking all 8. "We decline attacks"
  — 0.043 per game. Both closed by measurement rather than argument, which is worth more than the
  rules that were tried and failed.
- **The rating-variance finding.** Three byte-identical copies of one agent read **719.7, 688.5 and
  947.9→745**. Ratings before ~100 games describe the sample, not the player. Every headline number
  this project ever quoted — 788.1, 719.7, 947.9 — was an under-converged reading.

---

## The four lessons, in the order I'd apply them

1. **Audit the objective before optimising it.** Compute the maximum your metric can express and
   compare it to the target. If the ceiling is below the goal, no search fixes it.
2. **Optimise the worst case, not the mean**, in any environment where a fixed choice meets an
   adversarially-distributed field. Solve the matchup matrix; it costs twenty lines.
3. **Validate against the deployment target, not against your own harness.** One real submission on
   day one would have caught D11 and saved 28 candidates' worth of false confidence.
4. **Re-read what you are being scored on, periodically.** Not once at the start — the campaign's
   most expensive error was a field in an API response nobody looked at twice.

---

## The single sentence

*We built a rigorous measurement apparatus, pointed it at a quantity that could not reach the
target, never checked that our artifacts could run where they were going, and never noticed the
prize was in the other competition.*
