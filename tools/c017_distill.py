"""c017 Block C (§20-§22) — compact shared policy/value model, supervised search distillation.

Reuses the project's existing valid code rather than writing a new architecture: `TorchPolicy`
from c011 (the CUDA port of ModelV2, with a shared trunk feeding both an action head and a value
head) and `cg.policy_features` for featurisation. §7 allows reuse of existing project code and
forbids building new frameworks.

Two targets, one shared trunk (§20):
  * POLICY — cross-entropy against the search teacher's `label_action` over the legal mask;
  * VALUE  — regression against the game's ACTUAL final outcome, not a bootstrapped estimate.

Trajectories are split by GAME upstream, so no game straddles train/validation/test and imitation
agreement is measured on games the model never trained on.

Honest scope: probe P10 established that forward simulation is impossible in this simulator, so
the teacher is a depth-0 heuristic ranker. This model therefore distils a *ranking heuristic*,
not lookahead, and every artifact it produces carries that taint.
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
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C17 = os.path.join(_REPO, "contracts", "c017_end_to_end_search_learning_curriculum_campaign",
                   "results")
MODELS = os.path.join(C17, "models")
TRAJ = os.path.join(C17, "trajectories")
PROBES = os.path.join(C17, "probes")

MODEL_VERSION = "c017.policyvalue.v1"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def load_features(prefix: str) -> Dict[str, Any]:
    """Feature arrays are written by the trajectory generator as an NPZ sidecar."""
    p = os.path.join(TRAJ, f"{prefix}_features.npz")
    if not os.path.exists(p):
        return {}
    z = np.load(p, allow_pickle=True)
    return {k: z[k] for k in z.files}


def train(prefix: str, epochs: int, device: str = "cuda") -> Dict[str, Any]:
    import torch
    import torch.nn.functional as F
    import c011_torch_model as tm

    feats = load_features(prefix)
    if not feats:
        return {"status": "NOT_EXERCISED", "reason": "no feature sidecar found",
                "trust_status": "NON_SUBMITTABLE"}

    rows = [json.loads(l) for l in
            gzip.open(os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz"), "rt")]
    idx_by_split = collections.defaultdict(list)
    for i, r in enumerate(rows):
        idx_by_split[r["split"]].append(i)

    dev = device if torch.cuda.is_available() else "cpu"
    tm.enable_determinism(threads=1)
    model = tm.TorchPolicy(dtype=torch.float32, device=dev)
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-5)

    LONG = {"board_rows", "hand_rows", "disc_rows", "opt_rows"}
    T = {k: torch.tensor(np.asarray(v),
                         dtype=(torch.long if k in LONG else torch.float32), device=dev)
         for k, v in feats.items()
         if k not in ("n_options", "label_index", "final_outcome")}
    nopt = torch.tensor(feats["n_options"], dtype=torch.long, device=dev)
    label = torch.tensor(feats["label_index"], dtype=torch.long, device=dev)
    value = torch.tensor(feats["final_outcome"], dtype=torch.float32, device=dev)

    K = T["opt_dense"].shape[1]
    ar = torch.arange(K, device=dev)[None, :]
    mask = (ar < nopt[:, None]).float()
    # the model pools over options with an explicit mask; padding is inert only because of it
    T["opt_mask"] = mask

    hist = []
    t0 = time.time()
    for ep in range(epochs):
        model.train()
        tr = idx_by_split["train"]
        if not tr:
            break
        perm = np.random.default_rng(1700 + ep).permutation(len(tr))
        bs = 256
        tot_p = tot_v = nb = 0
        for s in range(0, len(perm), bs):
            sel = [tr[i] for i in perm[s:s + bs]]
            if not sel:
                continue
            ii = torch.tensor(sel, dtype=torch.long, device=dev)
            scores, val = _forward_compat(model, {k: v[ii] for k, v in T.items()})
            m = mask[ii]
            logits = scores.masked_fill(m == 0, -1e9)
            p_loss = F.cross_entropy(logits, label[ii])
            v_loss = F.mse_loss(val.reshape(-1), value[ii])
            loss = p_loss + 0.5 * v_loss
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            tot_p += float(p_loss)
            tot_v += float(v_loss)
            nb += 1
        ev = evaluate_split(model, idx_by_split["validation"], T, mask, label, value, dev)
        hist.append({"epoch": ep + 1, "train_policy_loss": round(tot_p / max(1, nb), 5),
                     "train_value_loss": round(tot_v / max(1, nb), 5), **ev})
        print(f"[distill] epoch {ep+1}/{epochs} pl={hist[-1]['train_policy_loss']} "
              f"vl={hist[-1]['train_value_loss']} val_top1={ev['top1_agreement']} "
              f"{time.time()-t0:.0f}s", flush=True)

    test = evaluate_split(model, idx_by_split["test"], T, mask, label, value, dev)
    os.makedirs(MODELS, exist_ok=True)
    ckpt = os.path.join(MODELS, "c017_policy_value.pt")
    torch.save({"state_dict": model.state_dict(), "cfg": dict(model.cfg),
                "model_version": MODEL_VERSION}, ckpt)

    # baseline-agreement reference: how often the TEACHER label equals the baseline action.
    # A model that merely reproduces the baseline is not evidence of distillation.
    base_agree = sum(1 for r in rows if not r["label_differs_from_baseline"]) / max(1, len(rows))
    doc = {
        "status": "PASS", "model_version": MODEL_VERSION, "device": dev,
        "epochs": epochs, "history": hist, "test": test,
        "n_train": len(idx_by_split["train"]), "n_validation": len(idx_by_split["validation"]),
        "n_test": len(idx_by_split["test"]),
        "checkpoint": os.path.relpath(ckpt, _REPO), "checkpoint_sha256": sha_file(ckpt),
        "teacher_equals_baseline_rate": round(base_agree, 4),
        "interpretation": "top-1 agreement must be read against teacher_equals_baseline_rate: "
                          "a model that only reproduces the baseline would score close to it "
                          "without having learned anything from the ranker",
        "trust_status": "TAINTED",
        "tainted_by": ["P10_forward_simulation"],
        "taint_reason": "the teacher is a depth-0 heuristic ranker, not lookahead; no claim "
                        "about search depth is supported",
    }
    json.dump(doc, open(os.path.join(MODELS, "distillation_report.json"), "w"), indent=2,
              default=str)
    return doc


def _forward_compat(model, b):
    """TorchPolicy exposes forward(batch_dict); adapt without modifying c011 code."""
    # TorchPolicy.forward returns (scores, value, ctx): the value head is already applied
    # inside forward, so the shared trunk serves both heads in a single pass.
    scores, value, _ctx = model(b)
    return scores, value


def evaluate_split(model, idx, T, mask, label, value, dev):
    import torch
    if not idx:
        return {"n": 0, "top1_agreement": None, "value_mae": None,
                "status": "NOT_OBSERVED"}
    model.eval()
    hits = 0
    vabs = 0.0
    with torch.no_grad():
        bs = 512
        for s in range(0, len(idx), bs):
            sel = idx[s:s + bs]
            ii = torch.tensor(sel, dtype=torch.long, device=dev)
            scores, val = _forward_compat(model, {k: v[ii] for k, v in T.items()})
            logits = scores.masked_fill(mask[ii] == 0, -1e9)
            pred = logits.argmax(dim=-1)
            hits += int((pred == label[ii]).sum())
            vabs += float((val.reshape(-1) - value[ii]).abs().sum())
    return {"n": len(idx), "top1_agreement": round(hits / len(idx), 4),
            "value_mae": round(vabs / len(idx), 4)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="scaled")
    ap.add_argument("--epochs", type=int, default=3)
    a = ap.parse_args(argv)
    os.makedirs(PROBES, exist_ok=True)
    doc = train(a.prefix, a.epochs)
    pd = os.path.join(PROBES, "P20_distillation")
    os.makedirs(pd, exist_ok=True)
    json.dump({"probe_id": "P20_distillation", "status": doc.get("status"),
               "trust_status": doc.get("trust_status"),
               "tainted_by": doc.get("tainted_by", []),
               "summary": {k: doc.get(k) for k in
                           ("device", "epochs", "n_train", "n_test", "test",
                            "teacher_equals_baseline_rate")}},
              open(os.path.join(pd, "probe.json"), "w"), indent=2, default=str)
    print(json.dumps({k: doc.get(k) for k in
                      ("status", "device", "n_train", "n_test", "test",
                       "teacher_equals_baseline_rate", "trust_status")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
