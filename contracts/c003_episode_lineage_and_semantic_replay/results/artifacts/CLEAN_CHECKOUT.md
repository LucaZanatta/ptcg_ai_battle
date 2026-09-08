# Clean Checkout & Run — c003 (schema v2)

How to reproduce schema-v2 capture and validation from a clean checkout of
branch `contract/c003_episode_lineage_and_semantic_replay` (final HEAD
`afe52dbbbc75e6ee592bb4a6878fd4dfa43d0525`). Run all commands **from the repo
root** with `.venv/bin/python`.

## 1. Tracked vs external

**Git-tracked (present after checkout):** `starter_kit/{main,safe_policy,
episode_capture,episode_schema,agents,episode_capture_v2,episode_compat}.py`,
`tools/*.py`, `tests/*.py`, `runtime_assets.json`, `REPRODUCIBILITY.md`, `.gitignore`.

**External runtime assets (NOT in git — provide out-of-band; see `runtime_assets.json`):**
`starter_kit/{api,sim,game,utils,__init__}.py`, `starter_kit/deck.csv`,
`starter_kit/libcg.so` (native `*.so`, `.gitignore`d), and the symlinks
`cg -> starter_kit`, `starter_kit/cg -> .`. Install `kaggle-environments==1.30.1`.

## 2. Provide externals + verify
```bash
# copy the starter-kit files into starter_kit/, then:
ln -s starter_kit cg ; ( cd starter_kit && ln -s . cg )
.venv/bin/pip install kaggle-environments==1.30.1
.venv/bin/python tools/verify_runtime_assets.py            # c002 manifest verifier
.venv/bin/python tools/environment_report.py --json /tmp/env.json   # v2 env/engine check
```

## 3. Run tests
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v    # 84 tests OK
```

## 4. Capture a schema-v2 dataset (from a clean tree)
```bash
.venv/bin/python tools/capture_episodes_v2.py --games-per-cohort 10 --base-seed 4242 \
    --require-clean --output-dir /tmp/run_v2
```
`--require-clean` refuses to capture if tracked files are modified, so the run's
`run_metadata.git.dirty` is `false` and its source/engine hashes match the branch.

## 5. Validate + semantic replay (jsonl and gzip)
```bash
.venv/bin/python tools/validate_episodes_v2.py /tmp/run_v2/episodes_v2.jsonl \
    --validation-report /tmp/val.json --semantic-report /tmp/sem.json \
    --context-report /tmp/ctx.json --latency-report /tmp/lat.json
.venv/bin/python tools/validate_episodes_v2.py /tmp/run_v2/episodes_v2.jsonl.gz
```
Expected: 0 structural errors, 100% semantic replay of safe-agent decisions,
identical results for jsonl and gzip.

## 6. Reproducibility scope
Seeds and seat assignments reproduce from `--base-seed`. The cabt **engine**
trajectory does NOT reproduce (std::random_device seeding; `engine_rng_controlled`
is recorded as `false`). Semantic replay reproduces the deterministic policy's
decision from the serialized observation — not the engine trajectory.

## 7. Results policy
The contract `results/` package (this folder) is review evidence and is not
committed to git; generated episode data is `.gitignore`d. All source needed to
reproduce the above is committed on the branch.
