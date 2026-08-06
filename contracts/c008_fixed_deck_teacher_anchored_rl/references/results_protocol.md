# Results Protocol

- Every claim requires executable evidence.
- Negative RL results may still produce PASS.
- c005, c006, and c007 are immutable.
- The frozen teacher and Dragapult deck are immutable.
- Raw logs belong in `results/test_logs/`.
- Models, trajectories, plots, reports, archives, and Kaggle evidence belong in `results/artifacts/`.
- Failures belong in `results/failures/`.
- Preserve every changed project source file in `results/artifacts/source_snapshot/`.
- Record initial/final Git HEAD and implementation commits.
- Never store credentials.
- Never submit when the registered gate says `DO_NOT_SUBMIT`.
