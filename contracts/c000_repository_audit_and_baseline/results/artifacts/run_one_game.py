"""c000 AC-04: run exactly one `cabt` game with the random baseline agent.

Minimal, self-contained reproduction. Run from the repo root:
    .venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/run_one_game.py
"""
import os
import random
import sys

REPO = os.path.dirname(os.path.abspath(__file__)).split("/contracts/")[0]
sys.path.insert(0, REPO)

from kaggle_environments import make
from cg.api import to_observation_class

with open(os.path.join(REPO, "starter_kit", "deck.csv")) as f:
    DECK = [int(line.strip()) for line in f if line.strip()]
assert len(DECK) == 60, f"deck.csv must have 60 cards, got {len(DECK)}"


def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:          # deck-selection phase
        return DECK
    return random.sample(range(len(obs.select.option)), obs.select.maxCount)


env = make("cabt", configuration={"decks": [DECK, DECK]})
env.run([random_agent, random_agent])

last = env.steps[-1]
print(f"steps: {len(env.steps)}")
print(f"player0 status: {last[0]['status']} reward: {last[0].get('reward')}")
print(f"player1 status: {last[1]['status']} reward: {last[1].get('reward')}")
ok = last[0]["status"] == "DONE" and last[1]["status"] == "DONE"
print("ONE_GAME_COMPLETED" if ok else "ONE_GAME_NOT_DONE")
sys.exit(0 if ok else 1)
