# Commands Run — c004

From repo root `/home/luca/kaggle/ptcg_ai_battle`, interpreter `.venv/bin/python`.
No secrets, no network used for candidates (all local).

## Git initial inspection (§14)
```bash
git status --short
git branch --show-current            # contract/c003_episode_lineage_and_semantic_replay
git rev-parse HEAD                    # afe52db...
git switch -c contract/c004_competitive_baseline_gauntlet
```

## Candidate-pool investigation
```bash
# cabt uses each agent's RETURNED deck (cabt.py:122), not configuration.decks.
# cabt.py ships a built-in 60-card deck distinct from starter_kit/deck.csv.
# -> 2 policies (deterministic-first, uniform-random) x 2 decks = 4 complete pairs.
nm -D starter_kit/libcg.so | grep -i rand   # (engine still std::random_device; not seedable)
```

## Phase 0 amendments + tests
```bash
.venv/bin/python -m unittest tests.test_c003_amendments -v > results/test_logs/c003_amendment_tests.txt
.venv/bin/python tools/validate_episodes_v2.py <c003 dataset>   # amended validator: 0 errors, 966/966 replay
```

## Commit source BEFORE the gauntlet (clean tree)
```bash
git commit -m "c004: fix competitive replay and terminal validation"    # 30189fd
git commit -m "c004: add frozen candidate registry and gauntlet runner"  # e584734
git status --porcelain --untracked-files=no   # empty
```

## Gauntlet (freeze + smoke + round-robin) from the clean tree
```bash
.venv/bin/python tools/run_gauntlet.py --base-seed 90210 --require-clean \
  --out-dir contracts/c004_competitive_baseline_gauntlet/results/artifacts
# -> 4 admitted, 40 smoke + 400 gauntlet games, freeze before==after, git_dirty=false
```

## Analysis, selection, tactical mining
```bash
.venv/bin/python tools/analyze_gauntlet.py --in-dir <artifacts> --out-dir <artifacts>
# -> BT ranking, bootstrap, worst matchups, reliability/latency/fallback, competitive_decision (primary=det_starter, backup=det_cabt)
.venv/bin/python tools/mine_tactical_failures.py --in-dir <artifacts> \
  --out <artifacts>/tactical_failure_examples.jsonl --candidate det_starter
# -> 3122/5774 MAIN decisions declined a legal ATTACK
```

## Tests + git evidence
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'          # 113 OK
.venv/bin/python -m unittest tests.test_gauntlet_stats tests.test_gauntlet_analysis -v \
  > results/test_logs/statistical_analysis_tests.txt
git commit -m "c004: add ranking analysis and baseline selection evidence"  # 9cc8426 (final HEAD)
git diff afe52db..9cc8426 -- starter_kit tools tests > results/artifacts/c004.patch
git diff --check afe52db..9cc8426        # no whitespace errors
git status --short > results/test_logs/final_git_status.txt
```
