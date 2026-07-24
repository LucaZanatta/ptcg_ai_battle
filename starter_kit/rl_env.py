"""c008 RL environment adapter over cabt.

Plays one cabt game with the RL policy on one seat against a fixed opponent, collecting a
transition per NON-FORCED selection (§9.1): forced choices bypass the network, produce no
policy loss, and remain only in history. The episode terminal reward (win +1 / draw 0 /
loss -1, §9.6) is assigned to every trainable transition; GAE is computed later. Runs in
spawn workers (fresh libcg.so + fresh policy loaded from a checkpoint per rollout).
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from cg import decoders
from cg import state_encoder_v2 as enc
from cg.episode_capture import context_name, normalize_observation
from cg.safe_policy import MalformedSelection, validate_selection

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C005_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                            "results", "artifacts", "teacher_sources")

_POLICY_CACHE: Dict[str, Any] = {}


def _forced(n, lo, hi):
    return n <= 1 or hi == 0 or (lo == hi == n and n >= 1)


class RLAgent:
    """Runtime RL agent: samples non-forced decisions, records transitions, safe-falls-back
    on forced/exception/ordered. Deterministic (greedy) mode for evaluation."""

    def __init__(self, policy, deck, rng, collect=True, greedy=False):
        self.policy = policy
        self.deck = deck
        self.rng = rng
        self.collect = collect
        self.greedy = greedy
        self.transitions: List[Dict[str, Any]] = []
        self.agent_id = "rl"
        self._reset()

    def _reset(self):
        self.prev_state = enc.initial_prev_state()
        self.n_decisions = 0
        self.n_forced = 0
        self.n_fallback = 0
        self.n_exception = 0
        self.n_ordered = 0
        self._last = {}

    def classify_decision(self, obs, result):
        return self._last or {"decision_source": "rl", "used_fallback": False, "fallback_reason": None}

    def __call__(self, obs):
        sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
        if sel is None:
            self._reset()
            return list(self.deck)
        norm = normalize_observation(obs)[0]
        n = len(sel.get("option", []))
        lo = sel.get("minCount") or 0
        hi = sel.get("maxCount") or 0
        ctxname = context_name(sel.get("context"))
        form = decoders.classify_form(ctxname, lo, hi, n)
        self.n_decisions += 1
        action = None
        source = "rl"
        if form == "ORDERED":
            self.n_ordered += 1  # §9.5: must BLOCK; here we flag + safe fallback for reliability
            action = decoders.safe_fallback(lo, hi, n)
            source = "ordered_block"
        elif _forced(n, lo, hi):
            self.n_forced += 1
            action = decoders.safe_fallback(lo, hi, n)
            source = "forced_bypass"
        else:
            try:
                feat = enc.encode(norm, self.prev_state)
                r = self.policy.act(feat, form, lo, hi, self.rng, greedy=self.greedy)
                action = list(r["action"])
                validate_selection(action, n, lo, hi)   # legality guard
                if self.collect:
                    self.transitions.append({
                        "feat": feat, "form": form, "lo": lo, "hi": hi, "n_options": n,
                        "action_seq": r["action_seq"], "logprob": r["logprob"],
                        "value": r["value"], "context": ctxname,
                    })
            except (MalformedSelection, Exception) as e:  # noqa: BLE001
                self.n_exception += 1 if not isinstance(e, MalformedSelection) else 0
                self.n_fallback += 1
                action = decoders.safe_fallback(lo, hi, n)
                source = "safe_fallback"
        self._last = {"decision_source": source, "used_fallback": source in ("safe_fallback", "forced_bypass"),
                      "fallback_reason": None if source == "rl" else source}
        self.prev_state = enc.derive_prev_state(norm, action)
        return action


def _build_opponent(spec, deck, sources):
    from cg.teachers import make_fresh as teacher_fresh
    kind = spec[0]
    if kind == "teacher":
        return teacher_fresh(spec[1], sources)
    if kind == "control":
        from cg.control_agent import DetControl
        return DetControl(deck)
    if kind == "lagged":
        from cg.rl_policy import RLPolicy
        pol = _POLICY_CACHE.get(spec[1]) or RLPolicy.load(spec[1])
        _POLICY_CACHE[spec[1]] = pol
        return RLAgent(pol, deck, np.random.default_rng(spec[2]), collect=False, greedy=False)
    raise ValueError(spec)


def play_game(job: Dict[str, Any]) -> Dict[str, Any]:
    from kaggle_environments import make
    from cg.rl_policy import RLPolicy
    ckpt = job["policy_ckpt"]
    pol = _POLICY_CACHE.get(ckpt)
    if pol is None:
        pol = RLPolicy.load(ckpt); _POLICY_CACHE[ckpt] = pol
    seat = job["seat"]
    rng = np.random.default_rng(job["rng_seed"])
    rl = RLAgent(pol, job["deck"], rng, collect=job.get("collect", True), greedy=job.get("greedy", False))
    opp = _build_opponent(job["opponent"], job["deck"], C005_SOURCES)
    players = [rl, opp] if seat == 0 else [opp, rl]
    exc = None; env = None
    try:
        env = make("cabt"); env.run([lambda o: players[0](o), lambda o: players[1](o)])
    except Exception as e:  # noqa: BLE001
        exc = repr(e)
    if env is None:
        return {"transitions": [], "reward": None, "completed": False, "exc": exc,
                "seat": seat, "opponent": job["opponent"][0] if job["opponent"][0] != "teacher"
                else job["opponent"][1], "defects": {"exception": 1}}
    last = env.steps[-1]
    st = [last[0]["status"], last[1]["status"]]
    rw = [last[0].get("reward"), last[1].get("reward")]
    completed = st == ["DONE", "DONE"]
    reward = None
    if completed:
        r = rw[seat]
        reward = 0.0 if rw[0] == rw[1] else (1.0 if r == 1 else -1.0)
    # assign terminal reward to every trainable transition; last one is terminal
    trs = rl.transitions if completed else []
    for k, t in enumerate(trs):
        t["reward"] = 0.0
        t["done"] = 0.0
    if trs:
        trs[-1]["reward"] = reward if reward is not None else 0.0
        trs[-1]["done"] = 1.0
    opp_label = job["opponent"][1] if job["opponent"][0] == "teacher" else job["opponent"][0]
    return {"transitions": trs, "reward": reward, "completed": completed, "exc": exc,
            "seat": seat, "opponent": opp_label,
            "score": (0.5 if reward == 0.0 else (1.0 if reward == 1.0 else 0.0)) if completed else None,
            "n_decisions": rl.n_decisions, "n_forced": rl.n_forced, "n_fallback": rl.n_fallback,
            "n_exception": rl.n_exception, "n_ordered": rl.n_ordered,
            "invalid": 0, "steps": len(env.steps)}


def run_rollout(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    if nproc <= 1 or len(jobs) == 1:
        return [play_game(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(play_game, jobs, chunksize=1))
