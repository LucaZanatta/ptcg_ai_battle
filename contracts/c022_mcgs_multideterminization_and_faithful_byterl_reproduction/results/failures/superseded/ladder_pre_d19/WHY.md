# Why the whole rung ladder is superseded

Two defects, both of which invalidate the LADDER rather than any single rung.

**D17** — `random_initial_construction` was declared in the stage table, asserted by the stage
delta test, and read by no implementation file. So BR1 and BR1.5 were the same system: the
ladder had a missing rung and a mislabelled one. Every `conf_*` manifest here predates the fix.

**D18** — `ctrl_BR0` ran under the 200-game `paired_k8` MCGS arm. Its learner ramped from 1.24 to
4.60 updates/s as that arm drained, against a flat 11.4 for the clean `ctrl_BR1`, while
steps/update and decisions/episode were identical. Its production/consumption ratio, queue age,
policy lag and learned policy are all contaminated.

**D19** — the B06 replay check compared the learner's recomputed log-probability against
`behaviour_logp`. Once D17's fix made `behaviour_logp` the UNIFORM value on randomised steps, as
V-trace requires, the check failed on the first batch of every rung from BR1.5 upward. `ctrl_BR1_5`
died at `policy_version 0`. The fix separates mu from pi; the packs here carry neither field.

Nothing in this directory is cited. The ladder is re-run in full from one commit, so that
`MANDATORY_IMPLEMENTATION B7`'s "one codebase must produce machine-verifiable stages" is true of
the ladder that is actually reported rather than of three code versions stitched together.
