# We have been competing in the track with no prize

**Found 2026-08-16, hours before the simulation deadline.** This is the single most valuable thing
this campaign has produced, and it is an intelligence failure that should have been caught in
June.

## The two tracks

| | **Simulation** (what we entered) | **Strategy** (what we did not) |
|---|---|---|
| Kaggle ref | `pokemon-tcg-ai-battle` | `pokemon-tcg-ai-battle-challenge-strategy` |
| reward field, per the API | **"Knowledge"** | **"240,000 Usd"** |
| teams | **6,841** | **388** |
| deadline | 2026-08-16 23:59 UTC (today) | **2026-09-13 23:59 UTC** |
| our submissions | 8 | **0** |

**Top 8 teams in the Strategy track receive $30,000 each** and advance to a second round
(winner $50,000, runner-up $30,000). 388 teams competing for 8 paid places is a base rate of
about 1 in 48 — against 1 in 855 for a top-8 finish in the simulation track, where we are
1,414th.

## What the Strategy track actually asks for

- A **written report, capped at ~2,000 words**, submitted as a Kaggle Writeup with a media
  gallery, explaining the strategic logic, deck concept and design decisions behind the agent.
- **Entry in the Simulation track is a prerequisite.** We have that — eight submissions, the
  most recent validated and playing.
- Reported scoring weights: **model approach 70%, deck concept 20%, report quality 10%**, with
  simulation performance also a factor. Sources agree on the structure; the exact percentages come
  from one secondary source and should be verified against the competition's own rules page before
  being relied on.

## Why this matters more than our ladder rank

The simulation track scores one number and we are 526 rating points behind the top of it. That is
not recoverable. **The Strategy track is judged mostly on the quality of the approach**, and the
approach is the part of this project that is actually strong:

- **~407,000 measured games** across c023 and c024, one harness, identity-carrying records, zero
  unexplained errors.
- **A calibration between local evaluation and Kaggle rating** (R² = 0.987 in sample), its
  **out-of-sample failure** (≈ −115 rating on a new archetype), and the **ceiling result** — a
  perfect score on our own panel predicts ~960 rating against a leaderboard top of ~1,268. That is
  a genuine methodological finding about how to measure agents in this environment, and it is not
  in any public notebook.
- **Four named, reproduced defects**, including D11: `kaggle_environments` `exec`s `main.py`
  without `__file__` in scope, so **every candidate this project packaged before 2026-08-13 would
  have died on its validation episode having played zero cards.** Any team building a wrapper
  architecture has this bug and does not know it.
- **A prize-card tracker validated by an exact oracle** — 0 violations over 233 real prize reveals
  across 83 ladder replays, prize pile known from turn 2 in 95.2% of decisions.
- **A negative result with a mechanism**: 28 candidates, five branches, no promotion, and a
  measured explanation (the objective saturates below the target) rather than five shrugs.

A report that says *"here is the instrument everyone is optimising, here is the arithmetic proof
it cannot reach the target, and here is the deployment bug that silently kills wrapper agents"* is
a stronger strategy submission than one that says "we tuned our heuristics and reached 1100".

## How this was missed

`competitions_list(search='pokemon')` returns both competitions with their `reward` fields, and
this campaign called that endpoint on 2026-08-13 to read the deadline — and read only the deadline.
The prize field was on screen and went unexamined. Eleven contracts optimised a Knowledge
competition while a $240,000 track with one-eighteenth the field sat unentered.

**The lesson is not "search harder".** It is that no contract in this project ever asked *what
exactly are we being scored on, and is that the thing with the reward attached?* Every contract
took the objective as given. That question belongs at the top of the next one.

## What to do, in order

1. **Today (before 23:59 UTC):** nothing changes for the simulation deadline. The entry is
   submitted and playing; the close proceeds as planned.
2. **Verify the rules first.** Read the Strategy competition's own rules and evaluation pages —
   eligibility, whether the Aug 16 simulation deadline gates Strategy entry, the real rubric, team
   registration. The secondary sources agree with each other but they are not the rules.
3. **Then write the report.** Four weeks is ample for 2,000 words when the evidence already
   exists. The work is selection and presentation, not new experiments.
4. **Do not restart agent development for it.** The report is scored on approach, and our approach
   is documented. Marginal ladder points will not move a 70%-approach rubric.

*(Sources: Kaggle competitions API `reward` and `deadline` fields, read directly; corroborated by
two independent secondary reports of the prize and deadline structure.)*
