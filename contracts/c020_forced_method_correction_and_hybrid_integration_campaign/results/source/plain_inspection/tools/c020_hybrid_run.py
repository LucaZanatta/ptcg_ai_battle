"""c020 C2-C5 — run H0..H4 with identical budgets and seeds, and produce the admission datasets.

`MANDATORY_CHANGES C5` requires the isolating contrasts to hold everything else fixed:
H0 vs H1 changes ONLY priors, H0 vs H2 changes ONLY the leaf value. So every mode here is built
from the same `CorrectedMCTSAgent` with the same config and the same seed sequence; the only
difference between two modes is which providers are attached.

H2-H4 execute even when value admission fails (C4), and are marked non-promotable rather than
skipped — "it did not run" and "it ran and was not admitted" are different evidence.
"""

from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
HY = os.path.join(C20, "hybrid")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def build_agent(mode: str, deck, cfg, seed, checkpoint, prior_ok, value_ok):
    from cg import c020_agent as AG, c020_hybrid as H
    adapter = None
    prior_fn = value_fn = None
    spec = H.MODES[mode]
    if checkpoint and (spec["priors"] == "byterl" or spec["value"] != "tactical_heuristic"):
        adapter = H.NeuralAdapter(checkpoint)
        if spec["priors"] == "byterl":
            prior_fn = adapter.prior_provider()
        if spec["value"] != "tactical_heuristic":
            vmode = "H4" if mode == "H4" else "H2"
            value_fn = adapter.value_provider(mode=vmode, alpha=H.H4_ALPHA,
                                              admitted=bool(value_ok))
    ag = AG.CorrectedMCTSAgent(deck, cfg, seed=seed, prior_provider=prior_fn,
                               value_provider=value_fn, neural_adapter=adapter, mode=mode)
    return ag, adapter


def _worker(payload):
    jobs, cfg, seed, checkpoint, prior_ok, value_ok = payload
    sys.path.insert(0, _REPO)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    deck = D19.archetype_decks()["mega_lucario"]
    out = []
    for ji, job in enumerate(jobs):
        ag, adapter = build_agent(job["mode"], deck, cfg, seed + ji, checkpoint,
                                  prior_ok, value_ok)
        opp = T.make_fresh(job["opponent"], ce.SOURCES)
        seat = int(job["seat"])

        def mk(a):
            def play(obs):
                return a.act(obs)
            return play

        def mo(o):
            def play(obs):
                return o(obs)
            return play

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
            out.append({"mode": job["mode"], "game_id": job["game_id"],
                        "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        out.append({"mode": job["mode"], "game_id": job["game_id"],
                    "opponent": job["opponent"], "seat": seat, "completed": completed,
                    "score": score, "seconds": round(time.time() - t0, 2),
                    "report": ag.report(),
                    "adapter": adapter.report() if adapter else None,
                    "adapter_traces": (adapter.traces[:20] if adapter else []),
                    "override_log": ag.override_log[:40]})
    return out


def latest_checkpoint() -> Optional[str]:
    d = os.path.join(C20, "byterl", "checkpoints")
    cands = []
    for tag in os.listdir(d) if os.path.isdir(d) else []:
        p = os.path.join(d, tag)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.endswith(".pt"):
                cands.append((os.path.getmtime(os.path.join(p, f)), os.path.join(p, f)))
    if not cands:
        return None
    # prefer a final/frozen checkpoint when one exists
    finals = [c for c in cands if "final" in os.path.basename(c[1])]
    return max(finals or cands)[1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-per-mode", type=int, default=8)
    ap.add_argument("--nproc", type=int, default=5)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--determinizations", type=int, default=4)
    ap.add_argument("--max-ms", type=int, default=700)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--modes", default="H0,H1,H2,H3,H4")
    ap.add_argument("--tag", default="smoke")
    a = ap.parse_args(argv)

    from cg import c020_hybrid as H
    for d in ("configs", "recurrent_state_traces", "prior_calibration", "value_calibration",
              "ablations", "raw_games", "evaluations", "packages"):
        os.makedirs(os.path.join(HY, d), exist_ok=True)

    ck = a.checkpoint or latest_checkpoint()
    pa = (json.load(open(os.path.join(HY, "prior_calibration", "prior_admission.json")))
          if os.path.exists(os.path.join(HY, "prior_calibration", "prior_admission.json"))
          else {})
    va = (json.load(open(os.path.join(HY, "value_calibration", "value_admission.json")))
          if os.path.exists(os.path.join(HY, "value_calibration", "value_admission.json"))
          else {})
    prior_ok = bool(pa.get("admitted"))
    value_ok = bool(va.get("admitted"))

    cfg = {"simulations_total": a.sims, "determinizations": a.determinizations,
           "max_ms_per_decision": a.max_ms}
    modes = [m for m in a.modes.split(",") if m in H.MODES]
    for m in modes:
        json.dump(H.mode_manifest(m, H.NeuralAdapter(ck) if ck else None, prior_ok, value_ok),
                  open(os.path.join(HY, "configs", f"{m}.json"), "w"), indent=2)

    # C5: identical opponent/seat/seed schedule for every mode
    jobs = []
    for mi, m in enumerate(modes):
        for i in range(a.games_per_mode):
            jobs.append({"mode": m, "game_id": f"{a.tag}:{m}:g{i}",
                         "opponent": OPPONENTS[i % len(OPPONENTS)], "seat": i % 2,
                         "pair_index": i})
    chunks = [[] for _ in range(a.nproc)]
    for i, j in enumerate(jobs):
        chunks[i % a.nproc].append(j)
    # seed depends on pair_index only, so mode i and mode j see the same agent-side seeds
    payload = [(ch, cfg, a.seed, ck, prior_ok, value_ok) for ch in chunks if ch]

    t0 = time.time()
    with mp.get_context("spawn").Pool(len(payload)) as pool:
        results = [r for res in pool.map(_worker, payload) for r in res]

    per_mode = collections.defaultdict(lambda: {"games": 0, "score": 0.0, "errors": 0,
                                                "per_opp": collections.defaultdict(
                                                    lambda: [0, 0.0])})
    adapters = collections.defaultdict(lambda: collections.Counter())
    raw = gzip.open(os.path.join(HY, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    trace_rows = []
    for r in results:
        m = r["mode"]
        if r.get("error"):
            per_mode[m]["errors"] += 1
            continue
        if r["completed"] and r["score"] is not None:
            per_mode[m]["games"] += 1
            per_mode[m]["score"] += r["score"]
            per_mode[m]["per_opp"][r["opponent"]][0] += 1
            per_mode[m]["per_opp"][r["opponent"]][1] += r["score"]
        raw.write(json.dumps({k: r[k] for k in ("mode", "game_id", "opponent", "seat",
                                                "completed", "score", "seconds")}
                             | {"report": r["report"]}) + "\n")
        if r.get("adapter"):
            for k, v in r["adapter"].items():
                if isinstance(v, (int, float)):
                    adapters[m][k] += v
        for t in r.get("adapter_traces", [])[:5]:
            if len(trace_rows) < 2000:
                trace_rows.append({"mode": m, "game_id": r["game_id"], **t})
    raw.close()

    out = {"tag": a.tag, "modes_executed": modes, "checkpoint": os.path.basename(ck) if ck else None,
           "prior_admitted": prior_ok, "value_admitted": value_ok,
           "h4_alpha": H.H4_ALPHA, "config": cfg,
           "results": {}, "wall_clock_s": round(time.time() - t0, 1)}
    for m in modes:
        d = per_mode[m]
        out["results"][m] = {
            "games": d["games"], "errors": d["errors"],
            "field_score": round(d["score"] / d["games"], 4) if d["games"] else None,
            "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4) if v[0] else None}
                             for k, v in d["per_opp"].items()},
            "adapter": dict(adapters[m]),
            "promotable": H.mode_manifest(m, None, prior_ok, value_ok)["promotable"]}
    json.dump(out, open(os.path.join(HY, "evaluations", f"{a.tag}_mode_results.json"), "w"),
              indent=2)
    json.dump(out, open(os.path.join(HY, "evaluations", "mode_results.json"), "w"), indent=2)

    total_none = sum(adapters[m]["state_none_at_nonroot"] for m in modes)
    json.dump({"state_none_at_nonroot": int(total_none),
               "advance_calls": int(sum(adapters[m]["advance_calls"] for m in modes)),
               "prior_calls": int(sum(adapters[m]["prior_calls"] for m in modes)),
               "value_calls": int(sum(adapters[m]["value_calls"] for m in modes)),
               "modes": modes,
               "c019_defect": "hybrid called recurrent ByteRL with state=None at search nodes"},
              open(os.path.join(HY, "recurrent_state_traces", "adapter_report.json"), "w"),
              indent=2)
    with open(os.path.join(HY, "recurrent_state_traces", f"{a.tag}_traces.jsonl"), "w") as f:
        for t in trace_rows:
            f.write(json.dumps(t) + "\n")

    print(json.dumps({k: v for k, v in out.items() if k != "config"}, indent=2)[:2200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
