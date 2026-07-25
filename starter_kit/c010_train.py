"""c010 training rollout worker with full per-game metadata (§14).

Plays one training game with the current policy on one seat against a registered opponent and
returns both the PPO transitions and a compact per-game record carrying the identity of the
weights that produced it (policy checkpoint hash, opponent id + opponent checkpoint hash),
seat, outcome, decision counts, episode length, mean entropy, start/end value predictions, and
every reliability counter.

Nothing under c005–c009 is written; B0/I0 are only ever read.
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                       "results", "artifacts", "teacher_sources")
FROZEN_TEACHER_MAIN = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                                   "results", "artifacts", "frozen_teacher", "main.py")

_CUR = {"version": None, "policy": None}
_LAG: Dict[str, Any] = {}
_SHA: Dict[str, str] = {}


def sha256_file(p: str) -> str:
    if p not in _SHA:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        _SHA[p] = h.hexdigest()
    return _SHA[p]


def opponent_identity(spec) -> Dict[str, str]:
    """Stable identity for any registered opponent."""
    kind = spec[0]
    if kind == "teacher":
        return {"opponent_id": spec[1],
                "opponent_checkpoint_sha256": sha256_file(
                    os.path.join(SOURCES, spec[1], "main.py"))}
    if kind == "control":
        return {"opponent_id": "__control__", "opponent_checkpoint_sha256": "deterministic_control"}
    if kind == "lagged":
        return {"opponent_id": f"lagged::{os.path.basename(spec[1])}",
                "opponent_checkpoint_sha256": sha256_file(spec[1])}
    raise ValueError(spec)


def _build_opponent(spec, deck):
    kind = spec[0]
    if kind == "teacher":
        from cg.teachers import make_fresh
        return make_fresh(spec[1], SOURCES)
    if kind == "control":
        from cg.control_agent import DetControl
        return DetControl(deck)
    if kind == "lagged":
        from cg.rl_policy import RLPolicy
        from cg.rl_env import RLAgent
        pol = _LAG.get(spec[1])
        if pol is None:
            pol = RLPolicy.load(spec[1]); _LAG[spec[1]] = pol
            if len(_LAG) > 4:
                _LAG.pop(next(iter(_LAG)))
        return RLAgent(pol, deck, np.random.default_rng(spec[2]), collect=False, greedy=False)
    raise ValueError(spec)


class _EntropyRecordingPolicy:
    """Thin proxy over RLPolicy that records the per-decision entropy RLAgent does not keep.

    Used instead of editing ``cg.rl_env`` (c008 source, which must stay untouched); RLAgent
    only ever calls ``policy.act``.
    """

    def __init__(self, policy):
        self._p = policy
        self.entropies: List[float] = []

    def act(self, *a, **kw):
        r = self._p.act(*a, **kw)
        e = r.get("entropy")
        if e is not None:
            self.entropies.append(float(e))
        return r

    def __getattr__(self, name):
        return getattr(self._p, name)


def play_training_game(job: Dict[str, Any]) -> Dict[str, Any]:
    from kaggle_environments import make
    from cg.rl_policy import RLPolicy
    from cg.rl_env import RLAgent
    t0 = time.time()
    ck = job["policy_ckpt"]
    if _CUR["version"] != job["policy_version"] or _CUR["policy"] is None:
        _CUR["policy"] = RLPolicy.load(ck); _CUR["version"] = job["policy_version"]
    pol = _EntropyRecordingPolicy(_CUR["policy"])
    seat = job["seat"]
    rng = np.random.default_rng(job["rng_seed"])
    rl = RLAgent(pol, job["deck"], rng, collect=True, greedy=False)
    oid = opponent_identity(job["opponent"])
    opp = _build_opponent(job["opponent"], job["deck"])
    players = [rl, opp] if seat == 0 else [opp, rl]
    exc = None
    env = None
    try:
        env = make("cabt")
        env.run([lambda o: players[0](o), lambda o: players[1](o)])
    except Exception as e:  # noqa: BLE001
        exc = f"{type(e).__name__}:{e}"

    meta = {"arm": job["arm"], "seed": job["seed"], "game_index": job["game_index"],
            "policy_checkpoint_sha256": job["policy_sha256"], "policy_version": job["policy_version"],
            **oid, "seat": seat, "requested_seed": job["rng_seed"],
            "decisions": int(rl.n_decisions), "forced_decisions": int(rl.n_forced),
            "trainable_decisions": len(rl.transitions),
            # RLAgent counts a fallback for every failed policy decision; those that were
            # malformed selections (rather than raised exceptions) are the invalid actions.
            "fallbacks": int(rl.n_fallback),
            "invalid_actions": int(max(0, rl.n_fallback - rl.n_exception)),
            "exceptions": int(rl.n_exception) + (1 if exc else 0),
            "timeouts": 0, "ordered_blocks": int(rl.n_ordered),
            "outcome": None, "score": None, "terminal": False, "episode_length_steps": None,
            "mean_entropy": None, "start_value": None, "end_value": None,
            "duration_seconds": round(time.time() - t0, 3), "defect": exc}
    if pol.entropies:
        meta["mean_entropy"] = float(np.mean(pol.entropies))
    if rl.transitions:
        meta["start_value"] = float(rl.transitions[0]["value"])
        meta["end_value"] = float(rl.transitions[-1]["value"])

    if env is None or exc is not None:
        return {"transitions": [], "meta": meta}
    last = env.steps[-1]
    statuses = [last[0]["status"], last[1]["status"]]
    rewards = [last[0].get("reward"), last[1].get("reward")]
    meta["episode_length_steps"] = len(env.steps)
    meta["timeouts"] = int(sum(1 for s in statuses if s == "TIMEOUT"))
    if statuses != ["DONE", "DONE"]:
        meta["defect"] = f"non_terminal:{statuses}"
        return {"transitions": [], "meta": meta}
    meta["terminal"] = True
    r = rewards[seat]
    if rewards[0] == rewards[1]:
        reward, meta["outcome"], meta["score"] = 0.0, "draw", 0.5
    elif r == 1:
        reward, meta["outcome"], meta["score"] = 1.0, "win", 1.0
    else:
        reward, meta["outcome"], meta["score"] = -1.0, "loss", 0.0
    trs = rl.transitions
    for t in trs:
        t["reward"] = 0.0
        t["done"] = 0.0
    if trs:
        trs[-1]["reward"] = reward
        trs[-1]["done"] = 1.0
    return {"transitions": trs, "meta": meta}


def run_rollout(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    if nproc <= 1 or len(jobs) == 1:
        return [play_training_game(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(play_training_game, jobs, chunksize=1))


# -------------------- value diagnostics by game phase (§14) --------------------

PHASES = ["0-20", "20-40", "40-60", "60-80", "80-100"]


def value_diagnostics_by_phase(games: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Held-out value calibration/EV by game phase.

    The ``value`` stored on each transition is the prediction made AT COLLECTION TIME, i.e. by
    the parameters from before this update — so it is genuinely out-of-sample for the data it
    is scored against. Aggregate in-rollout (post-update) explained variance is reported
    separately by the PPO update and must not be read as early-game credit assignment (§14).
    """
    buckets = {p: {"v": [], "r": []} for p in PHASES}
    for g in games:
        T = len(g)
        if T == 0:
            continue
        for t, tr in enumerate(g):
            if "ret" not in tr:
                continue
            b = PHASES[min(int(5 * t / T), 4)]
            buckets[b]["v"].append(tr["value"])
            buckets[b]["r"].append(tr["ret"])
    out = {}
    for p, d in buckets.items():
        v, r = np.asarray(d["v"]), np.asarray(d["r"])
        if len(r) < 2 or r.var() < 1e-12:
            out[p] = {"n": int(len(r)), "held_out_explained_variance": None,
                      "mean_predicted": float(v.mean()) if len(v) else None,
                      "mean_actual_return": float(r.mean()) if len(r) else None,
                      "calibration_bias": None}
            continue
        ev = float(1.0 - ((r - v).var() / r.var()))
        out[p] = {"n": int(len(r)), "held_out_explained_variance": ev,
                  "mean_predicted": float(v.mean()), "mean_actual_return": float(r.mean()),
                  "calibration_bias": float(v.mean() - r.mean()),
                  "rmse": float(np.sqrt(((r - v) ** 2).mean()))}
    allv = np.asarray([x for p in PHASES for x in buckets[p]["v"]])
    allr = np.asarray([x for p in PHASES for x in buckets[p]["r"]])
    out["overall_held_out"] = ({"n": int(len(allr)),
                                "held_out_explained_variance":
                                    float(1.0 - ((allr - allv).var() / allr.var()))
                                    if len(allr) > 1 and allr.var() > 1e-12 else None}
                               if len(allr) else {"n": 0, "held_out_explained_variance": None})
    return out
