# Commands Run — c000

All commands run from repo root `/home/luca/kaggle/ptcg_ai_battle`. No secrets used.

## Git (state capture + branch)
```bash
git status --short
git branch --show-current            # main
git rev-parse HEAD                   # 82faa29929e28bbd287461bcac5d28574bdbc05a
git check-ignore -v contracts/       # (not ignored)
git switch -c contract/c000_repository_audit_and_baseline
```

## Environment inspection
```bash
uname -a
.venv/bin/python --version           # Python 3.13.13
.venv/bin/pip freeze > results/test_logs/pip_freeze.txt
.venv/bin/python -c "import kaggle_environments as k, os; print(sorted(os.listdir(os.path.dirname(k.__file__)+'/envs')))"   # cabt present
du -sh <top-level entries>
```

## Repo inspection
```bash
grep -nE '^(class |def |@dataclass)' starter_kit/api.py
grep -nE 'def search_(begin|step|end|release)' starter_kit/api.py
head -1 pokemon-tcg-ai-battle-challenge-strategy/EN_Card_Data.csv
wc -l pokemon-tcg-ai-battle-challenge-strategy/{EN,JP}_Card_Data.csv
sort -u starter_kit/deck.csv
```

## Baseline execution (evidence)
```bash
.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/run_one_game.py \
    > results/test_logs/run_one_game.txt 2>&1        # exit 0, ONE_GAME_COMPLETED

.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/baseline_measure.py \
    > results/test_logs/baseline_run.txt 2>&1        # exit 0, 10/10 completed
```

## Git (commit — see GIT_REPORT.md)
```bash
git add contracts/c000_repository_audit_and_baseline
git commit -m "c000: repository audit and baseline evidence"
```
