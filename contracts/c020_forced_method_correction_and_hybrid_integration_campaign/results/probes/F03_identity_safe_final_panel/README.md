# F03 — Identity-safe final panel

Results are paired back to jobs by `game_id`, never by list position, because a round-robin worker pool returns them in worker order. Every candidate faces the same opponents at the same seats with the same agent-side seeds.

What cannot be controlled is stated rather than claimed: `make("cabt")` exposes no environment seed, so shuffles and coin flips are not paired across candidates and differences smaller than the reported Wilson interval are not attributable to the candidate.
