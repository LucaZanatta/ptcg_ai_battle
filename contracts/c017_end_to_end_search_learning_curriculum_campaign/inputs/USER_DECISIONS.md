# Fixed user decisions for c017

1. This is one large integrated contract, not a sequence of small block contracts.
2. Build the entire search → trajectory → policy/value → curriculum → guided-search pipeline.
3. Submit the previous official Mega Lucario baseline at the start.
4. Probes run throughout but are non-blocking by default.
5. Running later blocks is valuable because it may expose defects in earlier interfaces.
6. Do not spend months perfecting blocks one by one.
7. Complete a thin end-to-end run first, then perform one consolidated repair pass.
8. Continue after non-catastrophic probe failures using taint metadata and conservative fallbacks.
9. Only hidden information, illegality, serious timeout/crash risk, identity corruption, package/source mismatch, permission uncertainty, or failed extraction can block submission of an affected candidate.
10. Curriculum increases self-play according to performance against the frozen baseline, with a field-regression guard and a conservative fallback schedule.
11. Submit the strongest trustworthy intermediate or final stage; the final stage is not automatically preferred.
12. Include full repository source, focused source bundle, milestone source snapshots, configs, tests, probes, raw logs, trajectories/manifests, checkpoints, packages, hashes, and Git patch in results.
13. Winning and external improvement matter more than contract completion or technical elegance.
