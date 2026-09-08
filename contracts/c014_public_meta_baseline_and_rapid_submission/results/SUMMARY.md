# c014 — public meta baseline and rapid submission

**STATUS = PASS**

Selected **Archaludon ex / Cinderace metal tempo**, built one deterministic expert, validated 750 games, packaged, and uploaded. Kaggle submission **55004756** — status `COMPLETE`, public score **600.0**.

## Result against the only external reference

| agent | Kaggle ref | public score |
|---|---|---|
| Dragapult control (c005) | 54948560 | **719.7** |
| c014 Archaludon v0 | 55004756 | **600.0** |

v0 is **below** the control. That is the honest headline: a first deterministic expert for a newly selected deck does not beat a mature official sample agent. §11 anticipated this — strength is diagnostic here, and the contract's deliverable is a validated, accepted submission plus one measured loss mode.

## Why this deck

Public mining took **0.14 hours** against a 4–6 hour box. Archaludon ex / Cinderace was the only candidate with both a current rising-meta signal (score rate above 60% in a snapshot updated the same day) and an **exact legal 60-card list**. Starmie is the strongest *reported* archetype and was rejected anyway, because no public source publishes its list and inventing one would make the result unattributable.

## Hard gates

| gate | result |
|---|---|
| zero_invalid_selections | PASS |
| zero_exceptions | PASS |
| zero_timeouts | PASS |
| all_games_classified | PASS |
| both_seats_tested | PASS |
| p99_within_250ms | PASS |
| max_within_self_imposed_bound | PASS |
| package: at_least_100_games | PASS |
| package: zero_invalid_selections | PASS |
| package: zero_timeouts | PASS |
| package: all_completed | PASS |
| package: both_seats | PASS |
| package: at_least_three_opponents | PASS |

600 direct + 150 extracted-package games. Invalid selections **0**, exceptions **0**, timeouts **0**. Worst game p99 latency 0.1200239930767566 ms against a 250 ms gate.

## Is the thesis actually executed?

Yes. Setup success **1.0**, intended attacker prepared **0.8375**, and Archaludon ex delivers **0.7522** of all attacks across 3785 sampled decisions — with **zero** fallback decisions.

## Single next loss mode

> Cinderace reaches the Active Spot via Explosiveness in only a minority of games, so Turbo Flare - the deck's only energy accelerator, attaching 3 Basic Energy to the bench - is usually unavailable and the deck must reach {M}{M}{M} through one manual attachment per turn.

it is upstream of every other weakness measured here: slow energy is what makes the evolve-turn weakness window long enough to be punished.

## Known limitations

- public score 600.0 is below the Dragapult control's 719.7; v0 is a challenger, not a champion
- the competition's published per-decision timeout could not be scraped (Kaggle pages are client-rendered); a self-imposed 1000 ms maximum was enforced and labelled as such
- the daily submission limit could not be verified for the same reason; only one upload was made, so it was not binding
- Cinderace's Explosiveness opener fires in a minority of games — the selected single next loss mode

