"""c018 M01/M02 input — trusted real-search trajectories.

Every label here comes from `c018_search.plan`, which produces it from real `search_step`
successors. c017's depth-0 labels are NOT used and are not importable from here (§: "do not use
c017 depth-zero labels as trusted training data").

A decision is written as TRUSTED only when its own search actually ran: `searched == True`, the
plan reports at least one real successor, and the action validated legal. Fallback decisions are
written too, flagged `trusted: false`, so the dataset is auditable rather than silently filtered.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
TRAJ = os.path.join(C18, "trajectories")
SEARCH = os.path.join(C18, "search")
SCHEMA_VERSION = "c018.trajectory.v1"
FEAT_KEYS = ("global", "board_rows", "board_dyn", "hand_rows", "hand_dyn", "hand_mask",
             "disc_rows", "disc_mask", "opt_dense", "opt_rows")
KMAX = 32


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def generate(n_games, cfg, prefix, opponents, seed=1801):
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg.safe_policy import validate_selection, MalformedSelection
    from cg import state_encoder_v2 as enc
    from cg.episode_capture import normalize_observation
    import c018_search as S

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    stats = S.new_stats()
    traces = []
    rng = np.random.default_rng(seed)
    rows, games_meta = [], []
    feats = {k: [] for k in FEAT_KEYS + ("n_options", "label_index", "final_outcome")}
    t0 = time.time()

    for gi in range(n_games):
        opp_id = opponents[gi % len(opponents)]
        seat = gi % 2
        base = T.make_fresh("mega_lucario", ce.SOURCES)
        opp = T.make_fresh(opp_id, ce.SOURCES)
        stats["match_ms"] = 0.0
        decisions = []
        bad = [0]

        def me(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            stats["decisions"] += 1
            b = base(obs)
            r = S.plan(obs, b, deck, rng, cfg, stats, traces)
            a = r["action"]
            try:
                validate_selection(list(a), len(sel["option"]), sel["minCount"],
                                   sel["maxCount"])
            except MalformedSelection:
                bad[0] += 1
                a = list(b)
                r = {**r, "searched": False, "reason": "illegal_search_action"}
            n_opt = len(sel["option"])
            trusted = bool(r.get("searched") and (r.get("distinct_successors") or 0) > 0)
            rec = {"schema_version": SCHEMA_VERSION, "search_version": S.SEARCH_VERSION,
                   "leaf_version": S.LEAF_VERSION, "game_index": gi, "opponent_id": opp_id,
                   "seat": seat, "decision_index": len(decisions),
                   "context": int(sel.get("context", -1) or 0), "n_options": n_opt,
                   "min_count": int(sel.get("minCount") or 0),
                   "max_count": int(sel.get("maxCount") or 1),
                   "legal_mask": [1] * n_opt,
                   "baseline_action": list(b), "label_action": list(a),
                   "searched": bool(r.get("searched")), "trusted": trusted,
                   "reason": r.get("reason"),
                   "depth_max": r.get("depth_max"),
                   "distinct_successors": r.get("distinct_successors"),
                   "candidate_scores": r.get("candidate_scores", []),
                   "determinization_archetype": r.get("determinization_archetype"),
                   "search_ms": r.get("ms"),
                   "label_differs_from_baseline": list(a) != list(b)}
            decisions.append(rec)
            try:
                fd = enc.encode(normalize_observation(obs)[0], None)
                for k in FEAT_KEYS:
                    v = np.asarray(fd[k])
                    if k in ("opt_dense", "opt_rows"):
                        pad = np.zeros((KMAX,) + v.shape[1:], dtype=v.dtype)
                        m = min(KMAX, v.shape[0])
                        pad[:m] = v[:m]
                        v = pad
                    feats[k].append(v)
                li = int(a[0]) if a else 0
                feats["n_options"].append(min(n_opt, KMAX))
                feats["label_index"].append(li if li < KMAX else 0)
                feats["final_outcome"].append(0.0)
                rec["_feat_row"] = len(feats["global"]) - 1
            except Exception:  # noqa: BLE001
                stats["featurize_failed"] += 1
                rec["_feat_row"] = None
            return a

        agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
        env = make("cabt")
        try:
            env.run(agents)
            last = env.steps[-1]
            st = [s.status for s in last]
            rw = [s.reward for s in last]
            completed = st == ["DONE", "DONE"]
            outcome = (None if rw[seat] is None or rw[1 - seat] is None else
                       (1.0 if rw[seat] > rw[1 - seat] else
                        0.5 if rw[seat] == rw[1 - seat] else 0.0))
        except Exception as e:  # noqa: BLE001
            st, completed, outcome = ["ERROR", "ERROR"], False, None
            stats[f"game_exception:{type(e).__name__}"] += 1
        for d in decisions:
            d["final_outcome"] = outcome
            d["game_completed"] = completed
            fr = d.get("_feat_row")
            if fr is not None and outcome is not None:
                feats["final_outcome"][fr] = float(outcome)
        rows.extend(decisions)
        games_meta.append({"game_index": gi, "opponent_id": opp_id, "seat": seat,
                           "statuses": st, "completed": completed, "outcome": outcome,
                           "decisions": len(decisions), "invalid": bad[0]})
        if (gi + 1) % 10 == 0:
            tr = sum(1 for r in rows if r["trusted"])
            print(f"[c018 traj] {gi+1}/{n_games} decisions={len(rows)} trusted={tr} "
                  f"steps={stats['step_ok']} {time.time()-t0:.0f}s", flush=True)

    keep = [i for i, r in enumerate(rows) if r.get("final_outcome") is not None]
    fidx = [rows[i]["_feat_row"] for i in keep if rows[i].get("_feat_row") is not None]
    trusted_local = [j for j, i in enumerate(keep)
                     if rows[i].get("_feat_row") is not None and rows[i]["trusted"]]
    os.makedirs(TRAJ, exist_ok=True)
    if fidx:
        np.savez_compressed(os.path.join(TRAJ, f"{prefix}_features.npz"),
                            **{k: np.asarray([feats[k][j] for j in fidx]) for k in feats},
                            trusted_rows=np.asarray(trusted_local, dtype=np.int64))
    rows = [rows[i] for i in keep]
    for r in rows:
        r.pop("_feat_row", None)

    gids = sorted({r["game_index"] for r in rows})
    n = len(gids)
    tr_ids = set(gids[:int(n * 0.7)])
    va_ids = set(gids[int(n * 0.7):int(n * 0.85)])
    for r in rows:
        r["split"] = ("train" if r["game_index"] in tr_ids else
                      "validation" if r["game_index"] in va_ids else "test")

    path = os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz")
    with gzip.open(path, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    n_trusted = sum(1 for r in rows if r["trusted"])
    summary = {
        "schema_version": SCHEMA_VERSION, "search_version": S.SEARCH_VERSION,
        "config": cfg, "games": len(games_meta), "decisions": len(rows),
        "trusted_decisions": n_trusted,
        "trusted_fraction": round(n_trusted / max(1, len(rows)), 4),
        "real_search_counters": {k: (round(v, 2) if isinstance(v, float) else v)
                                 for k, v in stats.items()},
        "games_completed": sum(1 for g in games_meta if g["completed"]),
        "invalid_actions": sum(g["invalid"] for g in games_meta),
        "split_counts": dict(collections.Counter(r["split"] for r in rows)),
        "split_by": "game_index",
        "trajectory_file": os.path.relpath(path, _REPO),
        "trajectory_sha256": sha_file(path),
        "feature_file": os.path.relpath(
            os.path.join(TRAJ, f"{prefix}_features.npz"), _REPO),
        "uses_c017_labels": False,
        "games_meta": games_meta,
        "sample_traces": traces[:60],
    }
    os.makedirs(SEARCH, exist_ok=True)
    json.dump(summary, open(os.path.join(SEARCH, f"{prefix}_search_summary.json"), "w"),
              indent=2, default=str)
    return summary


def main(argv=None):
    import c018_search as S
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--prefix", default="smoke")
    ap.add_argument("--beam", type=int, default=3)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--nodes", type=int, default=40)
    a = ap.parse_args(argv)
    cfg = dict(S.DEFAULT_CFG)
    cfg.update({"beam_width": a.beam, "max_depth": a.depth, "max_nodes": a.nodes})
    s = generate(a.games, cfg, a.prefix,
                 ["dragapult", "iono", "mega_abomasnow", "mega_lucario"])
    print(json.dumps({k: s[k] for k in
                      ("games", "decisions", "trusted_decisions", "trusted_fraction",
                       "games_completed", "invalid_actions", "split_counts")},
                     indent=2, default=str))
    print(json.dumps(s["real_search_counters"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
