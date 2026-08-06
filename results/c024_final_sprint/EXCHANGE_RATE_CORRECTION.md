# The exchange-rate table got the format's best deck exactly backwards

`EXCHANGE_RATE.md` ranked all 22 validated meta decks by how fast each side takes prizes, and put
**Alakazam / Dudunsparce 16th of 22** at 1.389 — below N's Zoroark, below Okidogi, barely above
Festival Lead. It ranked our own Dragapult 4th and concluded that an archetype pivot was "worth
making" but not urgent.

That ranking is wrong, and the reason is one line in the metric.

## What the metric could not see

```
Powerful Hand      1 Psychic Energy      printed damage: 0
"Place 2 damage counters on your opponent's Active Pokémon for each card in your hand."
```

`best_attacker` scores an attack by `a.damage`, the **printed** number. Powerful Hand's printed
damage is 0, so the table fell back to Dudunsparce's Land Crush (90 for three energy) as
Alakazam's "best affordable attacker" and ranked the archetype on that.

Two damage counters per card in hand is **20 damage per card**:

| cards in hand | damage | one-shots |
|---:|---:|---|
| 10 | 200 | Munkidori, Froslass, most one-prizers |
| 11 | 220 | Archaludon ex |
| 15 | 300 | Mega Kangaskhan ex |
| **16** | **320** | **Dragapult ex, Marnie's Grimmsnarl ex** |
| **17** | **340** | **Mega Lucario ex** |

And the deck is built to do exactly that: 4 Poké Pad, 4 Hilda, 4 Dawn, 4 Buddy-Buddy Poffin,
4 Dudunsparce, Lillie's Determination, Xerosic's Machinations.

## Which inverts the two-hit race F8 closed the last campaign on

F8's arithmetic was: Phantom Dive does **200** into 320–340 HP attackers that hit back for
180–270, and a knocked-out Mega pays them three prizes to our two. That is real, and it is why
Dragapult loses the race.

Alakazam is on the other side of every term:

| | HP | prizes conceded | attack cost | damage |
|---|---:|---:|---:|---|
| Dragapult ex (ours) | 320 | **2** | 2 energy | fixed 200 |
| Mega Lucario ex | 340 | 3 | 3 energy | fixed 270 |
| **Alakazam** | 140 | **1** | **1 energy** | **20 × hand size — unbounded** |

**Every Pokémon in that 60-card list is a one-prize Pokémon.** The opponent needs *six* knockouts.
We need two or three against their Megas, and a single energy pays for each of ours. The metric
ranked the deck with the format's best exchange rate 16th because its headline attack prints a
zero.

## The independent confirmation

`S0_PUBLIC_AGENT_SCREEN.md` measured this without knowing any of the above. Two agents by
**different authors** — `pub_jazivxt_rising_tide_v21` and `pub_romanrozen_v10_950` — turn out to
play the **identical 60-card list** (4 Alakazam / 4 Kadabra / 4 Abra / 4 Dudunsparce / 3 Dunsparce
plus trainers), and they are the two strongest agents on the panel:

| | off-mirror field |
|---|---:|
| `pub_jazivxt_rising_tide_v21` | **0.6417** |
| `pub_romanrozen_v10_950` | **0.6197** |
| `official_dragapult` (ours) | 0.4967 |

Two independent authors converging on the same 60 cards, and both landing 12–15 local points
above our champion, is the strongest archetype signal this project has measured.

## The catch, stated plainly

Alakazam beats everything on the panel **except the deck that owns the ladder**:

| | vs `pub_tetsutani_grimmsnarl` |
|---|---:|
| `pub_jazivxt_rising_tide_v21` | 0.2250 |
| `pub_romanrozen_v10_950` | 0.2000 |
| `official_dragapult` (ours) | 0.1333 |

The mechanism is legible in Grimmsnarl's own list: **Froslass** puts a damage counter on every
Pokémon with an Ability at each checkup and **4 Munkidori** move three counters a turn — spread
damage against a board of 50–140 HP one-prizers — while the archetype's own supporter line
attacks the hand that Powerful Hand's damage is made of.

So this is not "Alakazam is the answer". It is:

- **Alakazam is a much better exchange rate than Dragapult**, and the table that said otherwise
  was broken in a way that is now fixed and understood;
- **it still loses to Grimmsnarl**, worse than 2:1, and Grimmsnarl is 58.8% of the 1100+ band;
- so the top of this leaderboard is a rock-paper-scissors problem, not a deck-power problem, and
  the deck that wins it is the one that beats Grimmsnarl **without** giving up the exchange rate
  everywhere else.

`EXCHANGE_RATE.md` and its `best_attacker` scoring are **SUPERSEDED** for any deck whose damage
comes from an effect rather than a printed number. That is at least Alakazam (hand size),
Crustle (a wall that does not race at all) and Great Tusk / LibraryOut (which wins by decking the
opponent out, a win condition the metric has no term for).
