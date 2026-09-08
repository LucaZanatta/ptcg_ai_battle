# Reproducibility — cabt Safe Agent

How a clean checkout of this branch becomes runnable, and exactly which commands
to run. All commands are run **from the repository root** with the project venv
(`.venv/bin/python`).

## 1. Asset categories

| Category | What | Where it comes from |
|----------|------|---------------------|
| **Git-tracked source/config** | `starter_kit/main.py`, `starter_kit/safe_policy.py`, `starter_kit/episode_capture.py`, `tests/`, `tools/`, `runtime_assets.json`, `.gitignore`, this file | This contract branch (git). |
| **External runtime assets** | `starter_kit/api.py`, `sim.py`, `game.py`, `utils.py`, `__init__.py`, `deck.csv`, and the native engine `starter_kit/libcg.so`; the `cg` and `starter_kit/cg` symlinks | Official cabt competition starter kit — **not committed** (native binary is `.gitignore`d as `*.so`; starter-kit files are provided out-of-band). Declared in `runtime_assets.json` with sha256. |
| **External package** | `kaggle-environments==1.30.1` (ships the built-in `cabt` env) | `pip install kaggle-environments==1.30.1`. |
| **Generated artifacts** | Episode JSONL, reports, coverage files | Produced by the commands below; episode data is `.gitignore`d. |

A clean checkout has the tracked source but **not** the external assets. Provide
them by copying the starter-kit files to `starter_kit/`, creating the two
symlinks, and installing `kaggle-environments`, then verify with the command below.

## 2. Provide the external assets

```bash
# From the official cabt starter kit, place these files:
#   starter_kit/api.py  starter_kit/sim.py  starter_kit/game.py
#   starter_kit/utils.py  starter_kit/__init__.py  starter_kit/deck.csv  starter_kit/libcg.so
# Then create the symlinks that make `from cg.api import ...` resolve:
ln -s starter_kit cg
( cd starter_kit && ln -s . cg )
# Install the competition harness:
.venv/bin/pip install kaggle-environments==1.30.1
```

Expected sha256 values for the external assets are recorded in `runtime_assets.json`.

## 3. Verify runtime assets

```bash
.venv/bin/python tools/verify_runtime_assets.py            # human-readable table; exit 0 iff all required pass
.venv/bin/python tools/verify_runtime_assets.py --json     # machine-readable
```

## 4. Run the tests

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Unit tests are side-effect free (they write only to temporary directories) and
do not modify any `contracts/*/results/` folder.

## 5. Run one cabt game

```bash
.venv/bin/python tools/capture_episodes.py --mode capture \
    --games-per-cohort 1 --base-seed 777 \
    --output /tmp/one_game.jsonl --summary /tmp/one_game_summary.json
```

(Prints `captured 3/3 games` — one game per cohort — and writes a JSONL trace.)

## 6. Capture episodes (60 games)

```bash
.venv/bin/python tools/capture_episodes.py --mode capture \
    --games-per-cohort 20 --base-seed 777 \
    --output  contracts/c002_reproducible_episode_capture/results/artifacts/episodes/episodes.jsonl \
    --summary contracts/c002_reproducible_episode_capture/results/artifacts/episode_run_summary.json
```

Validate and report:

```bash
.venv/bin/python tools/validate_episode_jsonl.py \
    contracts/c002_reproducible_episode_capture/results/artifacts/episodes/episodes.jsonl

.venv/bin/python tools/context_coverage_report.py \
    contracts/c002_reproducible_episode_capture/results/artifacts/episodes/episodes.jsonl \
    --json contracts/c002_reproducible_episode_capture/results/artifacts/context_coverage.json \
    --csv  contracts/c002_reproducible_episode_capture/results/artifacts/context_coverage.csv \
    --md   contracts/c002_reproducible_episode_capture/results/artifacts/CONTEXT_COVERAGE.md
```

## 7. Reproducibility scope (important)

Seeds and seat assignments are **fully reproducible** from `--base-seed`. The
cabt engine, however, seeds its own RNG from `std::random_device` (OS entropy)
and exposes no seed API, so **game trajectories (decision counts, winners) are
not reproducible** across runs — even with identical deterministic agents and
the same `configuration.seed`. What *is* reproducible: derived seeds, seat
schedule, and the safe agent's decision for a given recorded observation
(a pure function). See `--mode replay-check`:

```bash
.venv/bin/python tools/capture_episodes.py --mode replay-check --games-per-cohort 20 --base-seed 777
```
