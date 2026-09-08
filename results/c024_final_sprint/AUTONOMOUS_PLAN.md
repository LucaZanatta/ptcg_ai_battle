# Autonomous run plan — 2026-08-13 to the deadline

The user asked to be out of the loop. This is the standing plan, written down so it survives a
restart, and it is executed without further prompting.

**Hard deadline: 2026-08-16 23:59 UTC = 2026-08-17 01:59 Europe/Rome.**

*(Corrected 2026-08-15. This plan and every standing prompt derived from it read the Kaggle API's
`deadline: 2026-08-16 23:59` as Rome time. It is UTC, so the true cut-off is two hours later than
recorded, early on the 17th Rome time. The error was conservative — it would have closed early,
never late — but the user caught it before the close, and a two-hour error in the one hard
constraint of the campaign is worth naming rather than silently patching.)*

## The one rule that outranks everything else

**At the deadline, the strongest agent we have must be LIVE on the ladder.**

Kaggle keeps roughly the **two most recent** submissions playing and lets older ones go dormant
(measured: `LADDER_LOG.md`). So:

- **On 2026-08-15, resubmit `official_dragapult` (the champion package) unconditionally**, unless
  the ladder has by then shown a challenger genuinely ahead of it. Resubmitting makes it one of
  the two most recent and therefore certainly live, and leaves it a full day to converge.
- Never make a submission that would leave the champion dormant at the deadline.
- Do not spend the daily budget on speculative agents after 2026-08-15.

## Current state

| ref | agent | rating | note |
|---|---|---:|---|
| 55254872 | `official_dragapult` (champion) | **693.9** | 199 episodes, converged |
| 55477137 | c024 Alakazam v2 (ours) | 681.2 | 6 episodes — mostly prior, not a reading yet |
| 55466460 | c024 Alakazam v1 | ERROR | D11, `__file__` NameError |

## Each wake-up, in order

1. **Read the ladder.** Episode counts and ratings for both live submissions; append a row to
   `LADDER_LOG.md`. A rating on fewer than ~40 episodes is prior, not evidence.
2. **Check the champion is still playing.** If it has gone dormant, resubmit it immediately —
   that outranks all other work.
3. **Continue the local work** below, one change at a time, each measured on the full
   eleven-opponent panel at >= 660 games before it is kept.
4. **Commit.** Every wake ends with the repository in a state that can be picked up cold.

## The local work, in priority order

**1. The one-prize mirror problem — the archetype's real limit.**
Measured against `official_iono`: we take 3.00 prizes a game and concede **4.14**, while the
champion concedes 3.29 in the same matchup. The panel profile says the same thing everywhere:

- we beat every deck built on ex/Mega attackers (0.50–0.67), which give up 2–3 prizes each;
- we lose to every deck built on one-prize Pokémon — Iono 0.217, Crustle 0.183, the three
  Alakazam agents 0.167.

Our prize-efficiency edge only exists against decks that concede more prizes than we do. Against
another one-prize deck the edge is gone and our 50–140 HP bodies are a liability. **This is
structural, not a tuning defect**, and it bounds what this archetype can be worth. Any further
work on it must attack that matchup class or it is not worth doing.

**2. Do not chase sub-noise-floor changes.** Three consecutive "fixes" on 2026-08-12 each measured
1–2 points *down* across 660-game panels and were reverted. The floor is ~2.4 points at 1,200
games and wider at 660. A change that cannot clear it does not get kept, and a maximum over
several arms is not a result (D7).

## Stopping

- If nothing clears the champion by 2026-08-15, the champion is the entry and the remaining time
  goes to the final report, not to more arms.
- At the deadline: regenerate reports, capture Git and source evidence, and close with an honest
  competitive statement — including that this campaign's headline gain came from *deploying* the
  right existing agent rather than from building a better one.
