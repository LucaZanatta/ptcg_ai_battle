# Environment & Dependency Report

## Platform
- OS / kernel: `Linux luca 7.0.0-28-generic #28~24.04.1-Ubuntu SMP ... x86_64` (Ubuntu 24.04 base)
- Python: **3.13.13** (`.venv/bin/python`)
- Interpreter: project-local virtualenv at `.venv/`

## Key packages (from `test_logs/pip_freeze.txt`, 270 packages total)
| Package | Version | Relevance |
|---------|---------|-----------|
| `kaggle-environments` | **1.30.1** | Provides the built-in `cabt` competition environment. |
| `numpy` | 2.4.6 | Used by measurement/analysis code. |
| `kaggle` | 2.2.2 | Kaggle CLI/API (not required to run games locally). |
| `gym` | 0.26.2 | Transitive. |
| `gymnasium` | 1.2.0 | Transitive. |
| `jax` / `jaxlib` | 0.10.2 | Present but not used by the baseline. |

No `torch` / deep-learning framework is installed.

## `cabt` environment confirmation
`cabt` is a **registered built-in** environment (not a repo-local module):

```
.venv/lib/python3.13/site-packages/kaggle_environments/envs/cabt/
    cabt.py
    cabt.json
```

`sorted(os.listdir(kaggle_environments/envs))` includes `cabt` alongside
`connectx`, `halite`, `open_spiel_env`, etc. `make("cabt", ...)` constructs a
game successfully (see `RUN_ONE_GAME.md`).

## Engine
- `starter_kit/libcg.so` is a 1.3M x86-64 ELF shared object loaded via `ctypes`
  in `starter_kit/sim.py`. It loads without error (`lib.GameInitialize()` runs at
  import). A Windows counterpart (`cg.dll`) is referenced but not present — Linux
  is the supported platform here.

## Reproducibility note
All commands were run from the repo root using `.venv/bin/python`. The `cg`
symlink must exist at the repo root for `from cg.api import ...` to resolve.
