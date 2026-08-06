"""c018 — M02 -> RLPolicy export round-trip verification (blocking gate for M03).

`RLPolicy.load_state` silently drops any key it does not already hold:

    if k.startswith("trunk::") and k[7:] in self.trunk.p:   # else: dropped, no error

So an export whose key names drift by one character loads "successfully" while leaving that
tensor at its random initialisation. PPO would then show falling loss and rising win rate purely
by re-learning what the export threw away -- a training claim that satisfies every optimizer-step
and changed-hash check and still means nothing. c013 lost a gate to exactly this shape of silent
allow-list drop.

This asserts key-set EQUALITY (not merely "load didn't raise"), config round-trip, and numerical
agreement of scores and value on a fixed real batch in float64.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
LONG = {"board_rows", "hand_rows", "disc_rows", "opt_rows"}


def main():
    import c011_torch_model as tm
    from cg.rl_policy import RLPolicy

    ck = os.path.join(C18, "checkpoints", "m02_distilled.pt")
    blob = torch.load(ck, map_location="cpu")
    # float64 so the comparison measures export fidelity, not FP32 rounding
    model = tm.TorchPolicy(dtype=torch.float64, device="cpu")
    model.load_state_dict({k: v.double() for k, v in blob["state_dict"].items()})
    model.eval()

    sd = model.export_legacy_state()
    pol = RLPolicy(model.cfg, seed=0)
    expected = ({f"trunk::{k}" for k in pol.trunk.p} | {f"pv::{k}" for k in pol.pv})
    got = set(sd)
    missing, extra = expected - got, got - expected
    pol.load_state(sd)

    res = {"exported_keys": len(got), "policy_keys": len(expected),
           "keys_missing_from_export": sorted(missing),
           "keys_export_would_drop": sorted(extra),
           "key_sets_equal": not missing and not extra}

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "rt.npz")
        pol.save(p)                       # .save() writes __meta__, which .load() requires
        pol2 = RLPolicy.load(p)
        res["cfg_round_trip"] = all(int(pol2.trunk.cfg[k]) == int(model.cfg[k])
                                    for k in pol.trunk.cfg)
        sd2 = pol2.state_dict()
        res["reload_tensors_bitwise_equal"] = all(
            np.array_equal(sd2[k], sd[k]) for k in expected)

    # numerical agreement on a real batch
    npz = np.load(os.path.join(C18, "trajectories", "scaled_features.npz"))
    n = 64
    b = {k: npz[k][:n] for k in ("global", "board_rows", "board_dyn", "hand_rows", "hand_dyn",
                                 "hand_mask", "disc_rows", "disc_mask", "opt_dense", "opt_rows")}
    K = b["opt_dense"].shape[1]
    b["opt_mask"] = (np.arange(K)[None, :] < npz["n_options"][:n, None]).astype(np.float64)
    tb = {k: torch.tensor(v, dtype=(torch.long if k in LONG else torch.float64))
          for k, v in b.items()}
    with torch.no_grad():
        ts, tv, _ = model(tb)
    ns_n, nv_n, _ = pol.forward({k: np.asarray(v) for k, v in b.items()})
    ns = np.asarray(ns_n.data if hasattr(ns_n, "data") else ns_n)
    nv = np.asarray(nv_n.data if hasattr(nv_n, "data") else nv_n)
    m = b["opt_mask"] > 0
    res["max_abs_score_diff"] = float(np.abs(ts.numpy() - ns.reshape(ts.shape))[m].max())
    res["max_abs_value_diff"] = float(np.abs(tv.numpy() - nv.reshape(-1)).max())
    res["numerically_equivalent"] = (res["max_abs_score_diff"] < 1e-8
                                     and res["max_abs_value_diff"] < 1e-8)
    res["passed"] = bool(res["key_sets_equal"] and res["cfg_round_trip"]
                         and res["reload_tensors_bitwise_equal"]
                         and res["numerically_equivalent"])
    os.makedirs(os.path.join(C18, "artifacts"), exist_ok=True)
    json.dump(res, open(os.path.join(C18, "artifacts", "export_round_trip.json"), "w"),
              indent=2, default=str)
    print(json.dumps(res, indent=2, default=str))
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
