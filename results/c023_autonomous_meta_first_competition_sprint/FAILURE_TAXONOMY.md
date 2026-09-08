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

## F8 — the real ladder's answer: we lose the two-hit race, and it is a deck fact

Everything above is mined from *panel* games — our opponents, our seeds. This section is mined
from **83 real Kaggle ladder games the champion actually played**, read turn by turn out of their
replays (`tools/c023_replay_mine.py`). 48 won, 35 lost.

### The contrast

| feature | won | lost | Δ | std |
|---|---:|---:|---:|---:|
| **prize lead at turn 9** | **0.000** | **−1.886** | −1.886 | −0.93 |
| **mean bench size** | **3.558** | **2.503** | −1.055 | −0.87 |
| prize lead at turn 7 | −0.312 | −1.543 | −1.230 | −0.85 |
| prize lead at turn 5 | −0.312 | −1.029 | −0.716 | −0.76 |
| prize lead at turn 3 | −0.146 | −0.457 | −0.311 | −0.60 |
| cards left in deck (mean) | 28.13 | 31.23 | +3.10 | +0.42 |
| **turn of our first attack** | 2.978 | **2.697** | −0.281 | −0.17 |
| attacks taken | 5.792 | **6.229** | +0.437 | +0.13 |

### Read it honestly: most of this table is the scoreboard

Prize lead *is* the score. "We are behind on prizes in the games we lose" is not a finding, it is
a restatement, and a small bench is largely **downstream of being knocked out** rather than a cause
of it. The features are listed in full because suppressing the tautological ones would make the two
that matter look better than they are.

**And two of them contradict the local mining outright.** Against the panel's Grimmsnarl agent,
losses were the games where we attacked *late* (first attack turn 2.80 in losses against 2.24 in
wins). On the real ladder the sign flips: we attack **earlier** in losses (2.70 against 2.98) and
**more often** (6.23 attacks against 5.79). F5 — "slow development" — is a property of that panel
matchup, **not of how the champion loses on the ladder.** The campaign's most-cited failure class
does not survive contact with real games.

### What does survive: the game ends early, and only against the decks that out-muscle us

Split by opponent archetype, the losses that matter are short:

| opponent | won | lost | final turn, won | final turn, lost |
|---|---:|---:|---:|---:|
| **Mega Lucario** | 7 | 8 | 12.3 | **7.5** |
| **Marnie Grimmsnarl** | 4 | 6 | 14.0 | **9.0** |
| Alakazam | 14 | 5 | — | — |
| Crustle Wall | 2 | 7 | — | — |
| Dragapult (mirror) | 6 | 0 | — | — |

Against Mega Lucario we also get **3.25 turns with an attack available in losses against 5.43 in
wins** — we are not out-played over a long game, we are removed from one.

**The mechanism is arithmetic, and it is in the card text:**

| | HP | its attack | hits needed to kill Dragapult ex (320 HP) |
|---|---:|---|---:|
| Dragapult ex (ours) | 320 | Phantom Dive, **200** | — |
| Mega Lucario ex | **340** | Mega Brave, **270** | **2** |
| Marnie's Grimmsnarl ex | **320** | Shadow Bullet, **180** + 30 to a bench | 2 |

Phantom Dive's 200 does not kill a 320 or 340 HP attacker. **Ours needs two hits and theirs needs
two hits — but a Mega Lucario ex knocked out gives them three prizes to our two, and Grimmsnarl
adds 30 to a benched Pokémon every single attack.** We lose the race on the exchange rate, not on
the decisions.

### Why this is the campaign's closing finding

**It is a deck fact, and the deck is fixed by the archetype.** No override, no score constant, no
turn-level search changes what 200 damage does to 340 hit points. That is a mechanism for the
whole campaign's negative result — five branches, 28 candidates, ~90,000 games — rather than five
separate shrugs.

It also names the next campaign's first question precisely, and it is not "which constant":
**does an official base exist whose attacker wins the two-hit race against the current
320–350 HP format?** On this panel `official_dragapult` scores 0.325 against Grimmsnarl and 0.435
against the 1084-rated Mega Lucario agent, while the same panel's Alakazam agents — whose attacker
scales with hand size rather than a fixed 200 — sit at 0.60–0.64 overall.

## Classes considered and ruled out without a rule

- **Declining available attacks.** Measured at 0.043 turns per game. Nothing to correct.
- **Timeouts and illegal selections.** Zero across 30,000+ games in this campaign; every
  evaluation reports `errors=0` and the wrapper legality-checks every override before returning
  it. Not a failure class here.
- **Deck-out.** The base already guards it (`no_draw` at `deckCount <= 8`), and `my_prize_min`
  reaches 0 in both wins and losses at the same rate.
