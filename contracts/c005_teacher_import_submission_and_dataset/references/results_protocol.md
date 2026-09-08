# Results Protocol

- Every claim requires evidence.
- PASS only when every mandatory criterion passes.
- Earlier contract results are immutable.
- Raw logs go under `results/test_logs/`.
- Generated artifacts go under `results/artifacts/`.
- Failures and rejected candidates go under `results/failures/`.
- All changed project source files are copied into `results/artifacts/source_snapshot/`.
- Initial/final Git HEAD and commits are recorded.
- Credentials and tokens must never be written to results or committed.
- Third-party code may not be committed or submitted without verified permission.
