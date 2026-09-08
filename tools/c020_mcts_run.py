"""c020 — scaled corrected-MCTS run producing every artifact `CONTRACT §5` requires.

Runs real games with the corrected agent and writes the shared information-set tables,
determinization records, tree traces, leaf feature decompositions, override logs and latency to
`results/mcts/`. The floors it feeds are live searched decisions, real `search_step` expansions,
4-determinization decisions, complete tree traces and recorded override opportunities.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
MC = os.path.join(C20, "mcts")

OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def _worker(payload):
    jobs, cfg, seed = payload
    sys.path.insert(0, _REPO)
    import torch
    # one thread per worker -- see tools/c020_panel.py and
    # failures/DEFECT_panel_results_depended_on_machine_load.md
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    from cg import c020_agent as AG

    deck = D19.archetype_decks()["mega_lucario"]
    out = []
    for ji, job in enumerate(jobs):
        ag = AG.CorrectedMCTSAgent(deck, cfg, seed=seed + ji)
        opp = T.make_fresh(job["opponent"], ce.SOURCES)
        seat = int(job["seat"])

        def make_play(a):
            def play(obs):
                return a.act(obs)
            return play

        def make_opp(o):
            def play(obs):
                return o(obs)
            return play

        agents = ([make_play(ag), make_opp(opp)] if seat == 0
                  else [make_opp(opp), make_play(ag)])
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
            out.append({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        out.append({
            "game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
            "completed": completed, "score": score, "seconds": round(time.time() - t0, 2),
            "report": ag.report(),
            "override_log": ag.override_log[:200],
            "det_log": ag.det_log[:40],
            "infoset_dumps": ag.infoset_dumps[:3],
            "tree_traces": ag.tree_traces[:6],
            "leaf_samples": ag.leaf_samples[:40],
            "exceptions": ag.exceptions[:3],
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=120)
    ap.add_argument("--nproc", type=int, default=6)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--determinizations", type=int, default=4)
    ap.add_argument("--max-ms", type=int, default=700)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--tag", default="scaled")
    ap.add_argument("--no-overrides", action="store_true",
                    help="M09 arm: search and log, but always play the baseline")
    ap.add_argument("--no-veto", action="store_true",
                    help="M09 arm: override gate without the conservative veto")
    a = ap.parse_args(argv)

    for d in ("configs", "infoset_tables", "determinizations", "tree_traces", "leaf_features",
              "override_logs", "raw_games", "evaluations", "latency", "ablations"):
        os.makedirs(os.path.join(MC, d), exist_ok=True)

    cfg = {"simulations_total": a.sims, "determinizations": a.determinizations,
           "max_ms_per_decision": a.max_ms,
           "override_enabled": not a.no_overrides, "veto_enabled": not a.no_veto}
    from cg import c020_ismcts as S, c020_override as OV, c020_tactical_leaf as TL, \
        c020_determinize as DT
    full_cfg = {**S.DEFAULT_CFG, **cfg}
    json.dump({"config": full_cfg, "override_thresholds": OV.thresholds_report(),
               "leaf_weights": {"version": TL.WEIGHTS_VERSION, "weights": TL.WEIGHTS},
               "archetype_prior": DT.prior_report()},
              open(os.path.join(MC, "configs", f"{a.tag}_config.json"), "w"), indent=2)
    json.dump({"version": TL.WEIGHTS_VERSION, "weights": TL.WEIGHTS,
               "features": TL.feature_names()},
              open(os.path.join(MC, "configs", "leaf_weights.json"), "w"), indent=2)
    json.dump(OV.thresholds_report(),
              open(os.path.join(MC, "configs", "override_thresholds.json"), "w"), indent=2)

    jobs = [{"game_id": f"{a.tag}:g{i}", "opponent": OPPONENTS[i % len(OPPONENTS)],
             "seat": i % 2} for i in range(a.games)]
    chunks = [[] for _ in range(a.nproc)]
    for i, j in enumerate(jobs):
        chunks[i % a.nproc].append(j)
    payload = [(ch, cfg, a.seed + k * 101) for k, ch in enumerate(chunks) if ch]

    t0 = time.time()
    with mp.get_context("spawn").Pool(len(payload)) as pool:
        results = [r for res in pool.map(_worker, payload) for r in res]

    agg = collections.Counter()
    maxes: Dict[str, float] = {}
    per_opp = collections.defaultdict(lambda: [0, 0.0])
    games_f = gzip.open(os.path.join(MC, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    ov_f = gzip.open(os.path.join(MC, "override_logs", f"{a.tag}_overrides.jsonl.gz"), "wt")
    det_f = gzip.open(os.path.join(MC, "determinizations", f"{a.tag}_dets.jsonl.gz"), "wt")
    leaf_f = gzip.open(os.path.join(MC, "leaf_features", f"{a.tag}_leaves.jsonl.gz"), "wt")
    tt = []
    isets = []
    lat = []
    errors = []
    for r in results:
        if r.get("error"):
            errors.append(r)
            continue
        rep = r["report"]
        # Max-like and rate-like fields must NOT be summed. `max_depth_seen` summed over 900
        # games reported 11,034 against a configured max depth of 16, which reads as a runaway
        # search rather than as a sum of per-game maxima.
        MAXY = {"max_depth_seen", "match_search_ms"}
        RATEY = {"override_rate", "step_error_rate"}
        for k, v in rep.items():
            if not isinstance(v, (int, float)):
                continue
            if k in RATEY:
                continue
            if k in MAXY:
                maxes[k] = max(maxes.get(k, 0), v)
            else:
                agg[k] += v
        if r["completed"] and r["score"] is not None:
            per_opp[r["opponent"]][0] += 1
            per_opp[r["opponent"]][1] += r["score"]
        games_f.write(json.dumps({k: r[k] for k in
                                  ("game_id", "opponent", "seat", "completed", "score",
                                   "seconds")} | {"report": rep}) + "\n")
        for o in r["override_log"]:
            ov_f.write(json.dumps({"game_id": r["game_id"], **o}) + "\n")
        for d in r["det_log"]:
            det_f.write(json.dumps({"game_id": r["game_id"], **d}) + "\n")
        for lf in r["leaf_samples"]:
            leaf_f.write(json.dumps({"game_id": r["game_id"], **lf}) + "\n")
        if len(tt) < 400:
            tt.extend({"game_id": r["game_id"], **t} for t in r["tree_traces"])
        if len(isets) < 120:
            isets.extend({"game_id": r["game_id"], **d} for d in r["infoset_dumps"])
        lat.append({"game_id": r["game_id"], "seconds": r["seconds"],
                    "match_search_ms": rep.get("match_search_ms")})
    for f in (games_f, ov_f, det_f, leaf_f):
        f.close()
    json.dump(tt, open(os.path.join(MC, "tree_traces", f"{a.tag}_traces.json"), "w"), indent=2)
    json.dump(isets, open(os.path.join(MC, "infoset_tables", f"{a.tag}_tables.json"), "w"),
              indent=2)
    json.dump(lat, open(os.path.join(MC, "latency", f"{a.tag}_latency.json"), "w"), indent=2)

    shared_multi = sum(t.get("table", {}).get(
        "action_stats_updated_by_multiple_determinizations", 0) for t in tt)
    isets_multi = sum(t.get("table", {}).get(
        "info_sets_reached_by_multiple_determinizations", 0) for t in tt)
    ms = [x["match_search_ms"] or 0 for x in lat]
    summary = {
        "tag": a.tag, "config": full_cfg, "games": len(results), "errors": len(errors),
        "completed": sum(1 for r in results if r.get("completed")),
        **{k: int(v) for k, v in agg.items()},
        **{f"max_{k}" if not k.startswith("max_") else k: v for k, v in maxes.items()},
        "step_error_rate": round(agg["step_errors"] / max(1, agg["step_calls"]), 5),
        "override_rate": round(agg["overrides"] / max(1, agg["override_opportunities"]), 5),
        "shared_action_stats_multi_det": shared_multi,
        "info_sets_multi_det": isets_multi,
        "sampled_full_traces": len(tt),
        # taken from the agent's OWN per-decision counter, not derived from a total
        "decisions_with_4_determinizations": int(agg["decisions_with_4_determinizations"]),
        "decisions_with_2plus_determinizations": int(
            agg["decisions_with_2plus_determinizations"]),
        "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4) if v[0] else None}
                         for k, v in per_opp.items()},
        "field_score": round(sum(v[1] for v in per_opp.values())
                             / max(1, sum(v[0] for v in per_opp.values())), 4),
        "latency": {"max_match_search_ms": max(ms) if ms else 0,
                    "mean_match_search_ms": round(float(np.mean(ms)), 1) if ms else 0,
                    "max_game_seconds": max((x["seconds"] for x in lat), default=0)},
        "wall_clock_s": round(time.time() - t0, 1),
    }
    json.dump(summary, open(os.path.join(MC, "evaluations", "mcts_run_summary.json"), "w"),
              indent=2)
    json.dump(summary, open(os.path.join(MC, "evaluations", f"{a.tag}_summary.json"), "w"),
              indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "config"}, indent=2)[:2200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
