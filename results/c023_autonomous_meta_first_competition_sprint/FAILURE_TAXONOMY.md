# FAILURE_TAXONOMY

Losses assigned to concrete, countable classes, from raw games rather than from impressions.
Each class names what a rule would have to change, and each records whether a rule was written,
what it measured, and what happened.

The mining is the champion (`chal_dp_base2`, the wrapper with no rules, action-identical to
`official_dragapult`) against `pub_tetsutani_grimmsnarl` — the matchup that matters most, because
Marnie's Grimmsnarl ex is 58.8% of the 1100+ ladder band and the champion scores **0.250** there.

**300 games: 90 won, 210 lost.**

## What separates a win from a loss in this matchup

`tools/c023_mine.py`, contrasting won against lost games on features that map onto decisions:

| feature | won | lost | Δ (lost − won) | std |
|---|---:|---:|---:|---:|
| attacks taken | 6.36 | 4.70 | −1.66 | −0.97 |
| turns on which we attacked | 6.36 | 4.70 | −1.66 | −0.97 |
| decisions in the game | 107.6 | 81.4 | −26.2 | −0.96 |
| turns an attack was available | 6.36 | 4.74 | −1.61 | −0.95 |
| **mean bench size** | **3.31** | **2.63** | **−0.67** | −0.64 |
| final turn | 13.09 | 11.32 | −1.77 | −0.60 |
| **turn of our first attack** | **2.24** | **2.80** | **+0.55** | +0.37 |
| turns an attack was available and declined | 0.000 | 0.043 | +0.043 | +0.21 |
| active with zero energy at a MAIN decision | 18.26 | 17.96 | −0.30 | −0.04 |

## Reading this honestly

Most of that table is **confounded by game length**. We lose in 11.3 turns and win in 13.1, so
every *count* is lower in losses as an arithmetic consequence of losing, not as a cause. Attacks
taken, decisions, attacks available: all downstream.

Two features are not counts and survive the confound:

- **`first_attack_turn`: 2.24 in wins, 2.80 in losses.** Half a turn of setup, measured on the
  same games.
- **`mean_bench`: 3.31 in wins, 2.63 in losses.** A per-decision average, so it does not inflate
  with game length.

And one near-zero number is worth as much as the large ones:

- **`missed_attack_turns` ≈ 0.043 per game.** The champion essentially *never* declines an
  available attack. Whatever is wrong here, it is not tactical timidity, and a "take the attack"
  rule would have nothing to correct. That is a class ruled out by measurement rather than by
  argument.

## F5 — slow development (the class the data supports)

**Statement.** We lose the games in which the Dreepy → Drakloak → Dragapult ex line comes online
late and the board stays narrow. Grimmsnarl does not need to out-play the line; it needs the line
to be one turn behind, and then Shadow Bullet's 180 + 30 and Munkidori's three transferred
counters per turn close a 6-prize race in eleven turns.

**What a fix would have to change.** Reach the first Phantom Dive sooner and keep more
developable Pokémon on the board while doing it.

**What was tried.** This is precisely the axis `DECK_CHANGE_LEDGER.md` attacks — a third and
fourth Rare Candy (the only turn-two Dragapult ex enabler, scored 40000 by the agent), a fourth
Dragapult ex, a fourth Poké Pad, a third Night Stretcher, more energy. **Seventeen mutations,
none separating from the control over 1,200 games each.** The consistency of the official list is
not the binding constraint, even though the loss profile says consistency is what we lack.

**Status: IDENTIFIED, NOT CORRECTED.** The class is real and the obvious levers do not move it.

## F4 — bench exposure to a damage-spread deck (the class the data contradicts)

**Statement, as originally written.** Every small basic on our bench is a prize on a timer against
this deck: Shadow Bullet hits a *benched* Pokémon for 30 on top of 180 to the active, Froslass
puts a counter on every Pokémon with an Ability at each checkup, and Munkidori moves three
counters a turn onto our side. The sample scores playing a Dreepy at 51000 — the second-highest
number in its table — regardless of what is across the board.

**The evidence that motivated it.** `bench_wide_setup` lost **6.6 points in this matchup**
(0.242 vs 0.308) and 5.0 overall — a wide *opening* bench is measurably bad here.

**The evidence against it.** The mining says winning games have a **larger** mean bench (3.31 vs
2.63), which is the opposite sign. The two are not actually in conflict — an *opening* bench is
exposure before anything can evolve, while a *mid-game* bench is what a developed board looks
like — but the distinction means a mid-game veto is attacking the wrong half.

**Status: TESTED ANYWAY, because it was already built and the screen is cheap, and because a
correlational contradiction is not a controlled one.** Result in `rule_screen2` and
`EXECUTIVE_DECISION.md`. Recording the contradiction *before* the result is the point: had this
been written afterwards it would read as a hypothesis that was always doomed.

## F1 — turn order · F2 — opening bench · F3 — greedy option scoring

Three further classes, each with a rule written, screened and killed. Full statements, mechanisms
and numbers in `AGENT_CHANGE_LEDGER.md`:

| class | rule | dev field vs same-run control | verdict |
|---|---|---:|---|
| F1 turn order | `go_first` | 0.4883 vs 0.5166 | **KILLED** — and it cost 9.1 points against Grimmsnarl specifically |
| F2a opening bench (Dreepy) | `bench_dreepy_always` | 0.5033 vs 0.5166 | **KILLED** — inside the noise floor |
| F2b opening bench (wide) | `bench_wide_setup` | 0.4667 vs 0.5166 | **KILLED** — −5.0, outside the floor |
| F3 greedy option scoring | `turn_planner` ×4 variants | 0.479–0.4985 vs 0.506 | **KILLED** — monotone in override rate: the more it overrode, the worse it did |

F3's ordering is the informative part. `plan2`, which planned at *every* single-select decision
and therefore overrode most often, was the worst arm at 0.479; `plan1`, the most conservative,
was the best of the four at 0.4985. A search whose evaluator is a hand-written board score is
competing with constants that encode deck knowledge the evaluator does not have, and it loses
that argument more often than it wins it. That is what motivated the `prize_only` variant — an
override gated on facts (prizes taken, prizes conceded, terminal) rather than on taste.

## Classes considered and ruled out without a rule

- **Declining available attacks.** Measured at 0.043 turns per game. Nothing to correct.
- **Timeouts and illegal selections.** Zero across 30,000+ games in this campaign; every
  evaluation reports `errors=0` and the wrapper legality-checks every override before returning
  it. Not a failure class here.
- **Deck-out.** The base already guards it (`no_draw` at `deckCount <= 8`), and `my_prize_min`
  reaches 0 in both wins and losses at the same rate.
