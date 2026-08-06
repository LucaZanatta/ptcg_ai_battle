# Commands run — c016

## Phase 0 — start, raw ingest, immutability

```bash
git status --short; git branch --show-current; git rev-parse HEAD; git log -12 --oneline
git checkout -b contract/c016_public_agent_reproduction_gauntlet_and_champion_submission
# from the exact c015 final HEAD 6c5e602, verified against c015 STATUS.json
.venv/bin/python tools/c016_prior_audit.py    # raw re-derivation of c014/c015
```

Found **3 report-integrity defects in c015**, the most serious a Mechanism B success rate
asserted over a zero denominator.

## Phase 1 — facts, inventory, permission

```bash
.venv/bin/python tools/c016_phase1.py
```

The Kaggle API exposes **no licence field for kernels** — verified by listing kernel objects and
inspecting every attribute. Official samples are `SUBMISSION_REUSE_ALLOWED` on the factual basis
that c005 packaged one and Kaggle accepted and scored it; community notebooks are
`LOCAL_BENCHMARK_ONLY` and their source is never copied or packaged.

## Phase 2 — exact candidate reproduction

```bash
.venv/bin/python tools/c016_candidates.py
.venv/bin/python -m unittest tests.test_c016_gauntlet -v     # 16 tests
```

An early fidelity probe demanded Dragapult-specific identifiers (`AttackPlan`) from every agent
and failed Iono and Abomasnow for not having one. For a byte-identical copy the hash **is** the
anti-simplification proof.

## Phase 3 — frozen protocol, screening, gauntlet, confirmation

```bash
.venv/bin/python tools/c016_gauntlet.py --stage protocol        # committed at cc64cb5
.venv/bin/python tools/c016_gauntlet.py --stage screen          # Stage A
.venv/bin/python tools/c016_gauntlet.py --stage final           # Stage B
.venv/bin/python tools/c016_gauntlet.py --stage confirm         # independent seeds
.venv/bin/python tools/c016_gauntlet.py --stage confirm_topup   # to the registered minimums
.venv/bin/python tools/c016_select.py
```

The top-up is documented in `CONFIRMATION_TOPUP_NOTE.md`: §17's 200/300 are floors, while §18's
strength paths require 400/600, so the gate is unevaluable at the floor. Run once, to a fixed
target, for both finalists and the control.

## Phase 4 — package and submit

**Not performed.** The competitive gate failed, and §2/§18 forbid uploading a weak package
merely to complete the contract.

## Phase 5 — board, validation, bundle

```bash
.venv/bin/python tools/c016_reports.py
.venv/bin/python tools/c016_build_source_bundle.py
.venv/bin/python tools/c016_validate.py
```

## Game budget

```text
screening      360
final gauntlet 2,250
confirmation   2,900
--------------------
total          5,510      training games: 0
```
