"""c021 Phase 1 — environment and hardware characterization.

`CONTRACT §5` measures WITHOUT changing algorithms, and the numbers choose scheduling only. They
matter here for one specific reason: the official MCGS config allocates 15s for a first move and
10s for continuing moves, and whether that is affordable in PTCG depends entirely on how expensive
`search_step` is across the FFI boundary. c020 measured 891 `search_step` calls per decision at
~700ms, which is the only prior datapoint.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics as st
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")


def _bench_worker(payload):
    """One worker: measure raw native search primitives on real positions."""
    n_decisions, seed = payload
    sys.path.insert(0, _REPO)
    import numpy as np
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import api as A, c019_core as K, c019_determinize as D19
    from cg import c020_determinize as DT, c020_baseline_memory as BM
    from cg import teachers as T, c009_eval as ce

    deck = D19.archetype_decks()["mega_lucario"]
    rng = np.random.default_rng(seed)
    m = {"begin": [], "step": [], "release": [], "hash": [], "options": [],
         "decisions": 0, "step_errors": 0}
    state = {"mem": BM.initial_memory(), "n": 0}

    def make_me(s):
        def me(obs):
            act, _ = BM.recommend(obs, s["mem"])
            s["mem"] = BM.advance_after_executed(obs, act, s["mem"])
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is not None and s["n"] < n_decisions:
                s["n"] += 1
                try:
                    o = A.to_observation_class(obs)
                    v = K.visible_view(o)
                    t0 = time.perf_counter()
                    K.observation_hash(o)
                    m["hash"].append(time.perf_counter() - t0)
                    t0 = time.perf_counter()
                    opts = K.canonical_options(getattr(o, "select", None))
                    m["options"].append(time.perf_counter() - t0)
                    det, _draw = DT.determinize(v, deck, rng)
                    t0 = time.perf_counter()
                    ss = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck,
                                        det.opponent_prize, det.opponent_hand,
                                        det.opponent_active)
                    m["begin"].append(time.perf_counter() - t0)
                    cur = ss
                    for _ in range(24):
                        ob = getattr(cur, "observation", None)
                        se = getattr(ob, "select", None) if ob is not None else None
                        if se is None:
                            break
                        oo = K.canonical_options(se)
                        if not oo:
                            break
                        lo = max(1, int(getattr(se, "minCount", 1) or 1))
                        pay = [x.option_index for x in oo[:lo]]
                        t0 = time.perf_counter()
                        try:
                            cur = A.search_step(cur.searchId, pay)
                            m["step"].append(time.perf_counter() - t0)
                        except Exception:
                            m["step_errors"] += 1
                            break
                    t0 = time.perf_counter()
                    A.search_release(ss.searchId)
                    m["release"].append(time.perf_counter() - t0)
                    A.search_end()
                    m["decisions"] += 1
                except Exception:
                    pass
            return list(act)
        return me

    def mo(o):
        def f(x):
            return o(x)
        return f

    try:
        env = make("cabt")
        env.run([make_me(state), mo(T.make_fresh("mega_lucario", ce.SOURCES))])
    except Exception:
        pass
    return {k: (v if isinstance(v, int) else
                {"n": len(v), "mean_us": round(1e6 * st.mean(v), 1) if v else None,
                 "p50_us": round(1e6 * st.median(v), 1) if v else None,
                 "p95_us": round(1e6 * sorted(v)[int(0.95 * (len(v) - 1))], 1) if v else None})
            for k, v in m.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", type=int, default=12)
    ap.add_argument("--scales", default="1,2,4,8,12")
    a = ap.parse_args(argv)

    os.makedirs(os.path.join(C21, "benchmarks"), exist_ok=True)
    out: Dict[str, Any] = {"note": "scheduling input only; no algorithm depends on these",
                           "cpu_logical": os.cpu_count(), "scales": {}}

    # single-worker primitive costs
    t0 = time.time()
    prim = _bench_worker((a.decisions, 7))
    out["primitive_costs_single_worker"] = prim
    out["primitive_wall_s"] = round(time.time() - t0, 1)

    # process scaling
    for k in [int(x) for x in a.scales.split(",") if x]:
        t0 = time.time()
        with mp.get_context("spawn").Pool(k) as pool:
            res = pool.map(_bench_worker, [(a.decisions, 100 + i) for i in range(k)])
        wall = time.time() - t0
        steps = sum(r["step"]["n"] for r in res if r["step"]["n"])
        decs = sum(r["decisions"] for r in res)
        out["scales"][str(k)] = {
            "workers": k, "wall_s": round(wall, 1),
            "total_search_steps": steps, "total_decisions": decs,
            "steps_per_sec": round(steps / wall, 1) if wall else None,
            "steps_per_sec_per_worker": round(steps / wall / k, 1) if wall else None,
            "scaling_efficiency_vs_1w": None}
        print(f"  workers={k:2d} wall={wall:6.1f}s steps={steps:6d} "
              f"steps/s={steps/wall:8.1f}", flush=True)

    base = out["scales"].get("1", {}).get("steps_per_sec")
    if base:
        for k, v in out["scales"].items():
            if v["steps_per_sec"]:
                v["scaling_efficiency_vs_1w"] = round(
                    v["steps_per_sec"] / (base * int(k)), 3)

    # what the official MCGS time budget implies here
    sp = prim["step"]["mean_us"]
    if sp:
        out["official_budget_feasibility"] = {
            "source_first_move_seconds": 15, "source_continuing_move_seconds": 10,
            "measured_search_step_mean_us": sp,
            "steps_affordable_in_10s_single_worker": int(10e6 / sp),
            "c020_reference_steps_per_decision": 891,
            "comment": "the source's 10s budget buys this many native steps on one worker; "
                       "MCGS simulations cost several steps each, so the achievable simulation "
                       "count per decision follows from this number and the graph's branching"}
    json.dump(out, open(os.path.join(C21, "benchmarks", "environment_throughput.json"), "w"),
              indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "scales"}, indent=2)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
