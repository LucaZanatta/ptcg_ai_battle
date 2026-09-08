# Minimal Reproducible Command — Run One Game

## Command (from repo root)
```bash
.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/run_one_game.py
```

## What it does
Loads `starter_kit/deck.csv` (60 cards), builds `make("cabt", configuration={"decks": [deck, deck]})`,
and runs one game with two random agents, then prints the terminal status/reward
for both players.

## Verified output (see `test_logs/run_one_game.txt`)
```
steps: 139
player0 status: DONE reward: 1
player1 status: DONE reward: -1
ONE_GAME_COMPLETED
```
Exit code: `0`.

## Equivalent inline snippet
```python
import random, sys
sys.path.insert(0, ".")                      # repo root, so `cg` symlink resolves
from kaggle_environments import make
from cg.api import to_observation_class

deck = [int(x) for x in open("starter_kit/deck.csv") if x.strip()]  # 60 cards

def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return deck
    return random.sample(range(len(obs.select.option)), obs.select.maxCount)

env = make("cabt", configuration={"decks": [deck, deck]})
env.run([random_agent, random_agent])
print(env.steps[-1][0]["status"], env.steps[-1][1]["status"])   # DONE DONE
```

## Prerequisites
- `.venv` with `kaggle-environments==1.30.1`.
- `cg -> starter_kit` symlink present at repo root.
- Run from the repo root (or keep the `sys.path` insert pointing at it).
