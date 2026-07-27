"""c019 §11 — frozen identity-safe common evaluation panel.

Every candidate faces the same opponents at the same seeds and seats, and the protocol is written
to disk BEFORE the first game. Aggregates are recomputed from raw rows using each row's own
`candidate_id`/`opponent_id`; worker results are never positionally zipped onto the job list,
which is how a panel silently credits one agent with another's wins (F01).

Candidates are constructed here so the panel controls identity rather than inheriting whatever a
caller passed.
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

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
FP = os.path.join(C19, "final_panel")

OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def jload_local(rel):
    try:
        with open(os.path.join(C19, rel)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - m) / d, 4), round((c + m) / d, 4))


def build_candidate(cid: str, deck, seed: int, cfg: Dict[str, Any]):
    """Returns a ONE-PARAMETER agent callable.

    One parameter is mandatory: kaggle_environments passes (observation, configuration) to any
    callable that accepts two, which silently replaced a captured model with a config object
    earlier in this campaign (see failures/).
    """
    from cg import teachers as T, c009_eval as ce

    if cid == "baseline_official_mega_lucario":
        agent = T.make_fresh("mega_lucario", ce.SOURCES)

        def play(obs):
            return agent(obs)
        return play, None

    if cid == "ptcg_ismcts_v0":
        from cg import c019_ismcts as IS
        a = IS.ISMCTSAgent(deck, cfg.get("mcts") or {}, seed=seed)

        def play(obs):
            return a.act(obs)
        return play, a

    if cid == "ptcg_ismcts_hybrid_v0":
        # The SAME search, with the ByteRL adapters injected -- the only difference from
        # ptcg_ismcts_v0 is the two provider arguments, so a delta between them is attributable
        # to the adapters and to nothing else. The leaf-value adapter is enabled only because
        # H02's calibration gate passed on held-out leaves; DECISION_RULES forbids enabling it
        # on the grounds that the model merely exists.
        from cg import c019_ismcts as IS, c019_hybrid as HY
        ck = cfg.get("byterl_checkpoint")
        cal = cfg.get("leaf_value_calibrated")
        if not ck:
            raise ValueError("hybrid candidate requires --byterl-checkpoint")
        if not cal:
            raise ValueError("hybrid candidate requires a PASSED H02 calibration; refusing to "
                             "enable an uncalibrated leaf-value adapter")
        a = IS.ISMCTSAgent(deck, cfg.get("mcts") or {}, seed=seed,
                           prior_provider=HY.ByteRLPriorProvider(ck, enabled=True),
                           value_provider=HY.ByteRLLeafValue(ck, enabled=True, calibrated=True))

        def play(obs):
            return a.act(obs)
        return play, a

    if cid in ("ptcg_ismcts_priors_only_v0", "ptcg_ismcts_value_only_v0"):
        # Ablation. The combined hybrid injects TWO adapters at once, so a delta against pure
        # MCTS cannot be attributed to either. These isolate one adapter each against the same
        # search and the same config, which is the only way to say WHICH one moved the result.
        from cg import c019_ismcts as IS, c019_hybrid as HY
        ck = cfg.get("byterl_checkpoint")
        if not ck:
            raise ValueError("ablation candidates require --byterl-checkpoint")
        priors = cid == "ptcg_ismcts_priors_only_v0"
        if not priors and not cfg.get("leaf_value_calibrated"):
            raise ValueError("value-only ablation requires a PASSED H02 calibration")
        a = IS.ISMCTSAgent(
            deck, cfg.get("mcts") or {}, seed=seed,
            prior_provider=HY.ByteRLPriorProvider(ck, enabled=True) if priors else None,
            value_provider=(None if priors else
                            HY.ByteRLLeafValue(ck, enabled=True, calibrated=True)))

        def play(obs):
            return a.act(obs)
        return play, a

    if cid.startswith("ptcg_byterl"):
        import torch
        from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M
        from cg import api as A
        ckpt = cfg.get("byterl_checkpoint")
        model = M.PTCGByteRL()
        model.load_state_dict(torch.load(ckpt, map_location="cpu")["state_dict"])
        model.eval()
        state = [None]

        def play(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return list(deck)
            try:
                o = A.to_observation_class(obs)
                f = E.encode(o)
            except Exception:  # noqa: BLE001
                return []
            b = M.to_torch(f)
            with torch.no_grad():
                logits, _v, nxt = model.forward(b, state[0])
                probs = M.masked_probs(logits, b["opt_mask"])[0]
            state[0] = (nxt[0].detach(), nxt[1].detach())
            k = min(int(f["n_options"]), E.N_OPT)
            if k <= 0:
                return []
            lo = int(sel.get("minCount") or 0)
            hi = int(sel.get("maxCount") or 1)
            n_pick = max(1, min(lo if lo > 0 else 1, hi if hi > 0 else 1, k))
            p = probs[:k]
            s = float(p.sum())
            picks = (list(range(n_pick)) if s <= 0 else
                     torch.topk(p / p.sum(), n_pick).indices.tolist())
            opts = K.canonical_options(sel)
            try:
                chosen = [opts[i] for i in sorted(picks) if i < len(opts)]
                if chosen:
                    return K.to_select_payload(chosen, sel)
            except Exception:  # noqa: BLE001
                pass
            return sorted(set(min(int(i), max(0, len(opts) - 1)) for i in picks))
        return play, None

    raise ValueError(f"unknown candidate {cid}")


def _play(job):
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    import torch
    torch.set_num_threads(1)
    deck = T.read_deck("mega_lucario", ce.SOURCES)
    me, handle = build_candidate(job["candidate_id"], deck, job["seed"], job["cfg"])
    opp_agent = T.make_fresh(job["opponent_id"], ce.SOURCES)

    def opp(obs):
        return opp_agent(obs)

    seat = job["seat"]
    agents = [me, opp] if seat == 0 else [opp, me]
    row = {k: job[k] for k in ("candidate_id", "opponent_id", "seat", "seed", "pair_index")}
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
    if handle is not None:
        row["search_match_ms"] = round(getattr(handle, "match_ms", 0.0), 1)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="baseline_official_mega_lucario,ptcg_ismcts_v0")
    ap.add_argument("--games-per-pair", type=int, default=25)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1990)
    ap.add_argument("--byterl-checkpoint", default="")
    ap.add_argument("--mcts-sims", type=int, default=48)
    ap.add_argument("--mcts-determinizations", type=int, default=3)
    ap.add_argument("--mcts-max-ms", type=int, default=700)
    ap.add_argument("--tag", default="final")
    a = ap.parse_args(argv)
    os.makedirs(FP, exist_ok=True)
    cands = [c for c in a.candidates.split(",") if c]
    cfg = {"mcts": {"simulations_per_determinization": a.mcts_sims,
                    "determinizations": a.mcts_determinizations,
                    "max_ms_per_decision": a.mcts_max_ms},
           "byterl_checkpoint": a.byterl_checkpoint,
           # read from the H02 artefact, not from a flag -- the panel must not be able to
           # enable the leaf-value adapter by assertion
           "leaf_value_calibrated": bool(
               (jload_local("hybrid/comparisons/leaf_value_calibration.json") or {})
               .get("may_enable_leaf_value_adapter"))}

    jobs = []
    for oi, opp in enumerate(OPPONENTS):
        for g in range(a.games_per_pair):
            seed = a.seed + oi * 10007 + g
            for c in cands:
                jobs.append({"candidate_id": c, "opponent_id": opp, "seat": g % 2,
                             "seed": seed, "pair_index": g, "cfg": cfg})

    # FREEZE the protocol before any game runs
    protocol = {
        "frozen_at_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                           capture_output=True, text=True).stdout.strip(),
        "candidates": cands, "opponents": OPPONENTS,
        "games_per_pair": a.games_per_pair, "total_games": len(jobs),
        "seed_base": a.seed, "seed_list": sorted({j["seed"] for j in jobs}),
        "seat_assignment": "alternating by pair index; identical across candidates",
        # What IS controlled: every candidate faces the same opponents, the same seats and the
        # same agent-side RNG seeds. What is NOT: the `cabt` environment exposes no seed
        # (configuration is actTimeout/episodeSteps/runTimeout only), so deck shuffles and coin
        # flips differ game to game and cannot be paired across candidates. Claiming identical
        # game conditions would overstate the design; the Wilson intervals carry that variance.
        "identical_opponent_and_seat_schedule_across_candidates": True,
        "identical_agent_side_seeds_across_candidates": True,
        "identical_environment_randomness_across_candidates": False,
        "environment_seed_available": False,
        "uncontrolled_variance_note": (
            "kaggle_environments make('cabt') accepts no seed, so shuffle/flip randomness is "
            "not paired between candidates. Differences smaller than the reported Wilson "
            "intervals should not be read as method differences."),
        "scoring": "win 1.0, draw 0.5, loss 0.0; unscored unless both seats are DONE",
        "ranking": ("external score evidence, then common-panel field score, then score vs "
                    "frozen baseline/Dragapult, then worst meaningful matchup, then package "
                    "reliability and latency (§11)"),
        "config": cfg,
        "deck": "mega_lucario, frozen for both methods (§4)",
        "safe_random_agents": "not included; §11 makes them reliability checks only",
    }
    json.dump(protocol, open(os.path.join(FP, f"{a.tag}_registered_protocol.json"), "w"),
              indent=2, default=str)
    print(f"[panel] {len(jobs)} games: {len(cands)} candidates x {len(OPPONENTS)} opponents "
          f"x {a.games_per_pair}", flush=True)

    t0 = time.time()
    rows = []
    with mp.get_context("spawn").Pool(a.nproc) as pool:
        for i, r in enumerate(pool.imap_unordered(_play, jobs, chunksize=1)):
            rows.append(r)
            if (i + 1) % 25 == 0:
                print(f"  [panel] {i+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)

    raw = os.path.join(FP, f"{a.tag}_raw_games.jsonl.gz")
    with gzip.open(raw, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")

    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in rows:
        if r.get("score") is None:
            continue
        agg[(r["candidate_id"], r["opponent_id"])][0] += 1
        agg[(r["candidate_id"], r["opponent_id"])][1] += r["score"]

    results = []
    for c in cands:
        row = {"candidate_id": c}
        tot_n = tot_s = 0
        worst = (2.0, None)
        for o in OPPONENTS:
            n, s = agg[(c, o)]
            row[f"{o}_games"] = n
            row[f"{o}_rate"] = round(s / n, 4) if n else None
            if n:
                row[f"{o}_ci"] = list(wilson(s, n))
                if s / n < worst[0]:
                    worst = (s / n, o)
            tot_n += n
            tot_s += s
        row["games"] = tot_n
        row["field_score"] = round(tot_s / tot_n, 4) if tot_n else None
        row["field_ci"] = list(wilson(tot_s, tot_n)) if tot_n else None
        row["worst_matchup"] = worst[1]
        row["worst_matchup_rate"] = round(worst[0], 4) if worst[1] else None
        ms = [r.get("search_match_ms") for r in rows
              if r["candidate_id"] == c and r.get("search_match_ms") is not None]
        row["mean_search_match_ms"] = round(float(np.mean(ms)), 1) if ms else None
        row["max_search_match_ms"] = round(float(np.max(ms)), 1) if ms else None
        secs = [r["seconds"] for r in rows if r["candidate_id"] == c]
        row["mean_game_seconds"] = round(float(np.mean(secs)), 2) if secs else None
        row["max_game_seconds"] = round(float(np.max(secs)), 2) if secs else None
        row["incomplete_games"] = sum(1 for r in rows
                                      if r["candidate_id"] == c and not r.get("completed"))
        results.append(row)
    results.sort(key=lambda r: (-(r["field_score"] or 0), -(r["worst_matchup_rate"] or 0)))

    h = hashlib.sha256()
    with open(raw, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    out = {"tag": a.tag, "protocol": protocol, "results": results,
           "played_games": len(rows),
           "scored_games": sum(1 for r in rows if r.get("score") is not None),
           "incomplete_games": sum(1 for r in rows if not r.get("completed")),
           "raw_file": os.path.relpath(raw, C19), "raw_sha256": h.hexdigest(),
           "wall_clock_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(FP, f"{a.tag}_aggregates.json"), "w"), indent=2,
              default=str)
    print(json.dumps({"scored": out["scored_games"], "incomplete": out["incomplete_games"],
                      "wall_clock_s": out["wall_clock_s"]}, indent=2))
    for r in results:
        print(f"  {r['candidate_id']:34s} n={r['games']:4d} field={r['field_score']} "
              f"ci={r['field_ci']} worst={r['worst_matchup']}@{r['worst_matchup_rate']} "
              f"max_game={r['max_game_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
