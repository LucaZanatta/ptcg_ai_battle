# Results Protocol Reference

Every contract must produce reviewable evidence under its own `results/` directory.

Required principles:

1. `PASS` only when every mandatory acceptance criterion passes.
2. Raw command output belongs in `results/test_logs/`.
3. Generated data and reports belong in `results/artifacts/`.
4. Failed examples and unresolved diagnostics belong in `results/failures/`.
5. All changed source files must be copied to `results/artifacts/source_snapshot/`.
6. `FILES_CHANGED.md` must explain every changed project file.
7. `COMMANDS_RUN.md` must list meaningful commands without secrets.
8. `GIT_REPORT.md` must identify initial/final HEAD, branch, commits, status, and unrelated changes.
9. Earlier contract results are immutable.
10. Claims require executable evidence, not code inspection alone.
