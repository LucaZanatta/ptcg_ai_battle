# Repository Map — `ptcg_ai_battle`

Top-level entries (excluding `.git/` and `.venv/` internals).

| Entry | Type | Size | Role |
|-------|------|------|------|
| `starter_kit/` | dir | 1.4M | Competition starter kit: engine bindings + baseline agent (see `entry_points.md`). |
| `cg` | symlink → `starter_kit` | 0 | Makes `from cg.api import ...` resolve from repo root. Mirrored by `starter_kit/cg -> .`. |
| `test_engine.py` | file | 4.0K | Existing harness: runs 20 `cabt` games with a random agent via `kaggle_environments.make`. |
| `check.py` | file | 4.0K | Ad-hoc `os.walk` dump of the repo (hard-coded absolute path). Not part of the engine. |
| `pokemon-tcg-ai-battle-challenge-strategy/` | dir | 306M | Reference card data: `EN_Card_Data.csv`, `JP_Card_Data.csv` (2,102 cards each), plus two large card-ID list PDFs. |
| `contracts/` | dir | 40K | Contract folders (this audit lives here). Not project source. |
| `tmp.txt` | file | 4.4M | Scratch file (appears to be a card-ID dump). Not referenced by any code. |
| `.gitignore` | file | 8.0K | Python-template gitignore (from the GitHub initial commit). |
| `.venv/` | dir | 1.4G | Local virtualenv (Python 3.13). Not committed. |

## `starter_kit/` contents

| File | Size | Role |
|------|------|------|
| `libcg.so` | 1.3M | Compiled game engine (x86-64 ELF shared object). Core dependency. |
| `api.py` | 26.9K | Dataclasses + enums for the observation model; `to_observation_class`, `all_card_data`, `all_attack`, and the forward-search API (`search_begin/step/end/release`). |
| `sim.py` | 2.0K | `ctypes` bindings that load `libcg.so` and declare all FFI signatures. |
| `game.py` | 2.2K | Thin battle driver: `battle_start`, `battle_select`, `battle_finish`, `visualize_data`. |
| `main.py` | 1.3K | Baseline agent entry point: `read_deck_csv()` + `agent(obs_dict)` (random legal selection). |
| `utils.py` | 2.0K | `to_dataclass` / `json_to_dataclass` recursive converters. |
| `deck.csv` | 245B | 60-card deck (9 unique card IDs: 3, 721, 722, 723, 1145, 1158, 1205, 1227, 1235). |
| `__init__.py` | 0B | Marks `starter_kit`/`cg` as a package. |

## Notes

- The competition harness is the **built-in** `cabt` environment shipped inside
  `kaggle-environments==1.30.1` (`.venv/.../kaggle_environments/envs/cabt/`). It
  wraps the same engine family; no custom env registration is required.
- Untracked, out-of-scope files present in the working tree: `tmp.txt`,
  `check.py`, `cg`, `pokemon-tcg-ai-battle-challenge-strategy/`, `starter_kit/`.
