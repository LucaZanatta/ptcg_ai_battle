# Results Protocol

- Every claim requires executable evidence.
- Negative competitive results may still produce PASS.
- c005 and c006 are immutable.
- The frozen teacher and deck are immutable.
- Raw logs belong under `results/test_logs/`.
- Models, data, reports, archives, and Kaggle evidence belong under `results/artifacts/`.
- Failures belong under `results/failures/`.
- Copy changed project source into `results/artifacts/source_snapshot/`.
- Record initial/final Git HEAD and implementation commits.
- Never store credentials.
- Never submit when the local gate says `DO_NOT_SUBMIT`.
