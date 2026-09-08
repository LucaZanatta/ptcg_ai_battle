# Results Protocol

- Every claim requires executable evidence.
- PASS only when all mandatory acceptance criteria complete.
- A negative model result may still be a PASS.
- Earlier contract results are immutable.
- Raw logs belong in `results/test_logs/`.
- Generated data/models/reports belong in `results/artifacts/`.
- Failures belong in `results/failures/`.
- Changed source files are copied into `results/artifacts/source_snapshot/`.
- Initial/final Git HEAD and commits must be recorded.
- Never commit credentials or expose Kaggle tokens.
