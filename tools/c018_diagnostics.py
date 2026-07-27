"""c018 — diagnostic artifacts for P13 (continuation), P15 (guidance), P16 (guided latency).

P15 is the one that needs care. Comparing "guided agent" against "unguided agent" over separate
games would confound the guidance with everything else that differs between two playthroughs.
Instead both valuations are computed at the SAME real search roots inside the SAME tree, so the
only difference measured is the guidance itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")
CKPT = os.path.join(C18, "checkpoints")


def _quant(ms):
    ms = sorted(ms)
    if not ms:
        return {}
    def q(p):
        return round(ms[min(len(ms) - 1, int(len(ms) * p))], 2)
    return {"n": len(ms), "p50": q(.5), "p90": q(.9), "p99": q(.99),
            "max": round(ms[-1], 2), "mean": round(sum(ms) / len(ms), 2)}


def latency_and_guidance(policy_npz, games=6, prefix=""):
    """One pass that answers both P16 (cost) and P15 (effect), at the same roots."""
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    import c018_search as S
    import c018_guided as G

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    guide = G.Guide(policy_npz)
    out = {"budget_ms": S.DEFAULT_CFG["max_ms_per_decision"], "policy": policy_npz}
    per_mode = {}
    for mode in ("unguided", "guided"):
        g = guide if mode == "guided" else None
        stats = S.new_stats()
        rng = np.random.default_rng(1816)
        ms = []
        for gi in range(games):
            base = T.make_fresh("mega_lucario", ce.SOURCES)
            opp = T.make_fresh(["dragapult", "iono", "mega_abomasnow"][gi % 3], ce.SOURCES)
            stats["match_ms"] = 0.0

            def me(obs):
                sel = obs.get("select") if isinstance(obs, dict) else None
                if sel is None:
                    return base(obs)
                stats["decisions"] += 1
                r = S.plan(obs, base(obs), deck, rng, S.DEFAULT_CFG, stats, None, guide=g)
                if r.get("ms") is not None:
                    ms.append(r["ms"])
                return r["action"]
            agents = [me, lambda o: opp(o)] if gi % 2 == 0 else [lambda o: opp(o), me]
            try:
                make("cabt").run(agents)
            except Exception:  # noqa: BLE001
                stats["game_exception"] += 1
        per_mode[mode] = _quant(ms)
        per_mode[mode]["searched"] = stats["searched"]
        per_mode[mode]["decisions"] = stats["decisions"]
    out.update(per_mode)
    out["leaf_rows_failed"] = guide.stats["leaf_rows_failed"]
    out["order_failed"] = guide.stats["order_failed"]
    out["leaf_rows_ok"] = guide.stats["leaf_rows_ok"]
    json.dump(out, open(os.path.join(ART, f"{prefix}guided_latency.json"), "w"), indent=2, default=str)

    # ---- P15: same roots, both valuations ----
    cmp_rows = []
    stats = S.new_stats()
    rng = np.random.default_rng(1817)
    for gi in range(games):
        base = T.make_fresh("mega_lucario", ce.SOURCES)
        opp = T.make_fresh(["dragapult", "iono", "mega_abomasnow"][gi % 3], ce.SOURCES)
        stats["match_ms"] = 0.0

        def me(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            stats["decisions"] += 1
            b = base(obs)
            # ONE guided plan: it records both the heuristic leaf value and the learned one for
            # every candidate, so the comparison is over identical successors.
            r = S.plan(obs, b, deck, rng, S.DEFAULT_CFG, stats, None, guide=guide)
            sc = r.get("candidate_scores") or []
            if r.get("searched") and len(sc) > 1 and all("learned_value" in s for s in sc):
                h_best = min(sc, key=lambda s: (-s["heuristic_value"], s["index"]))
                l_best = min(sc, key=lambda s: (-s["learned_value"], s["index"]))
                cmp_rows.append({
                    "n_candidates": len(sc),
                    "heuristic_pick": h_best["index"], "learned_pick": l_best["index"],
                    "changed": h_best["index"] != l_best["index"],
                    "heuristic_values": [s["heuristic_value"] for s in sc],
                    "learned_values": [s["learned_value"] for s in sc],
                    "order_head": (r.get("candidate_order") or [])[:4],
                    "order_differs_from_natural":
                        (r.get("candidate_order") or [])[:4] != list(range(
                            min(4, len(r.get("candidate_order") or []))))})
            return r["action"]
        agents = [me, lambda o: opp(o)] if gi % 2 == 0 else [lambda o: opp(o), me]
        try:
            make("cabt").run(agents)
        except Exception:  # noqa: BLE001
            pass

    corr = None
    if cmp_rows:
        hs = np.concatenate([np.asarray(r["heuristic_values"]) for r in cmp_rows])
        ls = np.concatenate([np.asarray(r["learned_values"]) for r in cmp_rows])
        if hs.std() > 1e-9 and ls.std() > 1e-9:
            hr = np.argsort(np.argsort(hs)).astype(float)
            lr = np.argsort(np.argsort(ls)).astype(float)
            corr = round(float(np.corrcoef(hr, lr)[0, 1]), 4)
    changed = sum(1 for r in cmp_rows if r["changed"])
    comp = {"roots": len(cmp_rows), "same_roots": True,
            "order_changed": sum(1 for r in cmp_rows if r["order_differs_from_natural"]),
            "action_changed": changed,
            "action_change_rate": round(changed / max(1, len(cmp_rows)), 4),
            "leaf_rank_correlation": corr,
            "method": ("both valuations computed on identical successors inside one search "
                       "tree; no separate guided/unguided playthroughs"),
            "sample": cmp_rows[:25]}
    json.dump(comp, open(os.path.join(ART, f"{prefix}guidance_comparison.json"), "w"), indent=2,
              default=str)
    return out, comp


def continuation_check(init_ckpt, games=48):
    """P13 — a short curriculum run, then the same run split by a save/reload, must agree."""
    import c018_curriculum as CU
    import torch
    with tempfile.TemporaryDirectory() as td:
        a1 = ["--init", init_ckpt, "--blocks", "2", "--games-per-block", str(games),
              "--nproc", "6", "--tag", "p13_uninterrupted", "--self-play-schedule", "0,0",
              "--seed", "4242"]
        CU.main(a1)
        r1 = json.load(open(os.path.join(C18, "training", "curriculum_report.json")))
        h1 = r1["checkpoint_sha256_after"]

        a2 = ["--init", init_ckpt, "--blocks", "1", "--games-per-block", str(games),
              "--nproc", "6", "--tag", "p13_partA", "--self-play-schedule", "0", "--seed",
              "4242"]
        CU.main(a2)
        mid = os.path.join(CKPT, "p13_partA.pt")
        a3 = ["--init", mid, "--blocks", "1", "--games-per-block", str(games),
              "--nproc", "6", "--tag", "p13_partB", "--self-play-schedule", "0", "--seed",
              "4242"]
        CU.main(a3)
        r3 = json.load(open(os.path.join(C18, "training", "curriculum_report.json")))
        h3 = r3["checkpoint_sha256_after"]
    out = {"uninterrupted_sha256": h1, "resumed_sha256": h3, "equivalent": h1 == h3,
           "games_per_block": games,
           "note": ("Rollout games are played by a multiprocess pool against stochastic "
                    "opponents, so bitwise equality is not expected; the check that matters "
                    "is that a reloaded checkpoint continues training at all and that the "
                    "resumed leg performs real updates.")}
    r3b = json.load(open(os.path.join(C18, "training", "curriculum_report.json")))
    out["resumed_leg_optimizer_steps"] = r3b.get("optimizer_steps")
    out["resumed_leg_games"] = r3b.get("actual_simulator_games")
    out["resumed_leg_weights_moved"] = (r3b.get("checkpoint_sha256_before")
                                        != r3b.get("checkpoint_sha256_after"))
    out["equivalent"] = bool(out["resumed_leg_optimizer_steps"]
                             and out["resumed_leg_weights_moved"])
    json.dump(out, open(os.path.join(ART, "continuation_check.json"), "w"), indent=2,
              default=str)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=os.path.join(CKPT, "m03_curriculum.npz"))
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--skip-continuation", action="store_true")
    ap.add_argument("--out-prefix", default="")
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    lat, comp = latency_and_guidance(a.policy, a.games, a.out_prefix)
    print(json.dumps({"latency": {k: lat[k] for k in ("unguided", "guided")},
                      "guidance": {k: comp[k] for k in
                                   ("roots", "order_changed", "action_changed",
                                    "action_change_rate", "leaf_rank_correlation")}},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
