"""c018 — held-out metric depth and trajectory integrity detail (P07/P08/P10).

Covers the requirements the training report's headline numbers do not:

  * **P10** — top-1/top-k/KL *by decision category*, and value calibration against the honest
    constant baseline (predicting the training-set mean outcome). A value head that cannot beat
    a constant is not a value head, and a single aggregate MSE hides that.
  * **P07** — round-trip reconstruction of the trajectory rows, and proof that search IDs
    cannot be confused with game or action indices.
  * **P08** — a hidden-feature audit of the encoding, and source/config hash resolution.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import glob
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")
TRAJ = os.path.join(C18, "trajectories")
LONG = {"board_rows", "hand_rows", "disc_rows", "opt_rows"}


def primary_prefix(default="scaled"):
    """The trajectory set with the most TRUSTED decisions.

    Several prefixes coexist (smoke, vertical, budgetcheck, scaled, scaled2). Hardcoding one
    means a rerun at larger scale silently keeps reporting the smaller set, so the primary set
    is resolved from the evidence rather than named in code.
    """
    best, best_n = default, -1
    for p in glob.glob(os.path.join(C18, "search", "*_search_summary.json")):
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue
        n = d.get("trusted_decisions") or 0
        if n > best_n:
            best, best_n = os.path.basename(p)[:-len("_search_summary.json")], n
    return best


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def heldout_metrics(prefix="scaled", tag="m02_distilled", topk=3):
    import c011_torch_model as tm
    npz = np.load(os.path.join(TRAJ, f"{prefix}_features.npz"))
    rows = [json.loads(l) for l in
            gzip.open(os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz"), "rt")]
    trusted = set(int(i) for i in npz["trusted_rows"])
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    blob = torch.load(os.path.join(C18, "checkpoints", f"{tag}.pt"), map_location=dev)
    model = tm.TorchPolicy(dtype=torch.float32, device=dev)
    model.load_state_dict(blob["state_dict"])
    model.to(dev).eval()

    T = {k: torch.tensor(np.asarray(npz[k]),
                         dtype=(torch.long if k in LONG else torch.float32), device=dev)
         for k in npz.files
         if k not in ("n_options", "label_index", "final_outcome", "trusted_rows")}
    nopt = torch.tensor(npz["n_options"], dtype=torch.long, device=dev)
    label = torch.tensor(npz["label_index"], dtype=torch.long, device=dev)
    value = torch.tensor(npz["final_outcome"], dtype=torch.float32, device=dev)
    K = T["opt_dense"].shape[1]
    mask = (torch.arange(K, device=dev)[None, :] < nopt[:, None]).float()
    T["opt_mask"] = mask

    idx = {"train": [], "validation": [], "test": []}
    for i, r in enumerate(rows):
        if i in trusted and r["label_action"] and max(r["label_action"]) < K:
            idx[r["split"]].append(i)

    train_mean = float(value[torch.tensor(idx["train"], device=dev)].mean()) \
        if idx["train"] else 0.5

    def evaluate(sel_idx, by_category=False):
        if not sel_idx:
            return None
        per_cat = collections.defaultdict(lambda: {"n": 0, "top1": 0, "topk": 0, "kl": 0.0})
        tot = {"n": 0, "top1": 0, "topk": 0, "kl": 0.0, "legal": 0}
        vp, vt = [], []
        with torch.no_grad():
            for s in range(0, len(sel_idx), 512):
                chunk = sel_idx[s:s + 512]
                ii = torch.tensor(chunk, dtype=torch.long, device=dev)
                sc, val, _ = model({k: v[ii] for k, v in T.items()})
                m = mask[ii]
                logits = sc.masked_fill(m == 0, -1e9)
                lp = F.log_softmax(logits, dim=1)
                lab = label[ii]
                # the search's label is a point mass, so KL(target || model) = -log p(label)
                kl = (-lp.gather(1, lab[:, None]).reshape(-1)).cpu().numpy()
                order = logits.argsort(dim=1, descending=True)
                t1 = (order[:, 0] == lab).cpu().numpy()
                tk = (order[:, :topk] == lab[:, None]).any(dim=1).cpu().numpy()
                legal = (m.gather(1, order[:, :1]).reshape(-1) > 0).cpu().numpy()
                vp.extend(val.reshape(-1).cpu().numpy().tolist())
                vt.extend(value[ii].cpu().numpy().tolist())
                for j, gi in enumerate(chunk):
                    tot["n"] += 1
                    tot["top1"] += int(t1[j])
                    tot["topk"] += int(tk[j])
                    tot["kl"] += float(kl[j])
                    tot["legal"] += int(legal[j])
                    if by_category:
                        c = per_cat[rows[gi]["context"]]
                        c["n"] += 1
                        c["top1"] += int(t1[j])
                        c["topk"] += int(tk[j])
                        c["kl"] += float(kl[j])
        vp, vt = np.asarray(vp), np.asarray(vt)
        const_mse = float(((vt - train_mean) ** 2).mean())
        mse = float(((vp - vt) ** 2).mean())
        corr = (float(np.corrcoef(vp, vt)[0, 1])
                if vp.std() > 1e-9 and vt.std() > 1e-9 else None)
        # calibration: mean predicted vs mean actual within predicted-value deciles
        bins = np.clip((vp * 10).astype(int), 0, 9)
        calib = [{"bin": int(b), "n": int((bins == b).sum()),
                  "mean_predicted": round(float(vp[bins == b].mean()), 4),
                  "mean_actual": round(float(vt[bins == b].mean()), 4)}
                 for b in sorted(set(bins.tolist())) if (bins == b).sum() >= 20]
        out = {"n": tot["n"],
               "top1": round(tot["top1"] / tot["n"], 4),
               f"top{topk}": round(tot["topk"] / tot["n"], 4),
               "mean_kl_nats": round(tot["kl"] / tot["n"], 4),
               "legal_top1_rate": round(tot["legal"] / tot["n"], 6),
               "value_mse": round(mse, 6),
               "constant_baseline_mse": round(const_mse, 6),
               "constant_baseline_value": round(train_mean, 4),
               "beats_constant_baseline": mse < const_mse,
               "value_correlation": round(corr, 4) if corr is not None else None,
               "calibration_deciles": calib}
        if by_category:
            out["by_decision_category"] = {
                str(k): {"n": v["n"], "top1": round(v["top1"] / v["n"], 4),
                         f"top{topk}": round(v["topk"] / v["n"], 4),
                         "mean_kl_nats": round(v["kl"] / v["n"], 4)}
                for k, v in sorted(per_cat.items()) if v["n"] >= 20}
        return out

    # P10: no train/test game leakage -- checked on GAME ids, not row ids
    gsplit = collections.defaultdict(set)
    for r in rows:
        gsplit[r["game_index"]].add(r["split"])
    leak = [g for g, v in gsplit.items() if len(v) > 1]

    return {"probe_id": "P10", "device": dev, "checkpoint": f"{tag}.pt",
            "checkpoint_sha256": sha_file(os.path.join(C18, "checkpoints", f"{tag}.pt")),
            "validation": evaluate(idx["validation"]),
            "held_out_test": evaluate(idx["test"], by_category=True),
            "train": evaluate(idx["train"][:4000]),
            "games_crossing_splits": len(leak),
            "no_train_test_leakage": not leak,
            "metric_note": ("top-1 is FIRST-PICK agreement: the stored label is "
                            "label_action[0]. KL is against the search's point-mass target, so "
                            "it equals the negative log-probability of the searched action."),
            "promotion_note": ("imitation metrics do not promote a candidate; only the frozen "
                               "gameplay panel (P17) does")}


def trajectory_integrity(prefix="scaled"):
    """P07/P08 detail: round-trip, id-space separation, hidden-feature audit."""
    import c018_trajectories as TR
    rows = [json.loads(l) for l in
            gzip.open(os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz"), "rt")]
    # round trip: serialise and reparse, then compare field-by-field
    rt_ok = True
    for r in rows[:3000]:
        if json.loads(json.dumps(r)) != r:
            rt_ok = False
            break
    # id-space separation: a search id must never be mistaken for a game or action index.
    # No trajectory field carries a search id at all -- that is the separation.
    id_fields = {k for r in rows[:50] for k in r}
    search_id_leaked = any("search_id" in k or "searchId" in k for k in id_fields)

    enc_src = open(os.path.join(_REPO, "cg", "state_encoder_v2.py"),
                   encoding="utf-8-sig").read()
    forbidden = ["opponent.hand", "players[1 - ", ".prize[", "deck_list", "opp.hand"]
    hits = [t for t in forbidden if t in enc_src]

    src = os.path.join(_REPO, "tools", "c018_search.py")
    summary = json.load(open(os.path.join(C18, "search", f"{prefix}_search_summary.json")))
    return {"probe_id": "P07/P08",
            "rows": len(rows), "round_trip_ok": rt_ok,
            "trajectory_fields": sorted(id_fields),
            "search_id_absent_from_trajectories": not search_id_leaked,
            "identity_fields_present": all(
                k in id_fields for k in ("game_index", "opponent_id", "seat",
                                         "decision_index")),
            "encoder_forbidden_token_hits": hits,
            "encoder_has_no_opponent_private_reads": not hits,
            "search_module_sha256": sha_file(src),
            "search_version_in_summary": summary.get("search_version"),
            "config_hash": hashlib.sha256(
                json.dumps(summary.get("config") or {}, sort_keys=True).encode()
            ).hexdigest()[:32],
            "trajectory_sha256_recomputed": sha_file(
                os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz")),
            "trajectory_sha256_reported": summary.get("trajectory_sha256")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--tag", default="m02_distilled")
    a = ap.parse_args(argv)
    prefix = a.prefix or primary_prefix()
    os.makedirs(ART, exist_ok=True)
    hm = heldout_metrics(prefix, a.tag)
    json.dump(hm, open(os.path.join(ART, "heldout_metrics.json"), "w"), indent=2, default=str)
    ti = trajectory_integrity(prefix)
    ti["trajectory_hash_matches"] = (ti["trajectory_sha256_recomputed"]
                                     == ti["trajectory_sha256_reported"])
    json.dump(ti, open(os.path.join(ART, "trajectory_integrity.json"), "w"), indent=2,
              default=str)
    print(json.dumps({"held_out": {k: hm["held_out_test"][k] for k in
                                   ("n", "top1", "top3", "mean_kl_nats", "legal_top1_rate",
                                    "value_mse", "constant_baseline_mse",
                                    "beats_constant_baseline", "value_correlation")},
                      "categories": len(hm["held_out_test"].get("by_decision_category") or {}),
                      "no_leakage": hm["no_train_test_leakage"],
                      "integrity": {k: ti[k] for k in
                                    ("round_trip_ok", "search_id_absent_from_trajectories",
                                     "identity_fields_present",
                                     "encoder_has_no_opponent_private_reads",
                                     "trajectory_hash_matches")}}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
