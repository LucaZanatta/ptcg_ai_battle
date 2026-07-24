"""c007 hybrid gameplay harness: run T / H0 / H1 / H2 and opponents in parallel cabt
games (spawn, fresh libcg.so + fresh agent state per game). Serializable agent specs so
workers build agents themselves; each worker loads the v2 model + hybrid config once.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from typing import Any, Dict, List, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C005_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                            "results", "artifacts", "teacher_sources")

_MODEL_CACHE: Dict[str, Any] = {}
_CFG_CACHE: Dict[str, Any] = {}


def _model(path):
    if path not in _MODEL_CACHE:
        from cg.policy_model_v2 import ModelV2
        _MODEL_CACHE[path] = ModelV2.load(path)
    return _MODEL_CACHE[path]


def _cfg(path):
    if path not in _CFG_CACHE:
        from cg.hybrid_agent import HybridConfig
        _CFG_CACHE[path] = HybridConfig.load(path)
    return _CFG_CACHE[path]


def build_agent(spec: Tuple, cfg: Dict[str, Any]):
    from cg.teachers import make_fresh as teacher_fresh
    kind = spec[0]
    if kind == "teacher":
        return teacher_fresh("dragapult", C005_SOURCES)
    if kind == "opp":
        return teacher_fresh(spec[1], C005_SOURCES)
    if kind == "control":
        from cg.control_agent import DetControl
        t = teacher_fresh("dragapult", C005_SOURCES)
        return DetControl(t.deck)
    if kind in ("H0", "H1", "H2"):
        from cg.hybrid_agent import build_hybrid
        t = teacher_fresh("dragapult", C005_SOURCES)
        model = _model(cfg["model_path"]) if kind in ("H1", "H2") else None
        hcfg = _cfg(cfg["config_path"])
        return build_hybrid(kind, t, t.deck, model=model, cfg=hcfg)
    raise ValueError(spec)


def spec_label(spec: Tuple) -> str:
    return spec[1] if spec[0] in ("opp",) else spec[0]


def _defects(agent) -> Dict[str, int]:
    tel = getattr(agent, "telemetry", [])
    inv = sum(1 for t in tel if t.get("source") == "safe_fallback")
    ov = getattr(agent, "overrides", 0)
    return {"decisions": len(tel), "overrides": ov, "safe_fallbacks": inv}


def play_one(job: Dict[str, Any]) -> Dict[str, Any]:
    from kaggle_environments import make
    from cg.safe_policy import MalformedSelection, validate_selection
    cfg = job["cfg"]
    seat_ids = job["seat_ids"]
    agents = {s: build_agent(seat_ids[s], cfg) for s in (0, 1)}
    stats = {s: {"calls": 0, "invalid": 0, "lat": []} for s in (0, 1)}

    def wrap(seat):
        ag = agents[seat]

        def w(obs):
            sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
            t0 = time.perf_counter_ns()
            res = ag(obs)
            dt = time.perf_counter_ns() - t0
            if sel is not None:
                st = stats[seat]; st["calls"] += 1; st["lat"].append(dt)
                n = len(sel.get("option", []) if isinstance(sel, dict) else sel.option)
                lo = sel.get("minCount") if isinstance(sel, dict) else sel.minCount
                mx = sel.get("maxCount") if isinstance(sel, dict) else sel.maxCount
                try:
                    validate_selection(list(res), n, lo, mx)
                except MalformedSelection:
                    st["invalid"] += 1
            return res
        return w

    exc = None; env = None
    try:
        env = make("cabt"); env.run([wrap(0), wrap(1)])
    except Exception as e:  # noqa: BLE001
        exc = repr(e)
    if exc is not None or env is None:
        statuses, rewards = ["ERROR", "ERROR"], [None, None]
    else:
        last = env.steps[-1]
        statuses = [s.status for s in last]; rewards = [s.reward for s in last]
    r0, r1 = rewards
    wseat = None if r0 == r1 else (0 if (r0 or 0) > (r1 or 0) else 1)
    out = {
        "game_id": job["game_id"], "phase": job.get("phase"),
        "seat_labels": {str(s): spec_label(seat_ids[s]) for s in (0, 1)},
        "statuses": statuses, "rewards": rewards, "winner_seat": wseat,
        "winner_label": ("draw" if wseat is None else spec_label(seat_ids[wseat])),
        "completed": statuses == ["DONE", "DONE"], "env_exception": exc,
        "invalid_by_seat": {str(s): stats[s]["invalid"] for s in (0, 1)},
        "calls_by_seat": {str(s): stats[s]["calls"] for s in (0, 1)},
        "lat_ms_by_seat": {str(s): (float(np.percentile(np.array(stats[s]["lat"]) / 1e6, 99))
                                    if stats[s]["lat"] else None) for s in (0, 1)},
        "focus_seat": job.get("focus_seat"),
        "focus_label": job.get("focus_label"),
    }
    if job.get("focus_seat") is not None:
        fs = job["focus_seat"]
        agent = agents[fs]
        out["focus_score"] = (None if wseat is None and statuses != ["DONE", "DONE"]
                              else (0.5 if wseat is None else (1.0 if wseat == fs else 0.0)))
        out["focus_defects"] = _defects(agent)
    return out


def run_batch(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    if nproc <= 1 or len(jobs) == 1:
        return [play_one(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(play_one, jobs, chunksize=1))
