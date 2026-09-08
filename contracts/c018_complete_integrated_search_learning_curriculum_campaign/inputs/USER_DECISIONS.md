# Fixed User Decisions

1. Build the complete search → trajectories → policy/value → curriculum → guided-search pipeline in one integrated contract.
2. Run the full pipeline early rather than perfecting blocks one by one.
3. Probes must reveal defects but should not normally stop later blocks; downstream execution may expose upstream problems.
4. Submit the prior Mega Lucario baseline requirement through its existing accepted c017 submission; do not duplicate it unless invalid.
5. Use the official native search API, not `env.clone()`, for real forward simulation.
6. Curriculum must use actual games and optimizer updates; self-play share increases based on baseline performance with field-regression guards.
7. Allow one consolidated repair pass after the first end-to-end run.
8. Preserve every intermediate candidate and submit the strongest trustworthy post-baseline stage.
9. Include complete final repository source, focused source bundle, milestone code snapshots, probes, raw traces, games, trajectories, checkpoints, configs, packages, hashes, and Git evidence under `results/`.
10. Do not silently shrink the campaign and claim success. Unmet minimum execution floors require an honest partial result.
