# Clean Checkout & Run — c004

Reproduce the gauntlet + analysis from a clean checkout of branch
`contract/c004_competitive_baseline_gauntlet` (final HEAD
`9cc842681fedde99f8aec131a8ef46d052bce7c5`). Run from the repo root with
`.venv/bin/python`.

## 1. External runtime assets (as in c002/c003)
Git-tracked: all `starter_kit/*.py` added by c001–c004 (incl. `candidates.py`,
`gauntlet_stats.py`, `replay_registry.py`), `tools/*.py`, `tests/*.py`,
`runtime_assets.json`. Provide externally (see `runtime_assets.json`): the
starter-kit `api/sim/game/utils/__init__/deck.csv` files, native `libcg.so`
(`.gitignore`d), the `cg` / `starter_kit/cg` symlinks, and
`kaggle-environments==1.30.1` (which also supplies the **cabt built-in deck** used
by the `*_cabt` candidates). Verify:
```bash
ln -s starter_kit cg ; ( cd starter_kit && ln -s . cg )
.venv/bin/pip install kaggle-environments==1.30.1
.venv/bin/python tools/verify_runtime_assets.py
.venv/bin/python tools/environment_report.py --json /tmp/env.json
```

## 2. Tests
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v   # 113 tests OK
```

## 3. Run the gauntlet (from a clean tree)
```bash
.venv/bin/python tools/run_gauntlet.py --base-seed 90210 --require-clean --out-dir /tmp/gauntlet
```
`--require-clean` refuses a dirty tracked tree so `run_metadata.git.dirty=false`
and candidate/source hashes match the branch.

## 4. Analyze + select + mine
```bash
.venv/bin/python tools/analyze_gauntlet.py --in-dir /tmp/gauntlet --out-dir /tmp/gauntlet
.venv/bin/python tools/mine_tactical_failures.py --in-dir /tmp/gauntlet \
  --out /tmp/gauntlet/tactical_failure_examples.jsonl --candidate det_starter
```

## 5. Reproducibility scope
The **analysis** (Bradley-Terry, bootstrap ranking, selection) is fully
reproducible from a fixed `gauntlet_games.jsonl.gz` (seeded bootstrap → identical
ranking; tested). The **gauntlet capture itself is not** reproducible game-for-game:
the cabt engine seeds its RNG from `std::random_device` (`engine_rng_controlled=false`),
so a fresh run produces different games and shifted point estimates — the
qualitative ranking (deterministic ≫ random; the two deterministic tied) is stable.

## 6. Results policy
The contract `results/` package is review evidence and is not committed; the
~700 KB gzip capture lives only there. All source needed to reproduce is on the branch.
