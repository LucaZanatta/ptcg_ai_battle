"""c021 — scaled MCGS run: field evaluation plus graph/DAG evidence."""
from __future__ import annotations
import argparse, collections, gzip, json, multiprocessing as mp, os, sys, time
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
MC = os.path.join(C21, "mcgs")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]

def _worker(payload):
    jobs, cfg, seed = payload
    sys.path.insert(0, _REPO)
    import torch; torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    from cg import c021_mcgs_agent as AG
    deck = D19.archetype_decks()["mega_lucario"]
    out = []
    provider, arm = None, None
    if jobs and jobs[0].get("transfer_arm"):
        from cg import c021_transfer as TR
        arm = TR.arm_config(jobs[0]["transfer_arm"])
        ck = jobs[0].get("byterl_checkpoint")
        if ck and any(arm.values()):
            provider = TR.ByteRLPriorProvider(ck)
    for ji, job in enumerate(jobs):
        ag = AG.MCGSAgent(deck, cfg, seed=seed + ji,
                          prior_provider=provider, transfer_arm=arm)
        opp = T.make_fresh(job["opponent"], ce.SOURCES)
        seat = int(job["seat"])
        def mk(a):
            def f(o): return a.act(o)
            return f
        def mo(o):
            def f(x): return o(x)
            return f
        agents = [mk(ag), mo(opp)] if seat == 0 else [mo(opp), mk(ag)]
        t0 = time.time(); completed, score = False, None
        try:
            env = make("cabt"); env.run(agents)
            last = env.steps[-1]
            if [s.status for s in last] == ["DONE", "DONE"]:
                rw = [s.reward for s in last]
                if rw[seat] is not None:
                    completed = True
                    score = (1.0 if rw[seat] > rw[1-seat]
                             else (0.5 if rw[seat] == rw[1-seat] else 0.0))
        except Exception as e:
            out.append({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        out.append({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
                    "completed": completed, "score": score,
                    "seconds": round(time.time()-t0, 2), "report": ag.report(),
                    "decisions_log": ag.decisions_log[:60],
                    "graph_snapshots": ag.graph_snapshots[:4],
                    "exceptions": ag.exceptions[:2]})
    return out

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nproc", type=int, default=12)
    ap.add_argument("--first-move-seconds", type=float, default=2.0)
    ap.add_argument("--continuing-move-seconds", type=float, default=1.5)
    ap.add_argument("--max-sims", type=int, default=0)
    ap.add_argument("--seed", type=int, default=2101)
    ap.add_argument("--tag", default="scaled")
    ap.add_argument("--branch", default="MCGS_2019_OFFICIAL_SOURCE_PORT",
                    choices=["MCGS_2019_OFFICIAL_SOURCE_PORT",
                             "MCGS_2019_PTCG_LEGAL_CORRECTED"])
    ap.add_argument("--transfer-arm", default=None)
    ap.add_argument("--byterl-checkpoint", default=None)
    ap.add_argument("--no-manual-coin", action="store_true",
                    help="Ablation arm: random effects stay hidden inside the step, so NO chance "
                         "node can exist. Not the competitive configuration.")
    a = ap.parse_args(argv)
    for d in ("configs", "graph_traces", "raw_games", "evaluations", "latency", "fixtures"):
        os.makedirs(os.path.join(MC, d), exist_ok=True)
    from cg import c021_mcgs_agent as AG, c021_mcgs_graph as G
    cfg = {"first_move_seconds": a.first_move_seconds,
           "continuing_move_seconds": a.continuing_move_seconds,
           "max_simulations_per_decision": a.max_sims,
           "manual_coin": not a.no_manual_coin,
           "branch": a.branch}
    full = {**AG.REFERENCE_CFG, **cfg}
    json.dump({"config": full,
               "source_constants": {"uct": G.UCT_CONSTANT, "sample_width": G.SAMPLE_WIDTH,
                                    "damping": G.DAMPING_PARAMETER,
                                    "ucd": [full["ucd_d1"], full["ucd_d2"]],
                                    "sparse_threshold": G.CHANCE_SPARSE_THRESHOLD},
               "deployment_note": "first/continuing move seconds reduced from the source's 15/10 "
                                  "as a registered MECHANICAL_ADAPTER for the PTCG cumulative "
                                  "match clock; see benchmarks/scheduling_analysis.md"},
              open(os.path.join(MC, "configs", f"{a.tag}_config.json"), "w"), indent=2)
    jobs = [{"game_id": f"{a.tag}:g{i}", "opponent": OPPONENTS[i % 4], "seat": i % 2,
             "transfer_arm": a.transfer_arm, "byterl_checkpoint": a.byterl_checkpoint}
            for i in range(a.games)]
    chunks = [[] for _ in range(a.nproc)]
    for i, j in enumerate(jobs):
        chunks[i % a.nproc].append(j)
    payload = [(ch, cfg, a.seed + k*97) for k, ch in enumerate(chunks) if ch]
    t0 = time.time()
    with mp.get_context("spawn").Pool(len(payload)) as pool:
        res = [r for rr in pool.map(_worker, payload) for r in rr]
    agg = collections.Counter(); maxes = {}
    per = collections.defaultdict(lambda: [0, 0.0]); lat = []
    gf = gzip.open(os.path.join(MC, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    traces = []
    for r in res:
        if r.get("error"):
            agg["errors"] += 1; continue
        rep = r["report"]
        for k, v in rep.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if k in ("max_depth", "match_search_ms"):
                    maxes[k] = max(maxes.get(k, 0), v)
                elif k in ("sims_per_decision", "steps_per_decision"):
                    continue
                else:
                    agg[k] += v
        if r["completed"] and r["score"] is not None:
            per[r["opponent"]][0] += 1; per[r["opponent"]][1] += r["score"]
        gf.write(json.dumps({k: r[k] for k in ("game_id","opponent","seat","completed","score","seconds")} | {"report": rep}) + "\n")
        lat.append({"game_id": r["game_id"], "seconds": r["seconds"],
                    "match_search_ms": rep.get("match_search_ms")})
        if len(traces) < 200:
            traces.extend(r.get("graph_snapshots") or [])
    gf.close()
    json.dump(traces, open(os.path.join(MC, "graph_traces", f"{a.tag}_graphs.json"), "w"), indent=2)
    json.dump(lat, open(os.path.join(MC, "latency", f"{a.tag}_latency.json"), "w"), indent=2)
    tot_n = sum(v[0] for v in per.values()); tot_s = sum(v[1] for v in per.values())
    summary = {"tag": a.tag, "branch": "MCGS_2019_OFFICIAL_SOURCE_PORT", "config": full,
               "manual_coin": bool(full.get("manual_coin", True)),
               "manual_coin_contexts": sorted(G.MANUAL_COIN_CONTEXTS),
               "manual_coin_contexts_are_coin_head_only":
                   sorted(G.MANUAL_COIN_CONTEXTS) == [G.COIN_HEAD_CONTEXT],
               "transfer_arm": a.transfer_arm,
               "byterl_checkpoint": a.byterl_checkpoint,
               "chance_nodes_possible": bool(full.get("manual_coin", True)),
               "games": len(res), "completed": sum(1 for r in res if r.get("completed")),
               **{k: int(v) for k, v in agg.items()},
               **{f"max_{k}": v for k, v in maxes.items()},
               "sims_per_decision": round(agg["searches"]/max(1, agg["searched_decisions"]), 1),
               "steps_per_decision": round(agg["step_calls"]/max(1, agg["searched_decisions"]), 1),
               "rollout_terminal_rate": round(agg.get("rollout_terminals",0)/max(1,agg["rollouts"]), 4),
               "per_opponent": {k: {"games": v[0], "rate": round(v[1]/v[0],4) if v[0] else None}
                                for k, v in per.items()},
               "field_score": round(tot_s/tot_n, 4) if tot_n else None,
               "wall_clock_s": round(time.time()-t0, 1)}
    json.dump(summary, open(os.path.join(MC, "evaluations", f"{a.tag}_summary.json"), "w"), indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "config"}, indent=2)[:2200])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
