# Contract Results Protocol

All contract-specific evidence must be written under the contract's `results/` folder.

Required top-level files:

- `SUMMARY.md`
- `STATUS.json`
- `FILES_CHANGED.md`
- `COMMANDS_RUN.md`
- `ACCEPTANCE_CHECKLIST.md`
- `GIT_REPORT.md`

Required directories:

- `test_logs/`
- `artifacts/`
- `failures/`

Rules:

1. `PASS` requires every mandatory acceptance criterion to pass.
2. Every factual claim must point to a command, log, artifact, commit, or source snapshot.
3. Tests and benchmarks must save raw output.
4. Do not alter `CONTRACT.md`, `inputs/`, or `references/`.
5. Do not modify results from earlier contracts.
6. Source changes belong in the project repository; review copies belong in `results/artifacts/source_snapshot/`.
7. Include a Git patch from the initial contract HEAD to the final implementation HEAD.
8. Preserve failures and rejected cases under `results/failures/`; do not hide them.
