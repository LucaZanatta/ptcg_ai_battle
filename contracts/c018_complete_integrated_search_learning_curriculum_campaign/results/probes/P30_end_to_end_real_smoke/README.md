# P30 — End-to-end real smoke (Pass A vertical)

Every stage of the pipeline executed with small but **real** outputs before anything was scaled.
The point is to surface interface defects while they are cheap: a report-schema mismatch found
after a multi-hour training run costs that whole run.

| stage | evidence | real output |
|---|---|---|
| official search root | 233 real search_begin roots | yes |
| multi-step successor trace | 3274 search_step calls, depth 4, 1858 distinct successors | yes |
| real search trajectory | 233 trusted decisions in contracts/c018_complete_integrated_search_learning_curriculum_campaign/results/trajectories/vertical_trajectories.jsonl.gz | yes |
| supervised optimizer step | 2 steps on cuda, checkpoint hash changed: True | yes |
| actual PPO game and optimizer step | 200 real games, 88 optimizer steps, 3 distinct hashes | yes |
| guided-search inference | guided p90 8.02 ms vs unguided 3.31 ms; 258 shared roots compared | yes |
| evaluator | 16/16 panel games scored from raw identity-carrying rows | yes |
| package smoke | 4/4 games from a clean extraction with the repo off sys.path | yes |

Defects found and fixed during this vertical: 5.

- search_begin rejected under-length hidden-card predictions (2 begin + 49 step errors); the determinizer now tops short pools up with a legal card id and predicts a Pokemon for a face-down opponent Active
- kaggle_environments errors out the seat when handed the official teacher callable directly, which silently scored the baseline panel candidate 0 for 0
- clean-extraction validation could not import cg.teachers for its opponents, because the package's own cg correctly shadows the repo's; opponents now load by file path
- NpzFile decompresses on every key access, so reading opt_dense inside a 12k-row generator made P07 spin for five minutes
- the evidence validator returned PASS with every training milestone absent -- absence is now a critical failure in --final mode rather than a free pass

**Status: PASS.**
