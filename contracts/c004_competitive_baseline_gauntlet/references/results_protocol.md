# Results Protocol

Every claim requires reviewable evidence under the contract’s `results/` directory.

- `PASS` only when all mandatory acceptance criteria pass.
- Raw command output goes in `results/test_logs/`.
- Generated reports/data go in `results/artifacts/`.
- Failures and rejected candidates go in `results/failures/`.
- Changed source files are copied to `results/artifacts/source_snapshot/`.
- Earlier contract results are immutable.
- Git initial/final HEAD and commits must be recorded.
- Candidate strategy/deck hashes must be frozen before and verified after the gauntlet.
