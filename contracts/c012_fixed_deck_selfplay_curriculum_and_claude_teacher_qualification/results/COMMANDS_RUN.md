# c012 — COMMANDS_RUN

Run from the repository root with `.venv/bin/python`. `$ART` is
`contracts/c012_.../results/artifacts`.

## Phase 0 — repair, confirm, freeze (AC-01..AC-05)
```bash
.venv/bin/python tools/c012_phase0.py                       # deps, immutability, candidate registry
.venv/bin/python -m unittest tests.test_c012_rng_restore    # §7 active-Generator restore
.venv/bin/python -m unittest tests.test_c012_continuation   # §7 TRUE continuation + negative control
.venv/bin/python tools/c012_eval.py --panel confirmation \
    --candidates "<9 unconfirmed c011 candidates>" --nproc 16
.venv/bin/python tools/c012_elite.py --stage register       # ensembles + soups, weights frozen first
.venv/bin/python tools/c012_eval.py --panel confirmation \
    --candidates "SOUP_611+622,SOUP_611+633,SOUP_622+633,SOUP_611+622+633,S_633_g30176" --nproc 16
.venv/bin/python tools/c012_elite.py --stage freeze          # TRUE_INCUMBENT / ELITE / POOL
```

## Phase 1 — overlap and curriculum lock (AC-06/07)
```bash
.venv/bin/python tools/c012_overlap.py --stage crossplay --nproc 16 --games-per-pair 12
.venv/bin/python tools/c012_overlap.py --stage analyze
.venv/bin/python tools/c012_overlap.py --stage lock          # writes curriculum_registry.sha256
```
The trainer re-hashes `curriculum_registry.json` at startup and refuses to run on a mismatch,
so the §20 lock is mechanical rather than a promise.

## Phase 2 — controlled curriculum (AC-08/09/10)
```bash
for spec in "P0 711" "P0 722" "P0 733" "P1 811" "P1 822" "P1 833"; do
  set -- $spec
  .venv/bin/python tools/c012_train_population.py --arm $1 --seed $2 \
      --nproc 16 --max-games 30000 --device cuda
done
```
Sequential; 16 workers was the c011-calibrated optimum.

## Phase 2 evaluation and decisions
```bash
.venv/bin/python tools/c012_eval.py --panel screen --candidates ALL_NEW --nproc 16
.venv/bin/python tools/c012_eval.py --panel confirmation --candidates "<best 2 per seed>" --nproc 16
.venv/bin/python tools/c012_eval.py --panel final \
    --candidates "T_teacher,SOUP_622+633,<best per seed>" --nproc 16
.venv/bin/python tools/c012_decide.py
```

## Phase 3/4 — benchmark and Claude (AC-11/12/13)
```bash
.venv/bin/python tools/c012_hard_states.py --primary 240 --repeat 48
.venv/bin/python tools/c012_claude_label.py --stage preflight
.venv/bin/python tools/c012_claude_label.py --stage label  --n 60 --max-cost 22
.venv/bin/python tools/c012_claude_label.py --stage repeat --n 40 --max-cost 12
.venv/bin/python tools/c012_claude_qualify.py
```
Every Claude call: `claude -p <frozen prompt> --model opus --allowed-tools "" --output-format json`
— non-interactive, Opus requested explicitly and verified per call from `modelUsage`, tools
disabled, sequential, raw prompt and response saved.

## Phase 5 — validation, bundle, reports (AC-15/16)
```bash
.venv/bin/python tools/c012_validate_evidence.py --quiet
.venv/bin/python tools/c012_build_source_bundle.py --stage all
.venv/bin/python tools/c012_reports.py
.venv/bin/python tools/c012_summary.py
```

## Kaggle
`SUBMISSION_F = DO_NOT_SUBMIT`, so **no upload ran** and no archive was built. The only Kaggle
call was the read-only teacher refresh:
```bash
kaggle competitions submissions pokemon-tcg-ai-battle -v    # teacher ref 54948560
```
No credentials appear in any artifact or log.

## Corrections made mid-run
- The training chain was first launched with `nohup` inside a foreground call, so its
  completion was not surfaced for ~3 hours. Every later long job is a harness-tracked task.
- In-run evaluation pointed at a rewritten `cur.npz`; the per-path hash cache in
  `cg.c009_eval` then returned stale hashes and every evaluation after game 0 scored nothing.
  Evaluations now use content-addressed paths and an empty evaluation is a hard error. See
  `failures/DEFECT_inrun_evaluation_stale_hash.md`.
- Claude labelling initially died on one 180 s timeout and lost all completed work; calls now
  degrade to a recorded failure and results flush per label.
- Serialized states initially exposed only option counts; they now carry runtime-visible card
  content so the labelling task is meaningful.
- Claude schema/legality rates are computed over calls that RETURNED; subprocess timeouts are
  reported separately as call failures rather than counted as model errors.
