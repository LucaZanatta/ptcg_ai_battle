# c024 — executive decision

**Status at 2026-08-13 11:00 UTC, three days before close.** Written before the deadline rather
than after it, so the competitive call is on record ahead of the outcome.

## The decision

**`official_dragapult` — the Kiyota sample, byte-for-byte — is the entry.** No agent this project
has built beats it, including the one built in this contract. A copy is live on the ladder
(`55478202`) and a copy stays live through the close.

## The numbers, stated three ways because they differ

| | value | what it is |
|---|---:|---|
| champion, **converged** | **688.5** | 200 episodes, 94W–107L. The honest strength estimate. |
| best submission **right now** | 810.6 | `55478202`, 33 episodes, still falling from 947.9 |
| previous frozen best | 719.7 | the same agent, frozen at 83 episodes in July |

Rank at each: 2,360th / 907th / 1,840th of 6,791. **The spread across three byte-identical copies
of one agent is 122 rating points and 1,450 leaderboard places, and none of it is skill.**

Any honest reading of this campaign quotes **~690**. The leaderboard number is whatever the most
recently frozen lucky draw happens to be.

## Four findings, in order of what they cost to learn and what they are worth

### 1. The measuring instrument's ceiling is below the target

`CALIBRATION_RETEST.md`. The 13-player panel predicts rating as `≈341 + 619 × field`, and field
is a mean of score rates so it cannot exceed 1.0. **A perfect panel score predicts ~960. The
leaderboard top is 1233.7.**

The panel is *precise* — it reproduced its own anchor to 0.0002 across ten days and two contracts
— and it orders agents correctly across a 300-point range. It is a screening instrument, not a
target, and c023 used it as a target for 392,792 games. **That is a better explanation of that
campaign's null result than any of its five branch-level ones**, and it was computable from the
fitted slope before a single game was played.

It also failed its first out-of-sample test: our new agent was predicted at 617.5 and is at
497.6, a −120 residual against ±22 for the four agents inside the fit.

### 2. The archetype thesis was right about the mechanism and wrong about the payoff

`EXCHANGE_RATE_CORRECTION.md` found a real error in c023's closing analysis: Powerful Hand places
two damage counters *per card in hand* — 20 damage a card, unbounded, one energy, from a 140 HP
**one-prize** Stage 2. c023's table scored its printed `0` and ranked the archetype 16th of 22
when it should have been near the top. Two independent authors' agents play that exact list and
are the two strongest on our panel.

We built our own and it is **worse than the champion**: 0.4177 on the calibration panel against
0.5710, and 497.6 on the ladder against 688.5. The reason is structural, not a tuning failure:

- it beats every deck built on ex/Mega attackers (0.52–0.63) — they concede 2–3 prizes each;
- it loses to every deck built on one-prize Pokémon — Iono 0.290, Crustle 0.200, the three
  Alakazam agents 0.165–0.210, Grimmsnarl 0.105.

**Its prize-efficiency edge only exists against opponents who concede more prizes than it does.**
Against another one-prize deck the edge is gone and 50–140 HP bodies are the liability. Since
Marnie's Grimmsnarl is 58.8% of the 1100+ band and is itself mostly one-prize Pokémon, the
archetype cannot be the answer to this ladder.

### 3. Every candidate this project ever packaged was unsubmittable

`D11`, in `LADDER_LOG.md`. `kaggle_environments` does not import `main.py`; it `exec`s the source
in a namespace with **no `__file__`**. A module-level `os.path.abspath(__file__)` therefore raises
before the agent exists. Submission `55466460` passed extraction, play, latency and both-seat
checks, then died on its validation episode having played nothing.

Two gaps allowed it: the repo's loader uses `spec_from_file_location`, which *does* set `__file__`
— so ~400,000 games of local measurement ran agents through a loader the competition does not use
— and no evaluation ever played a candidate against itself, which is exactly what Kaggle's
validation episode is. `raw_python_check` now closes both.

**It has a second layer.** The wrapper is copied into each candidate at *build* time, so fixing
the source repaired nothing already built: all 28 c023 candidates still carry the broken bytes.
None was ever submitted, so c023's conclusions stand — but its claim to have packaged and
validated candidates *for submission* never covered the deployment path.

### 4. One component works and is worth keeping

`c024_prizes.PrizeTracker` deduces the prize pile exactly — decklist minus every visible zone,
including the in-flight card at `select.effect`, refusing to answer when the count does not close.
Validated against 83 real ladder replays with an exact oracle: **0 violations over 233 real prize
reveals, and the pile is known from turn 2 in 95.2% of decisions.**

The thing built on top of it — finish mode, overriding only on a win verified in every sampled
world — is **correct and inert**: over 60 games it found 8 winnable lines and the expert was
already taking all 8. That closes the "we miss lethal lines" class by measurement.

## What was not done, and should have been

**The ladder was used for six readings in eight weeks.** Five submissions a day were available
throughout. The single instrument that is not bounded below the goal, and that would have exposed
D11 in an hour, was the one left idle — while 392,792 games went into an instrument that
saturates at the 93rd percentile. If there is one process change for the next campaign, it is
that a candidate goes to the ladder on the day it exists.

## The open decision left to the user

A dormant submission freezes its rating and the leaderboard takes the best across submissions.
`55478202` touched **947.9** on eleven games; two further submissions would have locked that in.
Five a day are allowed, so it breaks no rule, and our previous 719.7 is already an accidental
frozen draw.

**I did not do it**, and the reason is in the first line of this document: it would make a
measurement artifact the headline number for an agent measured at 690. It is a competitive-strategy
call rather than a technical one. It remains available and it decays as the agent plays.
