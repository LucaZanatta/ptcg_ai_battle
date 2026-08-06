# Files Changed — c005

## New source (committed) — all my scripts, no third-party
| File | Commit | Purpose |
|------|--------|---------|
| `tools/acquire_teachers.py` | 5e47d15 | Reproducible anonymous kaggle kernel output/pull + pinned git clone + sha256 + reuse classification (no credentials). |
| `starter_kit/teachers.py` | 5e47d15 | Behavior-preserving teacher loader: fresh module instance per game per seat, deck baked in; freeze/lineage helpers. |
| `tests/test_teachers.py` | 5e47d15, 53b6fca | Loader isolation / freeze / real-game legality tests (skip if sources absent). |
| `tools/run_strategic_gauntlet.py` | 5e47d15 | Freeze + smoke + sequential balanced round-robin over loaded teachers, gzip schema-v2 capture (reuses gauntlet_stats). |
| `tools/analyze_strategic_gauntlet.py` | d052c28 | Matchup/BT/bootstrap/worst-matchups + context coverage/entropy/game-length. |
| `tools/select_teacher.py` | d052c28 | Pre-registered competitive_score + teacher_score selection. |
| `tools/build_submission.py` | d052c28 | Freeze teacher + build/validate Submission A from the extracted archive. |
| `tools/generate_teacher_dataset.py` | d052c28 | Full-obs teacher dataset + whole-game stratified splits + model-ready records. |
| `tools/validate_teacher_dataset.py` | 4137d98 | Streaming dataset validation (fields/ids/leakage/corruption/distributions). |

No existing project source was modified; c005 reuses committed c001–c004 modules
(safe_policy, episode_capture/schema, gauntlet_stats, candidates for the control).
Snapshots of all 9 files: `artifacts/source_snapshot/`.

## Generated evidence (NOT committed; results package)
Reports (`SUMMARY.md`, `STATUS.json`, `FILES_CHANGED.md`, `COMMANDS_RUN.md`,
`ACCEPTANCE_CHECKLIST.md`, `GIT_REPORT.md`, `artifacts/CLEAN_CHECKOUT.md`),
`test_logs/*`, all `artifacts/*.json|csv|md`, `strategic_gauntlet_games.jsonl.gz`,
`submission_A_teacher.tar.gz`, `teacher_dataset/` (train/validation/test.jsonl.gz +
reports), `c006_training_spec.md`/`c006_training_config.json`, `c005.patch`,
`source_snapshot/`.

## Third-party assets (NOT committed) — under results/, reuse-controlled
- `teacher_sources/` — 4 official kernel submissions (main.py/deck.csv/cg/) +
  notebook sources + `ptcg-abc` clone. Official = OFFICIAL_REUSABLE; ptcg-abc =
  LOCAL_BENCHMARK_ONLY.
- `frozen_teacher/` — the selected dragapult official sample (SOURCE/FREEZE + files).
- `submission_A_teacher.tar.gz` — packaged official reusable sample.
None are committed to git (conservative reuse posture + credential safety).
