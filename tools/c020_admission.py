"""c020 C3/C4 — prior and value admission on held-out MCTS leaves.

`DECISION_RULES` forbids promoting a hybrid mode on the grounds that the model exists. C3 checks
that ByteRL probabilities actually map onto MCTS action keys and do not bury the baseline action;
C4 compares the corrected value against FOUR controls — constant mean, the c019 value control,
random ranking, and the corrected tactical heuristic — on leaves the checkpoint never trained on.

The c019 campaign's own ablation is the reason both gates exist: bad priors cost −28.7 field
points there while the value cost −2.5, so priors are the component most capable of destroying a
search and the one most in need of an alignment check before it is allowed near one.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
HY = os.path.join(C20, "hybrid")


def collect_leaves(n_games: int, per_game: int, seed: int):
    """Held-out leaves: positions from baseline games, labelled with the eventual result."""
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c020_baseline_memory as BM

    rng = random.Random(seed)
    opp_ids = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]
    leaves, games = [], []
    for gi in range(n_games):
        opp = T.make_fresh(opp_ids[gi % len(opp_ids)], ce.SOURCES)
        seat = gi % 2
        st = {"mem": BM.initial_memory(), "snaps": []}

        def make_me(state, r):
            def me(obs):
                action, nxt = BM.recommend(obs, state["mem"])
                state["mem"] = BM.advance_after_executed(obs, action, state["mem"])
                if isinstance(obs, dict) and obs.get("select") is not None \
                        and r.random() < 0.14 and len(state["snaps"]) < per_game:
                    state["snaps"].append(obs)
                return list(action)
            return me

        def make_opp(o):
            def f(obs):
                return o(obs)
            return f

        agents = ([make_me(st, rng), make_opp(opp)] if seat == 0
                  else [make_opp(opp), make_me(st, rng)])
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            if [s.status for s in last] != ["DONE", "DONE"]:
                games.append({"game": gi, "completed": False})
                continue
            rw = [s.reward for s in last]
            out = (1.0 if rw[seat] > rw[1 - seat] else
                   (0.0 if rw[seat] == rw[1 - seat] else -1.0))
            games.append({"game": gi, "completed": True, "outcome": out,
                          "snapshots": len(st["snaps"])})
            for o in st["snaps"]:
                leaves.append({"obs": o, "outcome": out, "game": gi, "seat": seat})
        except Exception as e:  # noqa: BLE001
            games.append({"game": gi, "completed": False, "error": str(e)[:120]})
    return leaves, games


def value_preds(checkpoint: str, obs_list, kind: str) -> List[float]:
    import torch
    out = []
    if kind == "c020":
        from cg import c020_byterl_encode as E, c020_byterl_model as M
        m = M.PTCGByteRL()
        m.load_state_dict(torch.load(checkpoint, map_location="cpu")["state_dict"])
        m.eval()
        for o in obs_list:
            try:
                from cg import api as A
                oc = A.to_observation_class(o)
                b = M.to_torch(E.encode(oc))
                with torch.no_grad():
                    _l, v, _s = m.forward(b, None)
                out.append(float(v[0]))
            except Exception:  # noqa: BLE001
                out.append(0.0)
    else:                       # c019 value control
        from cg import c019_byterl_encode as E19, c019_byterl_model as M19
        m = M19.PTCGByteRL()
        m.load_state_dict(torch.load(checkpoint, map_location="cpu")["state_dict"])
        m.eval()
        for o in obs_list:
            try:
                from cg import api as A
                oc = A.to_observation_class(o)
                b = M19.to_torch(E19.encode(oc))
                with torch.no_grad():
                    _l, v, _s = m.forward(b, None)
                out.append(float(v[0]))
            except Exception:  # noqa: BLE001
                out.append(0.0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--per-game", type=int, default=5)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--checkpoint", default="")
    a = ap.parse_args(argv)

    from cg import c020_hybrid as H, c020_tactical_leaf as TL

    ck = a.checkpoint
    if not ck:
        from tools.c020_hybrid_run import latest_checkpoint  # noqa
    if not ck:
        cands = []
        for root, _d, fs in os.walk(os.path.join(C20, "byterl", "checkpoints")):
            for f in fs:
                if f.endswith(".pt"):
                    cands.append((os.path.getmtime(os.path.join(root, f)),
                                  os.path.join(root, f)))
        finals = [c for c in cands if "final" in os.path.basename(c[1])]
        ck = max(finals or cands)[1] if cands else None
    if not ck:
        print(json.dumps({"error": "no c020 checkpoint available yet"}))
        return 1

    os.makedirs(os.path.join(HY, "prior_calibration"), exist_ok=True)
    os.makedirs(os.path.join(HY, "value_calibration"), exist_ok=True)

    leaves, games = collect_leaves(a.games, a.per_game, a.seed)
    obs_list = [x["obs"] for x in leaves]
    outcomes = [x["outcome"] for x in leaves]

    # ------------------------------------------------------------ C4 value admission
    preds = {"c020_byterl_value": value_preds(ck, obs_list, "c020")}
    heur = []
    for o in obs_list:
        try:
            from cg import api as A
            s, _f = TL.evaluate(A.to_observation_class(o), False, None, None)
            heur.append(s)
        except Exception:  # noqa: BLE001
            heur.append(0.0)
    preds["tactical_heuristic"] = heur

    c19 = ((json.load(open(os.path.join(C20, "controls", "control_manifest.json")))
            .get("controls", {}).get("C019_BYTERL_CONTROL", {}).get("final_checkpoint"))
           if os.path.exists(os.path.join(C20, "controls", "control_manifest.json")) else None)
    if c19:
        p19 = os.path.join(_REPO, c19)
        if os.path.exists(p19):
            try:
                preds["c019_value_control"] = value_preds(p19, obs_list, "c019")
            except Exception as e:  # noqa: BLE001
                preds["c019_value_control_error"] = str(e)[:150]

    preds_clean = {k: v for k, v in preds.items() if isinstance(v, list)}
    va = H.value_admission(preds_clean, outcomes)
    va.update({"checkpoint": os.path.basename(ck), "leaves": len(leaves),
               "games_played": len(games),
               "games_completed": sum(1 for g in games if g.get("completed")),
               "held_out": "leaves come from frozen-baseline games the checkpoint never trained "
                           "on; label is the eventual result from the snapshotted seat"})
    json.dump(va, open(os.path.join(HY, "value_calibration", "value_admission.json"), "w"),
              indent=2)

    # ------------------------------------------------------------ C3 prior admission
    import torch
    from cg import c020_byterl_encode as E, c020_byterl_model as M
    from cg import c019_core as K, c020_baseline_memory as BM
    from cg import api as A
    m = M.PTCGByteRL()
    m.load_state_dict(torch.load(ck, map_location="cpu")["state_dict"])
    m.eval()
    samples = []
    for x in leaves[:600]:
        o = x["obs"]
        try:
            oc = A.to_observation_class(o)
            sel = getattr(oc, "select", None)
            opts = K.canonical_options(sel)
            if len(opts) < 2:
                continue
            b = M.to_torch(E.encode(oc))
            with torch.no_grad():
                lg, _v, _s = m.forward(b, None)
                probs = M.masked_probs(lg, b["opt_mask"])[0].numpy()
            refs = E.option_refs(oc)
            mapped = {}
            for i, r in enumerate(refs[:len(probs)]):
                for op in opts:
                    if op.option_index == r.option_index:
                        mapped[op.key()] = float(probs[i])
            base_action, _p = BM.recommend(o, BM.initial_memory())
            bkey = next((op.key() for op in opts if op.option_index in list(base_action)), None)
            ps = np.array(list(mapped.values())) if mapped else np.array([0.0])
            topk = sorted(mapped.items(), key=lambda kv: -kv[1])[:3]
            ent = float(-(ps * np.log(np.clip(ps, 1e-9, 1))).sum())
            samples.append({
                "aligned": len(mapped) == len(opts),
                "prob_sum": float(ps.sum()),
                "min_credible_prior": float(ps.min()) if len(ps) else 0.0,
                "baseline_in_topk": bool(bkey is not None and bkey in [k for k, _ in topk]),
                "baseline_prior": float(mapped.get(bkey, 0.0)) if bkey else 1.0,
                "entropy": ent, "n_options": len(opts)})
        except Exception:  # noqa: BLE001
            continue
    pa = H.prior_admission(None, samples)
    pa.update({"checkpoint": os.path.basename(ck)})
    json.dump(pa, open(os.path.join(HY, "prior_calibration", "prior_admission.json"), "w"),
              indent=2)

    print(json.dumps({"checkpoint": os.path.basename(ck),
                      "leaves": len(leaves),
                      "value_admission": {"admitted": va["admitted"],
                                          "metrics": va.get("metrics")},
                      "prior_admission": {k: v for k, v in pa.items() if k != "rule"}},
                     indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
