# S2a — finish mode: a correct override with nothing to correct

Two components were built on the legal base (`official_dragapult`, `SUBMISSION_REUSE_ALLOWED`).
One works and is worth keeping. The other is right and useless, and the measurement that shows it
is the point of this file.

## The prize tracker works, and the check is exact

`c024_prizes.PrizeTracker` deduces which of our own cards are sitting in the prize pile:
decklist − hand − discard − board − stadium − looking − the revealed deck − **the card currently
resolving an effect** (`select.effect`), refusing to answer whenever the count fails to close.

It cannot be validated by playing better; it is either right or wrong about a fact the game
reveals later. Every prize card eventually moves PRIZE → HAND and the log carries its id, so the
test is: *every card the tracker declared prized must be one the game later takes out of the
prize pile.* Run over the champion's **83 real Kaggle ladder replays**:

| | |
|---|---:|
| games parsed | 83 |
| games where it ever declared | **80** |
| median turn of first deduction | **2** |
| decision frames | 7,580 |
| frames with a live prize set | **7,213 (95.2%)** |
| prize cards taken while a set was live | **233** |
| sets dropped as inconsistent | **0** |
| **violations** | **0** |

**From turn two onward, in 95% of decisions, the prize pile is known exactly.** That removes the
larger of the two ways a forward search can verify an imaginary win.

## Finish mode is inert, and that is a result

`c024_finish` overrides the expert on one condition: the simulated line **ends the game in our
favour**, reproduced in *every* determinized world. `FAILURE_TAXONOMY` F3 killed four planner
variants whose losses were monotone in override rate; this is the far end of that curve and the
one point nobody had sampled.

60 games against Grimmsnarl, Crustle Wall and the mirror, counters summed across all 60 forked
children:

| counter | value | meaning |
|---|---:|---|
| `considered` | 416 | decisions passing the cheap gate (~6.9 per game) |
| `searched` | 416 | decisions that reached the engine |
| **`fired`** | **0** | decisions where the expert was overridden |
| `base_already_won` | 8 | a unanimous winning line existed — and the expert was already taking it |
| `vetoed` | 0 | a win in some worlds but not all |
| `errors` | 0 | |

**Across 60 games a verifiable win-this-turn line was found 8 times, and the expert was taking it
all 8 times. It missed none.**

This is the same class as `missed_attack_turns ≈ 0.043` in `FAILURE_TAXONOMY`: a failure mode
ruled out by measurement rather than by argument. The sample agent's *tactical* play — taking
available attacks, converting lethal lines — is not where its rating is going. The rule is kept in
the tree, off by default, because it costs nothing and the counters are the evidence.

**Status: CORRECT, INERT. Not a candidate.**

## D10 — a replay defect that inflated earlier evidence

A Kaggle replay records **both** seats at every step, and the seat that is not acting carries a
stale copy of its last observation — `select`, `logs` and all. In one sample game seat 0 had 59
ACTIVE frames carrying a selection and **94 INACTIVE ones**.

`tools/c023_replay_mine.py` filters on `observation.select` being present and does not check
`status`, so it counted those stale frames as decisions. The first oracle run inherited the same
filter and reported **80 violations out of 266 checks** — every one of them the same prize event
re-read from a repeated log. Restricting to `status == "ACTIVE"` took it to **0 out of 233**.

Consequence for `FAILURE_TAXONOMY` F8, which is mined by that tool: its per-game **counts**
(decisions, attacks taken, attacks available) are inflated by roughly 60%. Its **rates and turn
indices** — first-attack turn, prize lead by turn, mean bench — are ratios or minima over the same
inflated set and keep their sign, so F8's conclusions stand; the absolute counts in its table do
not. Recorded here rather than silently corrected in a closed contract.

## What it leaves

Thirty candidates have now been built on the `official_dragapult` base across c023 and c024, and
none has separated from it. The tactical layer is not the constraint, the deck-mutation layer is
not the constraint, and the score-constant layer is not the constraint. What is left is the
archetype — and `S0_PUBLIC_AGENT_SCREEN.md` plus `EXCHANGE_RATE_CORRECTION.md` are where that
goes next.
