# Commands run — c014

Run from the repository root with `.venv/bin/python`. Long jobs used harness-tracked background
tasks.

## Phase 0 — starting state, evidence, selection

```bash
git status --short; git branch --show-current; git rev-parse HEAD; git log -5 --oneline
git checkout -b contract/c014_public_meta_baseline_and_rapid_submission

# mining clock + pre-c014 immutability baseline, stamped BEFORE any edit
.venv/bin/python - <<'PY'   # writes mining_clock.json and immutability_baseline_pre_c014.json
PY

# deck floor: prove a legal non-Dragapult deck exists and plays, before mining for a better one
.venv/bin/python - <<'PY'   # mega_lucario vs dragapult, DONE/DONE, 0 invalid
PY

# authoritative competition facts via the Kaggle CLI
.venv/bin/kaggle competitions list -s pokemon-tcg -v
.venv/bin/kaggle competitions submissions pokemon-tcg-ai-battle -v
.venv/bin/kaggle competitions leaderboard pokemon-tcg-ai-battle -s --csv
.venv/bin/kaggle kernels list --competition pokemon-tcg-ai-battle --sort-by voteCount --page-size 20 -v
.venv/bin/kaggle kernels pull <ref> -p <snapshot dir> -m     # x7 notebooks

.venv/bin/python tools/c014_phase0.py
```

Mining elapsed **0.14 h** against a 4–6 h box: the Kaggle CLI returns authoritative, timestamped,
hashable rows, so almost no time went to scraping.

## Phase 1 — deterministic expert

```bash
.venv/bin/python -m unittest tests.test_c014_expert -v      # 17 tests
```

Two defects were found by measurement during development and are documented in `RULES.md`:

1. ATTACH scored below card plays → the agent emptied its hand every turn, never attached
   energy, and never attacked. Raised above all plays except the evolution.
2. Empty bench measured at 12.4 decisions/game → added the bench-liability rule (any benchable
   Pokémon outranks non-evolution plays while the bench is empty).

## Phase 2 — compact validation

```bash
.venv/bin/python tools/c014_validate.py --games 600 --trace-games 80 --out-prefix local
```

## Phase 3 — package and submit

```bash
.venv/bin/python tools/c014_package.py --stage validate --games 150
.venv/bin/python tools/c014_submit.py                # preflight only, no upload
.venv/bin/python tools/c014_submit.py --execute      # mandatory upload (§14)
```

Actual upload command (credentials resolved by the CLI, never read by the tool):

```bash
.venv/bin/kaggle competitions submit pokemon-tcg-ai-battle \
  -f contracts/c014_.../results/artifacts/submission_H_public_meta_v0.tar.gz \
  -m "c014 public-meta-v0 archaludon-cinderace 95c67e4"
```

Result: ref **55004756**, status **COMPLETE**, public score **600.0**, 3 bounded polls.

## Phase 4 — wrap-up, bundle, integrity

```bash
.venv/bin/python tools/c014_reports.py
.venv/bin/python tools/c014_build_source_bundle.py
# immutability recheck against the baseline captured at the START of c014
```

1,802 files across c005–c013 rechecked: **0 modified, 0 missing**.

## Game budget

```text
direct validation    600
package validation   150
------------------------
total                750   (§7 band: 500-1,000)
training games         0   (§7 requires exactly 0)
```

## Commits

```text
95c67e4 c014: Archaludon ex/Cinderace deterministic expert, validation and package
<later> c014: submission wrapper, reports, tests and source bundle
```
