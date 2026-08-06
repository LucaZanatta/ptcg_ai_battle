# Commands run — c015

## Hard start gate (§7) — before any implementation

```bash
git status --short; git branch --show-current; git rev-parse HEAD; git log -8 --oneline
.venv/bin/python tools/c015_gate.py          # gate: PASS, 6/6 blocking checks
git checkout -b contract/c015_anti_meta_deck_agent_v0    # from the verified c014 HEAD 7edfb81
```

The gate re-hashes c014's archive from its own bytes rather than reading its manifest, and
requires that hash to match both the manifest and `STATUS.json`.

## Phase 0 — delta check and thesis freeze

```bash
# delta clock + pre-c015 immutability baseline (1,873 files, c005-c014), stamped before edits
.venv/bin/python tools/c015_delta.py
```

Delta check elapsed **0.063 h** against a 1–2 h cap. One material change found: c014's public
score had moved from 600.0 to 754.5.

## Phase 1 — deterministic anti-meta expert

```bash
.venv/bin/python -m unittest tests.test_c015_expert -v      # 20 tests
```

Two measurement bugs were found and fixed during development, both documented in
`COUNTER_MECHANISMS.md`:

1. Mechanism B measured **zero** opportunities because the engine presents each attack as its own
   MAIN option; the scaled-damage logic lived only in the separate ATTACK context.
2. Mechanism A read **0.334** because availability was counted on search/discard decisions where
   the ability is not offered. Restricted to MAIN, it is **1.000**.

A development A/B before the final panel chose the opening: Voltorb-first 0.250, Tadbulb-first
0.400 against the target.

## Phase 2 — compact validation

```bash
.venv/bin/python tools/c015_validate.py --games 600 --trace-games 90 --out-prefix local
```

Panel includes the **exact c014 package** as the target implementation — §12's proxy concession
was not needed.

## Phase 3 — package and submit

```bash
.venv/bin/python tools/c015_package.py --stage validate --games 150
.venv/bin/python tools/c015_submit.py                # preflight only
.venv/bin/python tools/c015_submit.py --execute      # mandatory upload (§15)
```

```bash
.venv/bin/kaggle competitions submit pokemon-tcg-ai-battle \
  -f contracts/c015_.../results/artifacts/submission_I_anti_meta_v0.tar.gz \
  -m "c015 anti-meta-v0 iono-bellibolt vs archaludon 15d9e69"
```

Result: ref **55005237**, status **COMPLETE**, 3 bounded polls.

## Phase 4 — board, reports, bundle, integrity

```bash
.venv/bin/python tools/c015_reports.py
.venv/bin/python tools/c015_build_source_bundle.py
# immutability recheck against the baseline captured at c015 START
```

1,873 files across c005–c014 rechecked: **0 modified, 0 missing**.

## Game budget

```text
direct validation    600
package validation   150
------------------------
total                750   (§12 band: 500-1,000)
training games         0   (§6 forbids any training)
```

## Commits

```text
15d9e69 c015: Iono Bellibolt anti-meta expert, validation and package
<later> c015: reports, tests, source bundle and decision board
```
