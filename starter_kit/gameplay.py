"""Parallel cabt game execution for c006 gameplay evaluation.

Agents are described by serializable specs so games run across processes (spawn,
so each worker loads libcg.so fresh). Fresh agent instances per game (student GRU
hidden + teacher module state reset). Each game returns a schema-v2-style
game_terminal record with reliability, latency, and fallback per seat.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_agent(spec: Tuple, cfg: Dict[str, Any]):
    kind = spec[0]
    if kind == "teacher":
        from cg.teachers import make_fresh
        return make_fresh(spec[1], cfg["sources"])
    if kind == "student":
        from cg.student_agent import make_student
        return make_student(spec[1], cfg["deck"])
    if kind == "control":
        from cg.control_agent import DetControl
        return DetControl(cfg["deck"])
    raise ValueError(f"unknown agent spec {spec!r}")


def spec_label(spec: Tuple) -> str:
    if spec[0] == "student":
        return spec[2] if len(spec) > 2 else "student"
    if spec[0] == "teacher":
        return spec[1]
    return "control"


def _lat_summary(ns: List[int]) -> Dict[str, float]:
    if not ns:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None, "mean_ms": None}
    a = np.array(ns) / 1e6
    return {"count": int(a.size), "p50_ms": float(np.percentile(a, 50)),
            "p95_ms": float(np.percentile(a, 95)), "p99_ms": float(np.percentile(a, 99)),
            "max_ms": float(a.max()), "mean_ms": float(a.mean())}


def play_one(job: Dict[str, Any]) -> Dict[str, Any]:
    from kaggle_environments import make
    from cg.safe_policy import MalformedSelection, validate_selection
    cfg = job["cfg"]
    seat_ids = job["seat_ids"]           # {0: spec, 1: spec}
    agents = {s: build_agent(seat_ids[s], cfg) for s in (0, 1)}
    stats = {s: {"calls": 0, "lat": [], "invalid": 0, "fallback": 0, "forced": 0} for s in (0, 1)}

    def wrap(seat):
        ag = agents[seat]

        def w(obs):
            sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
            t0 = time.perf_counter_ns()
            res = ag(obs)
            dt = time.perf_counter_ns() - t0
            if sel is None:
                return res
            st = stats[seat]
            st["calls"] += 1
            st["lat"].append(dt)
            n = len(sel.get("option", []) if isinstance(sel, dict) else sel.option)
            lo = sel.get("minCount") if isinstance(sel, dict) else sel.minCount
            mx = sel.get("maxCount") if isinstance(sel, dict) else sel.maxCount
            try:
                validate_selection(list(res), n, lo, mx)
            except MalformedSelection:
                st["invalid"] += 1
            prov = ag.classify_decision(obs, res) if hasattr(ag, "classify_decision") else {}
            if prov.get("used_fallback"):
                st["fallback"] += 1
            if prov.get("decision_source") == "forced_bypass":
                st["forced"] += 1
            return res
        return w

    exc = None
    env = None
    try:
        env = make("cabt")
        env.run([wrap(0), wrap(1)])
    except Exception as e:  # pragma: no cover
        exc = repr(e)
    if exc is not None or env is None:
        statuses, rewards = ["ERROR", "ERROR"], [None, None]
    else:
        last = env.steps[-1]
        statuses = [s.status for s in last]
        rewards = [s.reward for s in last]
    r0, r1 = rewards
    wseat = None if r0 == r1 else (0 if (r0 or 0) > (r1 or 0) else 1)
    rel = {str(s): {"label": spec_label(seat_ids[s]), "invalid_selections": stats[s]["invalid"],
                    "agent_error": bool(statuses[s] in ("ERROR", "INVALID")),
                    "timeout": bool(statuses[s] == "TIMEOUT")} for s in (0, 1)}
    return {
        "schema_version": 2, "record_type": "game_terminal", "game_id": job["game_id"],
        "phase": job.get("phase"), "pair_id": job.get("pair_id"),
        "seat_labels": {str(s): spec_label(seat_ids[s]) for s in (0, 1)},
        "statuses": statuses, "rewards": rewards, "winner_seat": wseat,
        "winner_label": ("draw" if wseat is None else spec_label(seat_ids[wseat])),
        "completed": statuses == ["DONE", "DONE"], "env_exception": exc,
        "reliability": rel,
        "decisions_by_seat": {str(s): stats[s]["calls"] for s in (0, 1)},
        "forced_by_seat": {str(s): stats[s]["forced"] for s in (0, 1)},
        "fallback_by_seat": {str(s): stats[s]["fallback"] for s in (0, 1)},
        "latency_by_seat": {str(s): _lat_summary(stats[s]["lat"]) for s in (0, 1)},
        "game_length_steps": (len(env.steps) if env is not None else None),
    }


def run_batch(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    if nproc <= 1 or len(jobs) == 1:
        return [play_one(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(play_one, jobs, chunksize=1))
