# Project ground truth for c016

Generated 26 July 2026, Europe/Rome.

## Current strategic objective

Win the PTCG AI Battle competition by obtaining strong competition-valid deck-agent pairs quickly enough to learn from repeated external submissions. The unit of progress is competitive evidence, not contract completion.

## Corrected branch status

### Dragapult control

- Latest locally recorded public score: 719.7.
- Current role: temporary internal champion and evaluation control.
- Strategic status: not strong enough to be treated as a winning final target.
- Do not run another blind PPO continuation.

### c014 custom Archaludon/Cinderace

- Accepted submission reference: 55004756.
- Recorded public score in c014 status: 600.0, with volatile later observations.
- Local score rates: 9% vs Dragapult, 48% vs Mega Lucario, 2% vs official Iono, 35% vs Mega Abomasnow, 67% vs safe control.
- Operational result: legal, package-valid, no invalid actions/exceptions/timeouts.
- Corrected strategic result: weak custom implementation, not a champion.
- Key lesson: the project found a much richer public Archaludon implementation but replaced it with a smaller static-priority expert. This did not reproduce public strength.

### c015 custom Iono/Bellibolt

- Accepted submission reference: 55005237.
- Recorded score: 600.0 at contract close.
- Local score rates: 36% vs c014, 4% vs Dragapult, 20% vs Mega Lucario, 12% vs Mega Abomasnow, 61% vs safe control.
- Pre-registered thesis threshold: 60% vs c014; actual 36%; thesis falsified.
- The official Iono sample agent reportedly scored about 98% against the same c014 target in the c015 evidence, demonstrating a large implementation-quality gap.
- Report defects include copied c014 headings, null selected fields, zero Mechanism B opportunities reported as successful in prose, and inconsistent denominators.
- Corrected status: operational package pass; competitive fail; evidence integrity partial/fail; custom branch archived.

## c016 purpose

Do not patch c014 or c015. Establish a high public baseline by reproducing strong public competition agents faithfully, evaluate them on one common protocol, and submit only a candidate that clears a meaningful competitive gate.

## Existing public-source leads captured by c014

- masamikobayashi/a-sample-archaludon-75-wr-vs-my-1300-starmie
- romanrozen/strong-start-baseline-agent-v10-lb-950
- ryotasueyoshi/rule-based-not-psychic-alakazam-best-5th
- makthanithin/pok-mon-tcg-ai-battle-meta-snapshot-06-29
- pilkwang/pok-mon-tcg-ai-battle-meta-snapshot-18-july
- smallpond/en-replay-archetype-analysis
- ichigoe/beginner-guide-from-deck-list-to-first-valid-sub

These are leads, not automatically licensed or verified strong candidates. c016 must refresh current sources and resolve reuse rights.

## Last verified competition timing from c014

- Competition slug: pokemon-tcg-ai-battle.
- Last verified deadline UTC: 16 August 2026, 23:59 UTC.
- Rome equivalent recorded: 17 August 2026, 01:59 Europe/Rome.

These facts are time-sensitive and must be re-checked in c016.
