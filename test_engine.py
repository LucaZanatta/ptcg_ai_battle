import sys
import random
import time
import numpy as np
sys.path.insert(0, "/home/luca/kaggle/ptcg_ai_battle")

from kaggle_environments import make
from cg.api import to_observation_class

with open("/home/luca/kaggle/ptcg_ai_battle/starter_kit/deck.csv") as f:
    deck = [int(line.strip()) for line in f if line.strip()]

def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return deck  # deck selection phase
    return random.sample(list(range(len(obs.select.option))), obs.select.maxCount)

times = []
steps_list = []
for i in range(20):
    t0 = time.time()
    env = make("cabt", configuration={"decks": [deck, deck]})
    env.run([random_agent, random_agent])
    elapsed = time.time() - t0
    times.append(elapsed)
    steps_list.append(len(env.steps))
    print(f"Game {i+1}: {elapsed:.2f}s | steps: {len(env.steps)}")

print(f"\nMean: {np.mean(times):.2f}s | Min: {np.min(times):.2f}s | Max: {np.max(times):.2f}s")
print(f"Mean steps: {np.mean(steps_list):.1f} | Min: {np.min(steps_list)} | Max: {np.max(steps_list)}")

last = env.steps[-1]
print(f"\nFinal status: {last[0]['status']}, {last[1]['status']}")