# Thin end-to-end smoke (§10)

The full vertical executed at deliberately small budgets before any block was scaled:

```text
baseline action -> search attempt -> trajectory write/read -> policy/value train step -> curriculum scheduler/evaluation -> learned-policy inference -> final evaluator -> clean package smoke
```

**Objective was interface execution, not strength**, and it worked: six defects surfaced (see `FIRST_PASS_DEFECT_RANKING.md`) that no amount of block-level polishing would have revealed, because each only appears when one block hands data to the next.

| stage | smoke result |
|---|---|
| search teacher | 60 games, 3616 decisions, 1619 searched |
| trajectories | schema `c017.trajectory.v1`, split by game_index (no game straddles two splits) |
| distillation | CUDA, test top-1 0.526 |
| curriculum | 2000 games, 0 performance promotions |
| final panel | 2 candidates evaluated |
| package smoke | baseline validated from clean extraction, submitted as 55011215 |
