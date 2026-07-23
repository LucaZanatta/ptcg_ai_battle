"""c000 AC-05: run N>=10 `cabt` games with the random baseline agent and record
per-game wall-clock + step count, then aggregate min/mean/max.

Writes baseline_metrics.json next to this script. Run from the repo root:
    .venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/baseline_measure.py
"""
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__)).split("/contracts/")[0]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

from kaggle_environments import make
from cg.api import to_observation_class

N_GAMES = 10

with open(os.path.join(REPO, "starter_kit", "deck.csv")) as f:
    DECK = [int(line.strip()) for line in f if line.strip()]
assert len(DECK) == 60, f"deck.csv must have 60 cards, got {len(DECK)}"


def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return DECK
    return random.sample(range(len(obs.select.option)), obs.select.maxCount)


games = []
for i in range(N_GAMES):
    t0 = time.time()
    env = make("cabt", configuration={"decks": [DECK, DECK]})
    env.run([random_agent, random_agent])
    elapsed = time.time() - t0
    last = env.steps[-1]
    s0, s1 = last[0]["status"], last[1]["status"]
    r0, r1 = last[0].get("reward"), last[1].get("reward")
    completed = s0 == "DONE" and s1 == "DONE"
    games.append({
        "game": i + 1,
        "seconds": round(elapsed, 3),
        "steps": len(env.steps),
        "p0_status": s0, "p1_status": s1,
        "p0_reward": r0, "p1_reward": r1,
        "completed": completed,
    })
    print(f"Game {i+1:2d}: {elapsed:6.2f}s | steps: {len(env.steps):3d} | "
          f"{s0}/{s1} | reward {r0}/{r1} | {'OK' if completed else 'NOT_DONE'}")

times = [g["seconds"] for g in games]
steps = [g["steps"] for g in games]
completed_count = sum(1 for g in games if g["completed"])


def stats(xs):
    return {"min": min(xs), "mean": round(sum(xs) / len(xs), 3), "max": max(xs)}


summary = {
    "n_games": N_GAMES,
    "completed_games": completed_count,
    "all_completed": completed_count == N_GAMES,
    "seconds": stats(times),
    "steps": stats(steps),
    "python": sys.version.split()[0],
    "games": games,
}

with open(os.path.join(HERE, "baseline_metrics.json"), "w") as f:
    json.dump(summary, f, indent=2)

print()
print(f"Completed {completed_count}/{N_GAMES} games")
print(f"Seconds  -> min {summary['seconds']['min']:.2f} "
      f"mean {summary['seconds']['mean']:.2f} max {summary['seconds']['max']:.2f}")
print(f"Steps    -> min {summary['steps']['min']} "
      f"mean {summary['steps']['mean']} max {summary['steps']['max']}")
sys.exit(0 if completed_count == N_GAMES else 1)
