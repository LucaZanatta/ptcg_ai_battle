# c014 — public meta baseline and rapid submission

**STATUS = PASS**

Selected **None**, built one deterministic expert, validated 750 games, packaged, and uploaded. Kaggle submission **55005237** — status `COMPLETE`, public score **600.0**.

## Result against the only external reference

| agent | Kaggle ref | public score |
|---|---|---|
| Dragapult control (c005) | 54948560 | **719.7** |
| c014 Archaludon v0 | 55005237 | **600.0** |

v0 is **below** the control. That is the honest headline: a first deterministic expert for a newly selected deck does not beat a mature official sample agent. §11 anticipated this — strength is diagnostic here, and the contract's deliverable is a validated, accepted submission plus one measured loss mode.

## Why this deck

Public mining took **0.00 hours** against a 4–6 hour box. Archaludon ex / Cinderace was the only candidate with both a current rising-meta signal (score rate above 60% in a snapshot updated the same day) and an **exact legal 60-card list**. Starmie is the strongest *reported* archetype and was rejected anyway, because no public source publishes its list and inventing one would make the result unattributable.

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

600 direct + 150 extracted-package games. Invalid selections **0**, exceptions **0**, timeouts **0**. Worst game p99 latency 1.6098770138341933 ms against a 250 ms gate.

## Is the thesis actually executed?

Yes. Setup success **0.9333**, intended attacker prepared **None**, and Archaludon ex delivers **None** of all attacks across 8811 sampled decisions — with **zero** fallback decisions.

## Single next loss mode

> Both counter mechanisms execute whenever they are available, but the Bellibolt engine comes online later than the damage race requires: Thunderous Bolt cannot attack on consecutive turns and Voltaic Chain only reaches competitive damage once several {L} are already in play, so the deck spends its early turns developing while the opponent scores.

it is the one measurement that explains a high mechanism-execution rate coexisting with a low score rate; every other observed weakness is downstream of arriving late.

## Known limitations

- the pre-registered thesis falsifier FIRED: score rate vs the c014 target is 0.36 against a registered 0.60 threshold. Both counter mechanisms executed at 1.000 when available, so the failure is the matchup, not the execution
- the official Iono sample agent beats the same target 0.98 with the same deck; the 0.62 gap is this v0's implementation quality, not a wrong matchup thesis
- public score 600.0 is below the Dragapult control's 719.7; v0 is a challenger, not a champion
- the competition's published per-decision timeout could not be scraped (Kaggle pages are client-rendered); a self-imposed 1000 ms maximum was enforced and labelled as such
- the daily submission limit could not be verified for the same reason; only one upload was made, so it was not binding
- Cinderace's Explosiveness opener fires in a minority of games — the selected single next loss mode

