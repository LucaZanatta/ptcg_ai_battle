# Results Protocol

- c005 through c008 are immutable.
- Every aggregate must reproduce raw games exactly.
- Every game must preserve job and checkpoint identity.
- File existence is never sufficient for acceptance.
- The content-aware validator is mandatory.
- No training or checkpoint mutation is permitted.
- Raw logs belong under `results/test_logs/`.
- Raw games, aggregates, decisions, packages, and Kaggle evidence belong under `results/artifacts/`.
- Failures belong under `results/failures/`.
- Copy changed c009 project source into `results/artifacts/source_snapshot/`.
- Record initial/final Git HEAD and implementation commits.
- Never store credentials.
