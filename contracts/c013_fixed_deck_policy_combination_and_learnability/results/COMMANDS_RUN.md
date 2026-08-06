# Commands run — c013

Executed against `.venv/bin/python` from the repository root on the branch
`contract/c006_distilled_policy_baseline`. Long jobs ran as harness-tracked background tasks;
`nohup … &` inside a foreground call is deliberately not used, because in c012 that hid a
completed training chain for three hours.

## Phase 0 — dependencies, repairs, registries

```bash
.venv/bin/python tools/c013_registry.py --stage deps
.venv/bin/python tools/c013_registry.py --stage freeze
.venv/bin/python tools/c013_registry.py --stage combinations
.venv/bin/python -m unittest tests.test_c013_ensemble_math -v
.venv/bin/python -m unittest tests.test_c013_continuation -v
.venv/bin/python tools/c013_phase_evidence.py
```

## Phase 1 — combination panels

```bash
.venv/bin/python tools/c013_eval.py --panel selection    --candidates ALL --nproc 16
.venv/bin/python tools/c013_eval.py --panel confirmation --candidates FINALISTS --nproc 16
.venv/bin/python tools/c013_eval.py --panel final        --candidates FINALISTS --nproc 16
.venv/bin/python tools/c013_combination_report.py
```

## Phase 2 — soup learnability

```bash
.venv/bin/python tools/c013_learnability.py --arm Q0  --seed 901 --max-games 12000 --nproc 16
.venv/bin/python tools/c013_learnability.py --arm Q1  --seed 902 --max-games 12000 --nproc 16
.venv/bin/python tools/c013_learnability.py --arm Q2A --seed 903 --max-games 10000 --nproc 16
.venv/bin/python tools/c013_learnability.py --arm Q2B --seed 904 --max-games 10000 --nproc 16
.venv/bin/python tools/c013_recombine.py
.venv/bin/python tools/c013_eval.py --panel confirmation --candidates ALL_NEW --nproc 16
.venv/bin/python tools/c013_learnability_report.py --panel confirmation
```

Q1 was relaunched once: `torch.Generator().manual_seed(seed)` defaults to CPU while the model
tensors are on CUDA, raising `RuntimeError: Expected a 'cuda' device type for generator but
found 'cpu'`. Fixed with `torch.Generator(device=model.dev)`.

## Phase 3 — curriculum smoke

```bash
.venv/bin/python tools/c013_curriculum_smoke.py --arm R0 --seed 1001 --max-games 5000 --nproc 16
.venv/bin/python tools/c013_curriculum_smoke.py --arm R1 --seed 1002 --max-games 5000 --nproc 16
.venv/bin/python tools/c013_smoke_finalize.py      # backfill the game-5,000 evaluation
.venv/bin/python tools/c013_smoke_report.py
```

## Phase 4 — opponent overlap

```bash
.venv/bin/python tools/c013_overlap_analysis.py --stage collect --games 48 --max-states 150 \
    --neural '{"S611": "...", "S622": "...", "S633": "...", "C012_SOUP_622_633": "...", "P0_711": "..."}'
.venv/bin/python tools/c013_overlap_analysis.py --stage analyze
```

A one-game smoke ran first to confirm the shadow-query loop and the Struct-based permutation
round-trip worked against the real libcg-backed observation before the full panel was collected.

## Phase 5 — Claude semantic preflight

```bash
.venv/bin/python tools/c013_claude_preflight.py --stage build  --n 28
.venv/bin/python tools/c013_claude_preflight.py --stage label  --n 28 --max-cost 14
.venv/bin/python tools/c013_claude_preflight.py --stage repeat --n 10 --max-cost 6
.venv/bin/python tools/c013_claude_preflight.py --stage analyze
```

Each label is one `claude -p <prompt> --model opus --allowed-tools "" --output-format json`
subprocess: tools disabled, no session persistence between calls, and the resolved model read
back from `modelUsage`. Total cost $12.81 primary + repeat pass.

## Phase 6 — decisions, validation, bundle, reports

```bash
.venv/bin/python tools/c013_decide.py
.venv/bin/python tools/c013_validate_evidence.py
.venv/bin/python tools/c013_build_source_bundle.py
.venv/bin/python tools/c013_reports.py
.venv/bin/python tools/c013_registry.py --stage immutability     # run LAST
```

No Kaggle command was executed. `SUBMISSION_G = DO_NOT_SUBMIT`, and §32 authorises an upload
when and only when the gate is `SUBMIT`; `KAGGLE_SUBMIT_COMMAND.txt` records the command that
would have run, marked not executed.

## Commits

```text
8112dcd c013: registries, online ensemble implementation and identity-safe ensemble evaluation
0ba73d1 c013: soup learnability trainer (Q0 direct, Q1 value refit, Q2 component continue)
1f95c94 c013: semantic serializer and adaptive-curriculum smoke harness
79e361f c013: semantic claude preflight with decoded cards and typed actions
0543b8e c013: opponent overlap on identical states via shadow-query loop
efbb9b5 c013: decode options via engine OptionType and split clean/probe instances
10fcbd2 c013: repair-aware label scoring and tolerant output reading
61455bf c013: pair overlap series jointly and add exact-choice identity
23fe9d1 c013: combination panels recomputed from raw games, plus Q3 gate
5c02ca1 c013: learnability verdict, repair evidence, and carried-forward repair tests
e0bb445 c013: content-aware validator that re-derives every headline claim
455d65b c013: curriculum smoke evaluation flush, backfill, report, and decisions
```
