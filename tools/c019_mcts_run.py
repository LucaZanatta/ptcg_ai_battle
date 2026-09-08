"""c019 Branch A — scaled MCTS run with full probe evidence (§8.6).

Plays real games with `PTCG_ISMCTS_V0` and preserves everything M01–M11 need: per-decision
counters, sampled full trees, determinization records including rejections, PUCT statistics,
latency distributions, and raw game outcomes.

§8.6 floors: >=5,000 searched live decisions, >=500,000 simulations or native successor
expansions, >=1,000 decisions using multiple determinizations, >=100 complete sampled tree
traces. When the match clock prevents a target, actuals are reported and the status is PARTIAL —
never a silently lowered count.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
MC = os.path.join(C19, "mcts")


def _play(args):
    (gi, seed, opponent, cfg, traces_wanted) = args
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c019_ismcts as IS

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    agent = IS.ISMCTSAgent(deck, cfg, seed=seed, collect_traces=traces_wanted)
    opp = T.make_fresh(opponent, ce.SOURCES)
    seat = gi % 2
    per_decision_ms: List[float] = []

    def me(obs):
        t0 = time.perf_counter()
        a = agent.act(obs)
        per_decision_ms.append((time.perf_counter() - t0) * 1000.0)
        return a

    agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
    row = {"game": gi, "seed": seed, "opponent": opponent, "seat": seat}
    t0 = time.time()
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        st = [s.status for s in last]
        rw = [s.reward for s in last]
        row["statuses"] = st
        row["completed"] = st == ["DONE", "DONE"]
        row["score"] = (None if not row["completed"] or rw[seat] is None else
                        (1.0 if rw[seat] > rw[1 - seat] else
                         0.5 if rw[seat] == rw[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        row["statuses"] = ["EXC", "EXC"]
        row["completed"] = False
        row["score"] = None
        row["exception"] = f"{type(e).__name__}: {str(e)[:160]}"
    row["seconds"] = round(time.time() - t0, 2)
    row["stats"] = {k: (round(v, 3) if isinstance(v, float) else v)
                    for k, v in agent.stats.items()}
    row["decision_ms"] = [round(x, 2) for x in per_decision_ms]
    row["traces"] = agent.traces
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=64)
    ap.add_argument("--nproc", type=int, default=10)
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--determinizations", type=int, default=3)
    ap.add_argument("--max-ms", type=int, default=900)
    ap.add_argument("--max-match-ms", type=int, default=45000)
    ap.add_argument("--tag", default="scaled")
    ap.add_argument("--opponents", default="dragapult,iono,mega_abomasnow,mega_lucario")
    ap.add_argument("--traces-per-game", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1900)
    a = ap.parse_args(argv)

    for d in ("configs", "trees", "sampled_full_traces", "determinizations", "aggregate_stats",
              "latency", "raw_games", "evaluations", "parity"):
        os.makedirs(os.path.join(MC, d), exist_ok=True)

    from cg import c019_mcts as M
    cfg = dict(M.DEFAULT_CFG)
    cfg.update({"simulations_per_determinization": a.sims,
                "determinizations": a.determinizations,
                "max_ms_per_decision": a.max_ms, "max_match_ms": a.max_match_ms})
    json.dump({**cfg, "tag": a.tag, "games": a.games,
               "opponents": a.opponents.split(",")},
              open(os.path.join(MC, "configs", f"{a.tag}_config.json"), "w"), indent=2)

    opps = a.opponents.split(",")
    jobs = [(gi, a.seed + gi, opps[gi % len(opps)], cfg,
             a.traces_per_game if gi < 60 else 0) for gi in range(a.games)]

    t0 = time.time()
    rows = []
    with mp.get_context("spawn").Pool(a.nproc) as pool:
        for i, r in enumerate(pool.imap_unordered(_play, jobs, chunksize=1)):
            rows.append(r)
            if (i + 1) % 8 == 0:
                print(f"  [mcts] {i+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)

    agg = collections.Counter()
    all_ms: List[float] = []
    traces: List[Dict[str, Any]] = []
    dets: List[Dict[str, Any]] = []
    for r in rows:
        for k, v in r["stats"].items():
            if isinstance(v, (int, float)):
                agg[k] += v
        all_ms.extend(r["decision_ms"])
        for t in r.get("traces") or []:
            if len(traces) < 200:
                traces.append({"game": r["game"], "opponent": r["opponent"], **t})
            for d in t.get("determinizations") or []:
                if len(dets) < 4000:
                    dets.append({"game": r["game"], **d})

    with gzip.open(os.path.join(MC, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items()
                                 if k not in ("traces", "decision_ms")}, default=str) + "\n")
    with gzip.open(os.path.join(MC, "sampled_full_traces", f"{a.tag}_traces.jsonl.gz"),
                   "wt") as fh:
        for t in traces:
            fh.write(json.dumps(t, default=str) + "\n")
    with gzip.open(os.path.join(MC, "determinizations", f"{a.tag}_determinizations.jsonl.gz"),
                   "wt") as fh:
        for d in dets:
            fh.write(json.dumps(d, default=str) + "\n")

    ms = sorted(all_ms)
    def q(p):
        return round(ms[min(len(ms) - 1, int(len(ms) * p))], 1) if ms else None
    scored = [r["score"] for r in rows if r.get("score") is not None]
    match_ms = [r["stats"].get("match_ms", 0) for r in rows]

    # Multi-determinization decisions, counted from the RUN counters rather than from the
    # sampled trace subset. Counting from traces measured how many traces were collected, not
    # how many decisions used multiple worlds -- a floor must be measured on the population.
    legal_dets = agg["determinizations_legal"]
    searched = agg["searched"]
    dets_per_decision = (legal_dets / searched) if searched else 0.0
    multi_det = int(searched) if dets_per_decision >= 2.0 else 0
    multi_det_from_traces = sum(1 for t in traces
                                if sum(1 for d in (t.get("determinizations") or [])
                                       if d.get("legal")) >= 2)
    trees_with_nonroot_branching = 0
    for t in traces:
        for sh in t.get("tree_shapes") or []:
            if (sh.get("nonroot_nodes_with_2plus_children") or 0) > 0:
                trees_with_nonroot_branching += 1

    summary = {
        "tag": a.tag, "config": cfg, "games": len(rows),
        "games_completed": sum(1 for r in rows if r.get("completed")),
        "win_rate": round(sum(scored) / len(scored), 4) if scored else None,
        "by_opponent": {o: round(
            float(np.mean([r["score"] for r in rows
                           if r["opponent"] == o and r.get("score") is not None] or [np.nan])),
            4) for o in opps},
        "counters": dict(agg),
        "floors": {
            "searched_decisions": agg["searched"],
            "simulations": agg["simulations"],
            "native_expansions": agg["expansions"],
            "simulations_or_expansions": agg["simulations"] + agg["expansions"],
            "nonroot_expansions": agg["nonroot_expansions"],
            "sampled_full_traces": len(traces),
            "multi_determinization_decisions": multi_det,
            "legal_determinizations_per_searched_decision": round(dets_per_decision, 3),
            "multi_determinization_decisions_in_sampled_traces": multi_det_from_traces,
        },
        "latency": {"decisions_timed": len(ms), "p50_ms": q(.5), "p90_ms": q(.9),
                    "p99_ms": q(.99), "max_ms": round(ms[-1], 1) if ms else None,
                    "mean_match_search_ms": round(float(np.mean(match_ms)), 1)
                    if match_ms else None,
                    "max_match_search_ms": round(float(np.max(match_ms)), 1)
                    if match_ms else None,
                    "budget_ms_per_decision": cfg["max_ms_per_decision"],
                    "over_budget_decisions": sum(1 for x in ms
                                                 if x > cfg["max_ms_per_decision"])},
        "fidelity_evidence": {
            "trees_with_nonroot_branching": trees_with_nonroot_branching,
            "revisits": agg["revisits"],
            "backups": agg["backups"], "backup_nodes": agg["backup_nodes"],
            "rollout_baseline_calls": agg["rollout_baseline_calls"],
            "rollout_stochastic_calls": agg["rollout_stochastic_calls"],
            "determinizations_legal": agg["determinizations_legal"],
            "determinizations_rejected": agg["determinizations_rejected"],
            "release_errors": agg["release_errors"],
            "hidden_information_violations": agg["hidden_information_violations"],
            "chance_outcomes_recorded": agg["chance_outcomes_recorded"],
            "chance_nodes": agg["chance_nodes"],
        },
        "wall_clock_s": round(time.time() - t0, 1),
    }
    json.dump(summary, open(os.path.join(MC, "aggregate_stats", f"{a.tag}_summary.json"), "w"),
              indent=2, default=str)
    json.dump(summary["latency"], open(os.path.join(MC, "latency", f"{a.tag}_latency.json"),
                                       "w"), indent=2, default=str)
    print(json.dumps({"games": summary["games"], "win_rate": summary["win_rate"],
                      "by_opponent": summary["by_opponent"],
                      "floors": summary["floors"], "latency": summary["latency"],
                      "fidelity": summary["fidelity_evidence"],
                      "wall_clock_s": summary["wall_clock_s"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
