# c013 — next step

## 1. Stop trying to improve the soup by continuation

Q0/Q1/Q2 all fail to produce a confirmed improvement, and the strategic-field tendency is positive but underpowered at ~12,000 games per arm. Either commit a budget large enough to resolve a ~0.04 field effect, or change the objective — not another 12,000-game arm.

## 2. Close the gap to the frozen teacher on the strategic field

the teacher scores ~0.55 on the field against ~0.37 for the best RL candidate. That, not the soup, is the binding constraint on SUBMISSION_G, and no amount of policy combination has moved it.

## 3. Rebuild the semantic benchmark with phase- and opponent-stratified sampling

the Claude preflight is PARTIAL only because the sampler stratified by option type and never drew attack, setup, or matchup-failure states. 8 of §27's 10 categories are reachable with a different sampler.

## 4. Investigate the shared opponent skeleton

Lucario and Abomasnow are identical on all 98 promotion decisions. If the official agents share a promotion routine, exploiting it is a concrete edge that no amount of self-play discovers.

