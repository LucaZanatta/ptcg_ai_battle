"""c020 F03 — frozen identity-safe final panel.

`CONTRACT §6` names eleven candidates that must face the same field. Two identity rules matter and
both were learned the hard way in c019:

  * results are paired back to jobs by `game_id`, NEVER by list position, because a round-robin
    worker pool returns them in worker order;
  * every candidate faces the same opponents at the same seats with the same agent-side seeds.

What CANNOT be controlled is stated rather than claimed: `make("cabt")` exposes no environment
seed, so shuffles and coin flips differ game to game and cannot be paired across candidates. The
protocol records that explicitly (c019 initially claimed an identical schedule it did not have).
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
FP = os.path.join(C20, "final_panel")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - m) / d, 4), round((c + m) / d, 4)]


def build(cid: str, deck, seed: int, cfg: Dict[str, Any]):
    """Every candidate the contract names. Unknown ids raise rather than silently degrade."""
    from cg import teachers as T, c009_eval as ce

    if cid == "BASELINE_OFFICIAL_MEGA_LUCARIO":
        agent = T.make_fresh("mega_lucario", ce.SOURCES)

        def play(obs):
            return agent(obs)
        return play, None

    if cid == "C019_PIMC_PUCT_CONTROL":
        from cg import c019_ismcts as IS19
        a = IS19.ISMCTSAgent(deck, cfg.get("c019_mcts") or {}, seed=seed)

        def play(obs):
            return a.act(obs)
        return play, a

    if cid == "C019_BYTERL_CONTROL":
        # Delegate to c019's OWN panel builder. A control is only a control if it is the code
        # being controlled for: re-implementing the c019 agent inside c020 would compare c020
        # against my paraphrase of c019 rather than against c019. The first attempt did exactly
        # that and returned an empty payload on encode failure, so all four smoke games went
        # incomplete -- recorded in failures/.
        sys.path.insert(0, _REPO)
        from tools.c019_panel import build_candidate as build19
        play, handle = build19("ptcg_byterl_v0", deck, seed,
                               {"byterl_checkpoint": cfg["c019_byterl_checkpoint"]})
        return play, handle

    if cid == "C019_HYBRID_CONTROL":
        # c019's hybrid, delegated to c019's own builder for the same reason as the ByteRL
        # control: the artifact must be the code being controlled for. c019's hybrid is the one
        # that called the recurrent model with state=None at every node (audit #14), which is
        # exactly the behaviour C1 corrects, so it belongs on the panel as the contrast.
        sys.path.insert(0, _REPO)
        from tools.c019_panel import build_candidate as build19h
        play, handle = build19h("ptcg_ismcts_hybrid_v0", deck, seed,
                                {"mcts": cfg.get("c019_mcts") or {},
                                 "byterl_checkpoint": cfg["c019_byterl_checkpoint"],
                                 "leaf_value_calibrated": True})
        return play, handle

    if cid == "C020_CORRECTED_MCTS":
        from cg import c020_agent as AG
        a = AG.CorrectedMCTSAgent(deck, cfg.get("c020_mcts") or {}, seed=seed,
                                  mode=cid)

        def play(obs):
            return a.act(obs)
        return play, a

    if cid == "C020_CORRECTED_BYTERL":
        import torch
        from cg import c020_byterl_model as M, c020_byterl_actor as AC
        ck = cfg["c020_byterl_checkpoint"]
        model = M.PTCGByteRL()
        model.load_state_dict(torch.load(ck, map_location="cpu")["state_dict"])
        model.eval()
        actor = AC.ByteRLActor(model, deck, version=-1, greedy=True, seed=seed)

        def play(obs):
            return actor.act(obs)
        return play, actor

    if cid.startswith("C020_H"):
        from tools.c020_hybrid_run import build_agent
        mode = cid.replace("C020_", "")
        ag, adapter = build_agent(mode, deck, cfg.get("c020_mcts") or {}, seed,
                                  cfg.get("c020_byterl_checkpoint"),
                                  cfg.get("prior_admitted", False),
                                  cfg.get("value_admitted", False))

        def play(obs):
            return ag.act(obs)
        return play, ag

    raise ValueError(f"unknown candidate {cid}")


def _worker(payload):
    jobs, cfg, deck = payload
    sys.path.insert(0, _REPO)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    out = []
    for job in jobs:
        try:
            me, handle = build(job["candidate_id"], deck, job["seed"], cfg)
        except Exception as e:  # noqa: BLE001
            out.append({**{k: job[k] for k in ("candidate_id", "opponent_id", "seat", "seed",
                                               "pair_index", "game_id")},
                        "error": f"build: {type(e).__name__}: {e}"[:200], "completed": False})
            continue
        opp = T.make_fresh(job["opponent_id"], ce.SOURCES)
        seat = int(job["seat"])

        def mo(o):
            def f(obs):
                return o(obs)
            return f

        agents = [me, mo(opp)] if seat == 0 else [mo(opp), me]
        t0 = time.time()
        row = {k: job[k] for k in ("candidate_id", "opponent_id", "seat", "seed",
                                   "pair_index", "game_id")}
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            done = [s.status for s in last] == ["DONE", "DONE"]
            rw = [s.reward for s in last]
            row["completed"] = bool(done and rw[seat] is not None)
            row["score"] = (None if not row["completed"] else
                            (1.0 if rw[seat] > rw[1 - seat] else
                             (0.5 if rw[seat] == rw[1 - seat] else 0.0)))
        except Exception as e:  # noqa: BLE001
            row["completed"] = False
            row["error"] = f"{type(e).__name__}: {e}"[:200]
        row["seconds"] = round(time.time() - t0, 2)
        rep = getattr(handle, "report", None)
        if callable(rep):
            try:
                row["search_match_ms"] = rep().get("match_search_ms")
                row["overrides"] = rep().get("overrides")
                row["override_opportunities"] = rep().get("override_opportunities")
            except Exception:  # noqa: BLE001
                pass
        out.append(row)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="BASELINE_OFFICIAL_MEGA_LUCARIO,C020_CORRECTED_MCTS")
    ap.add_argument("--games-per-pair", type=int, default=25)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260728)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--determinizations", type=int, default=4)
    ap.add_argument("--max-ms", type=int, default=700)
    ap.add_argument("--tag", default="final")
    ap.add_argument("--append", action="store_true",
                    help="merge with an existing raw file for this tag")
    a = ap.parse_args(argv)

    from cg import c019_determinize as D19
    deck = D19.archetype_decks()["mega_lucario"]
    os.makedirs(FP, exist_ok=True)

    cm = json.load(open(os.path.join(C20, "controls", "control_manifest.json")))
    c19ck = cm["controls"]["C019_BYTERL_CONTROL"].get("final_checkpoint")
    c19ck = os.path.join(_REPO, c19ck) if c19ck else None
    c20ck = None
    cands_ck = []
    for root, _d, fs in os.walk(os.path.join(C20, "byterl", "checkpoints")):
        for f in fs:
            if f.endswith(".pt"):
                cands_ck.append((os.path.getmtime(os.path.join(root, f)),
                                 os.path.join(root, f)))
    finals = [c for c in cands_ck if "final" in os.path.basename(c[1])]
    if cands_ck:
        c20ck = max(finals or cands_ck)[1]

    def jload(p, d=None):
        try:
            return json.load(open(os.path.join(C20, p)))
        except (OSError, ValueError):
            return d

    cfg = {
        "c020_mcts": {"simulations_total": a.sims, "determinizations": a.determinizations,
                      "max_ms_per_decision": a.max_ms},
        "c019_mcts": {"simulations_per_determinization": 12, "determinizations": 1,
                      "max_ms_per_decision": 120},
        "c019_byterl_checkpoint": c19ck,
        "c020_byterl_checkpoint": c20ck,
        "prior_admitted": bool((jload("hybrid/prior_calibration/prior_admission.json", {}) or {})
                               .get("admitted")),
        "value_admitted": bool((jload("hybrid/value_calibration/value_admission.json", {}) or {})
                               .get("admitted")),
    }

    # per-candidate game counts: "NAME:N" overrides --games-per-pair for that candidate.
    # The floors differ per candidate (800 baseline-vs-corrected-MCTS games, 200 per promotable
    # hybrid mode, 40 diagnostic for non-promotable), and running every candidate at the largest
    # count would spend hours of search time producing games no floor asks for.
    spec = {}
    cands = []
    for tok in a.candidates.split(","):
        if not tok:
            continue
        name, _, n = tok.partition(":")
        cands.append(name)
        spec[name] = int(n) if n else a.games_per_pair
    jobs = []
    for c in cands:
        for oi, opp in enumerate(OPPONENTS):
            for g in range(spec[c]):
                jobs.append({"candidate_id": c, "opponent_id": opp, "seat": g % 2,
                             "seed": a.seed + oi * 1000 + g,   # depends on pair only
                             "pair_index": g,
                             "game_id": f"{a.tag}:{c}:{opp}:{g}"})

    protocol = {
        "tag": a.tag, "candidates": cands, "opponents": OPPONENTS,
        "games_per_pair": spec, "total_games": len(jobs),
        "frozen_at_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                           capture_output=True, text=True).stdout.strip(),
        "config": cfg,
        "seat_assignment": "alternating by pair index; identical across candidates",
        "identical_opponent_and_seat_schedule_across_candidates": True,
        "identical_agent_side_seeds_across_candidates": True,
        "identical_environment_randomness_across_candidates": False,
        "environment_randomness_note":
            'make("cabt") exposes actTimeout/episodeSteps/runTimeout but NO seed, so shuffles '
            "and coin flips are not paired between candidates. Differences smaller than the "
            "reported Wilson interval are not attributable to the candidate.",
        "results_paired_by": "game_id (never by list position)",
    }
    json.dump(protocol, open(os.path.join(FP, f"{a.tag}_registered_protocol.json"), "w"),
              indent=2)

    chunks = [[] for _ in range(a.nproc)]
    for i, j in enumerate(jobs):
        chunks[i % a.nproc].append(j)
    payload = [(ch, cfg, deck) for ch in chunks if ch]
    print(f"[panel] {len(jobs)} games: {len(cands)} candidates x {len(OPPONENTS)} opponents "
          f"x {a.games_per_pair}", flush=True)

    t0 = time.time()
    with mp.get_context("spawn").Pool(len(payload)) as pool:
        rows = [r for res in pool.map(_worker, payload) for r in res]

    by_id = {r["game_id"]: r for r in rows}
    ordered = [by_id[j["game_id"]] for j in jobs if j["game_id"] in by_id]

    # Batches append to ONE raw file and aggregates are computed from the union, so a panel run
    # in two batches produces exactly the artifact a single run would. The registered protocol is
    # frozen before either batch, and no candidate's configuration differs between them.
    raw_path = os.path.join(FP, f"{a.tag}_raw_games.jsonl.gz")
    prior = []
    if a.append and os.path.exists(raw_path):
        try:
            with gzip.open(raw_path, "rt") as f:
                prior = [json.loads(l) for l in f if l.strip()]
        except (EOFError, OSError, ValueError):
            prior = []
    seen = {r.get("game_id") for r in ordered}
    ordered = [r for r in prior if r.get("game_id") not in seen] + ordered
    cands = sorted({r["candidate_id"] for r in ordered},
                   key=lambda c: (c not in cands, cands.index(c) if c in cands else 0))
    with gzip.open(raw_path, "wt") as f:
        for r in ordered:
            f.write(json.dumps(r) + "\n")
    h = hashlib.sha256(open(raw_path, "rb").read()).hexdigest()

    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in ordered:
        if r.get("completed") and r.get("score") is not None:
            agg[(r["candidate_id"], r["opponent_id"])][0] += 1
            agg[(r["candidate_id"], r["opponent_id"])][1] += r["score"]

    results, cis = [], {}
    for c in cands:
        row = {"candidate_id": c}
        tot_n = tot_s = 0
        for opp in OPPONENTS:
            n, s = agg[(c, opp)]
            row[f"{opp}_games"] = n
            row[f"{opp}_rate"] = round(s / n, 4) if n else None
            row[f"{opp}_ci"] = wilson(s, n)
            tot_n += n
            tot_s += s
        row["games"] = tot_n
        row["field_score"] = round(tot_s / tot_n, 4) if tot_n else None
        row["field_ci"] = wilson(tot_s, tot_n)
        rates = [(o, row[f"{o}_rate"]) for o in OPPONENTS if row[f"{o}_rate"] is not None]
        if rates:
            w = min(rates, key=lambda kv: kv[1])
            row["worst_matchup"], row["worst_matchup_rate"] = w
        secs = [r["seconds"] for r in ordered if r["candidate_id"] == c]
        row["max_game_seconds"] = max(secs) if secs else None
        ms = [r.get("search_match_ms") for r in ordered
              if r["candidate_id"] == c and r.get("search_match_ms")]
        row["max_search_match_ms"] = max(ms) if ms else None
        ovs = [(r.get("overrides") or 0, r.get("override_opportunities") or 0)
               for r in ordered if r["candidate_id"] == c]
        row["overrides"] = sum(x[0] for x in ovs)
        row["override_opportunities"] = sum(x[1] for x in ovs)
        row["incomplete_games"] = sum(1 for r in ordered
                                      if r["candidate_id"] == c and not r.get("completed"))
        results.append(row)
        cis[c] = {"field_ci": row["field_ci"],
                  **{o: row[f"{o}_ci"] for o in OPPONENTS}}

    out = {"tag": a.tag, "protocol": protocol, "results": results,
           "played_games": len(ordered), "scored_games": sum(r["games"] for r in results),
           "incomplete_games": sum(r["incomplete_games"] for r in results),
           "raw_file": os.path.basename(raw_path), "raw_sha256": h,
           "wall_clock_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(FP, f"{a.tag}_aggregates.json"), "w"), indent=2)
    json.dump(cis, open(os.path.join(FP, f"{a.tag}_confidence_intervals.json"), "w"), indent=2)
    print(json.dumps({"scored": out["scored_games"], "incomplete": out["incomplete_games"],
                      "wall_clock_s": out["wall_clock_s"]}, indent=2))
    for r in results:
        print(f"  {r['candidate_id']:34s} n={r['games']:4d} field={r['field_score']} "
              f"ci={r['field_ci']} worst={r.get('worst_matchup')}@{r.get('worst_matchup_rate')} "
              f"max_game={r['max_game_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
