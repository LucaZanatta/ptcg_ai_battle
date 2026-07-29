"""c021 — scaled MCGS run: field evaluation plus graph/DAG evidence."""
from __future__ import annotations
import argparse, collections, gzip, json, multiprocessing as mp, os, sys, time
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
MC = os.path.join(C21, "mcgs")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]

def _one_game(job, cfg, seed, q):
    """Play ONE game in its own process, so a stalemate cannot stall a whole arm."""
    sys.path.insert(0, _REPO)
    import torch; torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    from cg import c021_mcgs_agent as AG
    deck = D19.archetype_decks()["mega_lucario"]
    provider, arm = None, None
    if job.get("transfer_arm"):
        from cg import c021_transfer as TR
        arm = TR.arm_config(job["transfer_arm"])
        ck = job.get("byterl_checkpoint")
        if ck and any(arm.values()):
            provider = TR.ByteRLPriorProvider(ck)
    ag = AG.MCGSAgent(deck, cfg, seed=seed, prior_provider=provider, transfer_arm=arm)
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
    except Exception as e:  # noqa: BLE001
        q.put({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200]})
        return
    q.put({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
           "completed": completed, "score": score,
           "seconds": round(time.time()-t0, 2), "report": ag.report(),
           "decisions_log": ag.decisions_log[:6],
           "graph_snapshots": ag.graph_snapshots[:1],
           "exceptions": ag.exceptions[:1]})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nproc", type=int, default=12)
    ap.add_argument("--first-move-seconds", type=float, default=2.0)
    ap.add_argument("--continuing-move-seconds", type=float, default=1.5)
    ap.add_argument("--max-sims", type=int, default=0)
    ap.add_argument("--match-clock-seconds", type=float, default=90.0)
    ap.add_argument("--game-timeout-seconds", type=float, default=300.0)
    ap.add_argument("--role", default=None,
                    choices=["competitive", "diagnostic", "ablation", "transfer"],
                    help="What this run is FOR. Diagnostic and ablation runs must never be "
                         "eligible as a competitive candidate; inferred from the tag if omitted.")
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
           "match_clock_seconds": a.match_clock_seconds,
           "game_timeout_seconds": a.game_timeout_seconds,
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
    t0 = time.time()
    # One PROCESS PER GAME with a hard join timeout, at most `nproc` at a time. A chunked Pool
    # cannot do this: pool workers are daemonic and may not spawn children, so a game that
    # stalls inside `env.run` is uninterruptible and blocks the whole arm. A stalemate grinding
    # toward deck-out was measured pinning a worker for 21 minutes while every other game
    # finished in about two.
    ctx = mp.get_context("spawn")
    cap = float(cfg.get("game_timeout_seconds") or 300.0)
    res, running = [], []          # running: (proc, queue, job, started)

    def _reap(block: bool):
        for item in list(running):
            pr, q, job, started = item
            # DRAIN FIRST, regardless of liveness. A child that has finished and called q.put()
            # with a large payload blocks on the pipe buffer (~64 KB on Linux) until the parent
            # reads it -- so it stays `is_alive()`, trips the deadline, and gets recorded as
            # abandoned even though it completed. Gating the read on `not is_alive()` therefore
            # manufactures fake timeouts, and it does so more often for arms whose payloads are
            # larger, which is exactly the kind of differential bias that corrupts a comparison.
            try:
                r = q.get_nowait()
                res.append(r)
                pr.join(10)
                if pr.is_alive():
                    pr.terminate(); pr.join(5)
                running.remove(item)
                continue
            except Exception:  # noqa: BLE001
                pass
            alive = pr.is_alive()
            over = (time.time() - started) > cap
            if alive and not over and not block:
                continue
            if alive and over:
                # COUNTED and EXCLUDED from the field score -- never scored as a loss, which
                # would bias the result toward whichever arm stalls least.
                pr.terminate(); pr.join(5)
                if pr.is_alive():
                    pr.kill(); pr.join(5)
                res.append({"game_id": job["game_id"], "opponent": job["opponent"],
                            "abandoned": True, "reason": f"exceeded {cap:.0f}s wall clock"})
                running.remove(item)
                continue
            if alive:
                continue
            pr.join(1)
            try:
                res.append(q.get_nowait())
            except Exception:  # noqa: BLE001
                res.append({"game_id": job["game_id"], "error": "no result returned"})
            running.remove(item)

    for ji, job in enumerate(jobs):
        while len(running) >= a.nproc:
            _reap(False)
            if len(running) >= a.nproc:
                time.sleep(0.5)
        q = ctx.Queue()
        pr = ctx.Process(target=_one_game, args=(job, cfg, a.seed + ji * 97, q))
        pr.start()
        running.append((pr, q, job, time.time()))
    while running:
        _reap(False)
        if running:
            time.sleep(0.5)
    agg = collections.Counter(); maxes = {}
    per = collections.defaultdict(lambda: [0, 0.0]); lat = []
    gf = gzip.open(os.path.join(MC, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    traces = []
    for r in res:
        if r.get("abandoned"):
            agg["abandoned"] += 1; continue
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
    # Per-decision root edge statistics: the richest diagnostic the agent produces, and it was
    # collected by the worker and then dropped. Without it there is no way to ask whether the
    # search's chosen action is separated from its alternatives or is being picked out of noise.
    dl = [d for r in res for d in (r.get("decisions_log") or [])]
    json.dump(dl, open(os.path.join(MC, "graph_traces", f"{a.tag}_decisions.json"), "w"), indent=2)
    json.dump(lat, open(os.path.join(MC, "latency", f"{a.tag}_latency.json"), "w"), indent=2)
    tot_n = sum(v[0] for v in per.values()); tot_s = sum(v[1] for v in per.values())
    summary = {"tag": a.tag, "branch": "MCGS_2019_OFFICIAL_SOURCE_PORT", "config": full,
               "manual_coin": bool(full.get("manual_coin", True)),
               "drain_fixed": True,
               # What this run is FOR. Throughput probes and ablations write into the same
               # evaluations directory as real arms, and a blocklist let `scale_w2` -- a
               # 11-game worker-scaling probe -- become the best-scoring eligible candidate for
               # the headline MCGS result. Role is explicit and the report ALLOW-lists it.
               "role": (a.role or ("transfer" if a.transfer_arm else
                                   "diagnostic" if a.tag.startswith(("scale_", "smoke", "a4_",
                                                                     "boundtest", "clocktest",
                                                                     "drainfix", "livelock"))
                                   else "ablation" if a.tag.startswith("ablation")
                                   else "competitive")),
               "manual_coin_contexts": sorted(G.MANUAL_COIN_CONTEXTS),
               "manual_coin_contexts_are_coin_head_only":
                   sorted(G.MANUAL_COIN_CONTEXTS) == [G.COIN_HEAD_CONTEXT],
               "transfer_arm": a.transfer_arm,
               "byterl_checkpoint": a.byterl_checkpoint,
               "chance_nodes_possible": bool(full.get("manual_coin", True)),
               "games": len(res), "completed": sum(1 for r in res if r.get("completed")),
               "abandoned": int(agg.get("abandoned", 0)),
               "abandoned_note": ("games exceeding the per-game wall clock; EXCLUDED from the "
                                  "field score rather than scored as losses"),
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
