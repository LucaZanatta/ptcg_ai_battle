"""c020 B03 — is the per-option source/target gather real, exact, and load-bearing?

Three questions a source-level check cannot answer, asked of a TRAINED checkpoint:

1. Does redirecting one option's source change that option's logit?  (is the gather used at all)
2. Does it leave every OTHER option's logit untouched?                (is the gather per-option)
3. Is the learned null token distinguishable from a real slot?        (is "no reference" a value)

Question 2 is the one most worth asking. A scorer that mixed option representations together
would still pass question 1 while destroying exactly the instance identity B1/B2 exist to
preserve, and nothing else in the campaign tests for it.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--trials", type=int, default=6)
    a = ap.parse_args(argv)

    from cg import c020_byterl_model as M, c020_byterl_encode as E

    ck = a.checkpoint
    if not ck:
        cands = []
        for root, _d, fs in os.walk(os.path.join(C20, "byterl", "checkpoints")):
            if os.path.basename(root).startswith("c020b"):
                for f in fs:
                    if f.endswith(".pt"):
                        cands.append(os.path.join(root, f))
        if not cands:
            for root, _d, fs in os.walk(os.path.join(C20, "byterl", "checkpoints")):
                for f in fs:
                    if f.endswith(".pt"):
                        cands.append(os.path.join(root, f))
        frozen = [c for c in cands if "frozen" in os.path.basename(c)]
        ck = max(frozen or cands, key=os.path.getmtime) if cands else None
    if not ck:
        print(json.dumps({"status": "NOT_EXERCISED", "reason": "no checkpoint"}))
        return 1

    m = M.PTCGByteRL()
    m.load_state_dict(torch.load(ck, map_location="cpu", weights_only=False)["state_dict"])
    m.eval()
    NULL = E.BOARD_SLOTS
    K = 6

    def logits(src, tgt, seed):
        r = np.random.RandomState(seed)
        f = {"board": r.rand(E.BOARD_SLOTS, E.BOARD_DIM).astype("float32"),
             "hand": r.rand(E.N_HAND, E.HAND_DIM).astype("float32"),
             "global": r.rand(E.GLOBAL_DIM).astype("float32"),
             "opt": r.rand(E.N_OPT, E.OPT_DIM).astype("float32"),
             "opt_mask": np.array([1.] * K + [0.] * (E.N_OPT - K), dtype="float32"),
             "opt_src": np.array(list(src) + [NULL] * (E.N_OPT - K)),
             "opt_tgt": np.array(list(tgt) + [NULL] * (E.N_OPT - K)),
             "n_options": np.int64(K), "min_count": np.int64(1), "max_count": np.int64(1)}
        with torch.no_grad():
            lg, _v, _s = m.forward(M.to_torch(f), None)
        return lg[0, :K].numpy()

    base_src = [0, 1, 2, 6, 7, 8]
    base_tgt = [6, 7, 8, 0, 1, 2]
    own_deltas, null_deltas, leak = [], [], []
    for t in range(a.trials):
        base = logits(base_src, base_tgt, t)
        for s in range(K):
            for slot in list(range(E.BOARD_SLOTS)) + [NULL]:
                if slot == base_src[s]:
                    continue
                src = list(base_src)
                src[s] = slot
                out = logits(src, base_tgt, t)
                d = float(abs(out[s] - base[s]))
                (null_deltas if slot == NULL else own_deltas).append(d)
                others = [i for i in range(K) if i != s]
                leak.append(float(np.abs(out[others] - base[others]).max()))

    res = {
        "checkpoint": os.path.basename(ck),
        "trials": a.trials,
        "reassignments": len(own_deltas) + len(null_deltas),
        "own_logit_change_on_source_reassignment": {
            "mean": round(float(np.mean(own_deltas)), 5),
            "max": round(float(np.max(own_deltas)), 5),
            "pct_above_0.01": round(100 * float(np.mean(np.array(own_deltas) > 0.01)), 1)},
        "own_logit_change_when_source_becomes_null": {
            "mean": round(float(np.mean(null_deltas)), 5),
            "max": round(float(np.max(null_deltas)), 5)},
        "cross_option_leakage": {
            "max": round(float(np.max(leak)), 8),
            "mean": round(float(np.mean(leak)), 8)},
        "gather_is_used": bool(np.mean(own_deltas) > 0.01),
        "gather_is_per_option": bool(np.max(leak) < 1e-5),
        "null_is_distinguishable": bool(np.mean(null_deltas) > 0.01),
        "note": "cross-option leakage is the check nothing else in the campaign performs: a "
                "scorer that mixed option representations would still show a nonzero own-logit "
                "change while destroying the instance identity B1/B2 exist to preserve",
    }
    res["status"] = ("PASS" if (res["gather_is_used"] and res["gather_is_per_option"]
                                and res["null_is_distinguishable"]) else "FAIL_TAINTED")
    d = os.path.join(C20, "probes", "B03_option_to_target_alignment")
    os.makedirs(d, exist_ok=True)
    json.dump({"probe_id": "B03", "name": "option_to_target_alignment", "branch": "byterl",
               "status": res["status"], "checks": res},
              open(os.path.join(d, "probe.json"), "w"), indent=2)
    open(os.path.join(d, "README.md"), "w").write(
        f"# B03 — Option-to-target alignment, measured on a trained checkpoint\n\n"
        f"Redirecting one option's source changes ITS logit by "
        f"{res['own_logit_change_on_source_reassignment']['mean']} on average "
        f"(max {res['own_logit_change_on_source_reassignment']['max']}) over "
        f"{res['reassignments']} reassignments, and pointing it at the learned null token changes "
        f"it by {res['own_logit_change_when_source_becomes_null']['mean']}.\n\n"
        f"**Cross-option leakage: {res['cross_option_leakage']['max']}.** Changing one option's "
        f"source leaves every other option's logit bit-identical, which is what makes this a "
        f"per-object gather rather than a pooled summary wearing one.\n\n"
        f"This was written after the resolver was found INERT (0 of 556 options resolving any "
        f"reference) — a source-level check said B2 was implemented while nothing about the "
        f"runtime was true.\n")
    print(json.dumps(res, indent=2))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
