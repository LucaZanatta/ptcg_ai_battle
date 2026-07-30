"""c022 — run one MCGS arm against the frozen four-archetype panel.

One arm = one (K, protocol, simulations) triple. Games run in separate processes so a stalled
game cannot take the arm with it, and results are drained as they arrive.

Two things c021 got wrong here and this runner does not:

**The queue is drained while children are alive.** c021's parent read child results only after
`join()`, so children blocking on a full pipe were recorded as abandoned. Twelve games that
"abandoned" at 154 s completed in 45 s once the drain was fixed. This runner drains continuously.

**Latency is not the budget.** Arms are budgeted by simulation count, so worker contention makes
a run slower but never weaker. c021's own M16 measurement found `sims_per_decision` collapsing to
8% of its single-worker value at 24 workers with nothing in the field score to reveal it. That
failure mode cannot occur here — but `sims_per_decision` is still reported per arm, because a
budget that is not being delivered must be visible.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _one_game(job: Dict[str, Any], cfg: Dict[str, Any], seed: int, q):
    """Play ONE game in its own process."""
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)          # mandatory: one BLAS thread per worker
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    from cg import c022_mcgs_agent as AG

    deck = D19.archetype_decks()["mega_lucario"]
    provider, arm = None, None
    if job.get("transfer_arm"):
        from cg import c021_transfer as TR
        arm = TR.arm_config(job["transfer_arm"])
        ck = job.get("byterl_checkpoint")
        if ck and any(arm.values()):
            provider = TR.ByteRLPriorProvider(ck)
    # Each game gets its own world base seed, so two games never search identical worlds; paired
    # arms reuse the SAME seed for the same game_id, which is what makes them paired.
    gcfg = dict(cfg)
    gcfg["world_base_seed"] = int(job["world_base_seed"])
    ag = AG.MultiDetMCGSAgent(deck, gcfg, seed=seed, prior_provider=provider, transfer_arm=arm)

    opp = T.make_fresh(job["opponent"], ce.SOURCES)
    seat = int(job["seat"])

    def mk(a):
        def f(o):
            return a.act(o)
        return f

    def mo(o):
        def f(x):
            return o(x)
        return f

    agents = [mk(ag), mo(opp)] if seat == 0 else [mo(opp), mk(ag)]
    t0 = time.time()
    completed, score = False, None
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        if [s.status for s in last] == ["DONE", "DONE"]:
            rw = [s.reward for s in last]
            if rw[seat] is not None:
                completed = True
                score = (1.0 if rw[seat] > rw[1 - seat]
                         else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        q.put({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200]})
        return

    # Staple the realised outcome onto every calibration row. A predicted probability with no
    # realised outcome cannot be calibrated against anything.
    cal = ag.calibration
    for row in cal:
        row["realised"] = score
        row["game_id"] = job["game_id"]
        row["opponent"] = job["opponent"]
    q.put({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
           "completed": completed, "score": score,
           "seconds": round(time.time() - t0, 2),
           "report": ag.report(),
           "calibration": cal,
           "traces": ag.traces[:2],
           "exceptions": ag.exceptions[:2]})


def run_arm(a) -> Dict[str, Any]:
    cfg = {
        "branch": a.branch,
        "k_worlds": a.k,
        "budget_protocol": a.protocol,
        "simulations_per_decision": a.sims,
        "aggregation_rule": a.aggregation,
        "graph_reuse": bool(a.graph_reuse),
        "match_clock_seconds": float(a.match_clock),
        "decision_seconds_cap": float(a.decision_cap),
        "decision_wall_ceiling_seconds": float(a.wall_ceiling),
    }
    jobs = [{"game_id": f"{a.tag}:g{i}",
             "opponent": OPPONENTS[i % len(OPPONENTS)],
             "seat": i % 2,
             # Paired across arms: game i always gets world base seed derived from i alone, so
             # arm A and arm B searching game i search the SAME hidden worlds.
             "world_base_seed": a.seed * 1000003 + i,
             "transfer_arm": a.transfer_arm,
             "byterl_checkpoint": a.byterl_checkpoint}
            for i in range(a.games)]

    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    results: List[Dict[str, Any]] = []
    running: Dict[str, Any] = {}
    pending = list(jobs)
    t0 = time.time()
    deadline = t0 + a.arm_timeout

    while (pending or running) and time.time() < deadline:
        while pending and len(running) < a.nproc:
            job = pending.pop(0)
            p = ctx.Process(target=_one_game,
                            args=(job, cfg, a.seed + len(results) + len(running), q))
            p.start()
            running[job["game_id"]] = (p, job, time.time())
        # Drain CONTINUOUSLY. Reading only after join() is what made c021 record live children
        # as abandoned.
        drained = 0
        while True:
            try:
                results.append(q.get(timeout=0.25))
                drained += 1
            except Exception:  # noqa: BLE001
                break
        for gid, (p, job, started) in list(running.items()):
            if not p.is_alive():
                p.join(timeout=1)
                del running[gid]
            elif time.time() - started > a.game_timeout:
                p.terminate()
                p.join(timeout=5)
                del running[gid]
                results.append({"game_id": gid, "opponent": job["opponent"],
                                "completed": False, "score": None,
                                "abandoned": True,
                                "seconds": round(time.time() - started, 1)})
    for gid, (p, job, started) in list(running.items()):
        p.terminate()
        p.join(timeout=5)
        results.append({"game_id": gid, "opponent": job.get("opponent"),
                        "completed": False, "score": None, "abandoned": True,
                        "arm_timeout": True})
    while True:
        try:
            results.append(q.get(timeout=0.5))
        except Exception:  # noqa: BLE001
            break

    # ---------------------------------------------------------------- aggregate
    os.makedirs(a.out, exist_ok=True)
    scored = [r for r in results if r.get("completed") and r.get("score") is not None]
    abandoned = [r for r in results if r.get("abandoned")]
    errored = [r for r in results if r.get("error")]
    wins = sum(r["score"] for r in scored)
    n = len(scored)

    agg_stats: Dict[str, Any] = collections.defaultdict(float)
    for r in results:
        for k, v in (r.get("report") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                agg_stats[k] += v

    per_opp = collections.defaultdict(lambda: [0, 0.0])
    for r in scored:
        per_opp[r["opponent"]][0] += 1
        per_opp[r["opponent"]][1] += r["score"]

    cal_rows = [row for r in results for row in (r.get("calibration") or [])]
    with open(os.path.join(a.out, f"{a.tag}_calibration.jsonl"), "w") as fh:
        for row in cal_rows:
            fh.write(json.dumps(row) + "\n")
    with open(os.path.join(a.out, f"{a.tag}_games.jsonl"), "w") as fh:
        for r in results:
            fh.write(json.dumps({k: r.get(k) for k in
                                 ("game_id", "opponent", "seat", "completed", "score",
                                  "seconds", "abandoned", "error")}) + "\n")
    with open(os.path.join(a.out, f"{a.tag}_traces.jsonl"), "w") as fh:
        for r in results:
            for t in (r.get("traces") or []):
                fh.write(json.dumps({"game_id": r.get("game_id"), **t}) + "\n")

    sd = max(1.0, agg_stats.get("searched_decisions", 0.0))
    summary = {
        "tag": a.tag, "branch": a.branch, "config": cfg,
        "seed": a.seed, "nproc": a.nproc,
        "games": a.games, "completed": n,
        "abandoned": len(abandoned), "errored": len(errored),
        "abandoned_note": "games exceeding the per-game wall clock; EXCLUDED from the field "
                          "score rather than scored as losses",
        "field_score": round(wins / n, 4) if n else None,
        "wilson95": wilson(round(wins), n) if n else [None, None],
        "field_score_bounds_if_abandoned_counted": [
            round(wins / (n + len(abandoned)), 4) if (n + len(abandoned)) else None,
            round((wins + len(abandoned)) / (n + len(abandoned)), 4)
            if (n + len(abandoned)) else None],
        "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4)}
                         for k, v in sorted(per_opp.items()) if v[0]},
        "wall_clock_s": round(time.time() - t0, 1),
        "searched_decisions": int(agg_stats.get("searched_decisions", 0)),
        "total_simulations": int(agg_stats.get("searches", 0)),
        "sims_per_decision": round(agg_stats.get("searches", 0.0) / sd, 1),
        "mean_k_used": round(agg_stats.get("k_used_total", 0.0) / sd, 3),
        "world_errors": int(agg_stats.get("world_errors", 0)),
        "decision_deadline_stops": int(agg_stats.get("decision_deadline_stops", 0)),
        "match_clock_exhausted_decisions": int(
            agg_stats.get("match_clock_exhausted_decisions", 0)),
        "signature_mismatches": int(agg_stats.get("signature_mismatches", 0)),
        "mixed_terminal_scale_decisions": int(
            agg_stats.get("mixed_terminal_scale_decisions", 0)),
        "aggregate_empty_decisions": int(agg_stats.get("aggregate_empty_decisions", 0)),
        "term_root_win": int(agg_stats.get("term_root_win", 0)),
        "term_root_loss": int(agg_stats.get("term_root_loss", 0)),
        "term_undecided": int(agg_stats.get("term_undecided", 0)),
        "finalised": int(agg_stats.get("finalised", 0)),
        "terminal_leaves": int(agg_stats.get("terminal_leaves", 0)),
        "lethal_bonus": int(agg_stats.get("lethal_bonus", 0)),
        "step_errors": int(agg_stats.get("step_errors", 0)),
        "begin_errors": int(agg_stats.get("begin_errors", 0)),
        "transposition_merges": int(agg_stats.get("transposition_merges", 0)),
        "dummy_edges": int(agg_stats.get("dummy_edges", 0)),
        "chance_nodes_created": int(agg_stats.get("chance_nodes_created", 0)),
        "manual_coin_node_ucb_selected": int(
            agg_stats.get("manual_coin_node_ucb_selected", 0)),
        "calibration_rows": len(cal_rows),
        "budget_delivered": bool(agg_stats.get("decision_deadline_stops", 0) == 0),
    }
    with open(os.path.join(a.out, f"{a.tag}_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--branch", default="MCGS_2019_PTCG_MULTI_DET_REFERENCE")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--protocol", default="fixed_total",
                    choices=["fixed_total", "fixed_per_world"])
    ap.add_argument("--sims", type=int, default=512)
    ap.add_argument("--aggregation", default="source_sum",
                    choices=["source_sum", "visit_sum", "robust_lcb"])
    ap.add_argument("--graph-reuse", type=int, default=0)
    ap.add_argument("--match-clock", type=float, default=0.0)
    ap.add_argument("--decision-cap", type=float, default=0.0)
    ap.add_argument("--wall-ceiling", type=float, default=120.0)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nproc", type=int, default=12)
    ap.add_argument("--seed", type=int, default=90210)
    ap.add_argument("--game-timeout", type=float, default=900.0)
    ap.add_argument("--arm-timeout", type=float, default=14400.0)
    ap.add_argument("--transfer-arm", default=None)
    ap.add_argument("--byterl-checkpoint", default=None)
    ap.add_argument("--out", default=os.path.join(MC, "k_sweeps"))
    a = ap.parse_args(argv)

    s = run_arm(a)
    print(json.dumps({k: s[k] for k in
                      ("tag", "games", "completed", "abandoned", "field_score", "wilson95",
                       "sims_per_decision", "mean_k_used", "total_simulations",
                       "budget_delivered", "match_clock_exhausted_decisions",
                       "signature_mismatches", "mixed_terminal_scale_decisions",
                       "world_errors", "wall_clock_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
