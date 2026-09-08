# Entry Points, Decks, Engine & Run Commands

## Agent entry point
- **`starter_kit/main.py:agent(obs_dict) -> list[int]`** — the baseline agent.
  - `obs = to_observation_class(obs_dict)`.
  - If `obs.select is None` → deck-selection phase → return the 60-card deck.
  - Otherwise → return `random.sample(range(len(obs.select.option)), obs.select.maxCount)`.
  - Contract: each returned index is `0 <= i < len(obs.select.option)`; list length
    in `[obs.select.minCount, obs.select.maxCount]`; no duplicates.
- `starter_kit/main.py:read_deck_csv()` — loads `deck.csv` (falls back to
  `/kaggle_simulations/agent/deck.csv` on the Kaggle runner).

## Deck files
- **`starter_kit/deck.csv`** — 60 card IDs, one per line. Unique IDs present:
  `3, 721, 722, 723, 1145, 1158, 1205, 1227, 1235` (9 distinct cards).
- Card reference data: `pokemon-tcg-ai-battle-challenge-strategy/EN_Card_Data.csv`
  and `JP_Card_Data.csv` — 2,102 rows each, columns include
  `Card ID, Card Name, HP, Type, Weakness, Retreat, Move Name, Cost, Damage, Effect Explanation`.

## Engine
- **`starter_kit/libcg.so`** — compiled engine.
- **`starter_kit/sim.py`** — `ctypes` loader + FFI signatures. Notable symbols:
  `GameInitialize`, `BattleStart`, `Select`, `GetBattleData`, `BattleFinish`,
  `VisualizeData`, and a **forward-search API** `SearchBegin`/`SearchStep`/
  `SearchEnd`/`SearchRelease`, `AllCard`, `AllAttack`.
- **`starter_kit/game.py`** — Python wrappers: `battle_start(deck0, deck1)`,
  `battle_select(list[int])`, `battle_finish()`, `visualize_data()`.
- **`starter_kit/api.py`** — observation model. Enums: `AreaType`, `EnergyType`,
  `CardType`, `SpecialConditionType`, `SelectType`, `SelectContext` (~28 decision
  contexts: MAIN, SETUP_ACTIVE_POKEMON, SWITCH, ATTACH_TO, EVOLVES_TO, DISCARD, …),
  `OptionType`, `LogType`. Dataclasses: `Card`, `Pokemon`, `PlayerState`, `State`,
  `Option`, `SelectData`, `Observation`, `CardData`, `Attack`. Python-level search
  helpers: `search_begin`, `search_step`, `search_end`, `search_release`.

## Run / test harnesses
| Command | What it does |
|---------|--------------|
| `.venv/bin/python test_engine.py` | Existing harness: 20 `cabt` games with a random agent, prints timing + steps + final status. (Uses a hard-coded absolute repo path.) |
| `.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/run_one_game.py` | c000 minimal one-game reproduction (AC-04). |
| `.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/baseline_measure.py` | c000 10-game measurement (AC-05). |

## Recommended integration points (for future contracts)
- Replace the body of `starter_kit/main.py:agent` (after the `obs.select is None`
  branch) to inject a real policy — the observation → action interface is stable.
- The `search_*` API in `api.py` is the natural hook for a planning/rollout agent.
- `all_card_data()` / `EN_Card_Data.csv` give static card features for a model.
