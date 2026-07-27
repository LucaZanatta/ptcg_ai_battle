"""c018 M02 — distil the trusted real-search policy into one compact shared policy/value model.

Trained ONLY on rows whose own search actually ran (`trusted`), on CUDA. c017's depth-zero
labels are not used and c017's distilled checkpoint is not continued: this initialises fresh so
that a changed checkpoint hash means *this* campaign's optimiser moved *these* weights.

Everything the P90 validator needs to disbelieve a training claim is recorded from the training
loop itself, not asserted afterwards: optimiser step count read off the optimiser, per-epoch
loss finiteness, and the checkpoint content hash before and after.
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
import torch
import torch.nn.functional as F

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
TRAJ = os.path.join(C18, "trajectories")
CKPT = os.path.join(C18, "checkpoints")
TRAIN = os.path.join(C18, "training")
LONG = {"board_rows", "hand_rows", "disc_rows", "opt_rows"}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_state(sd):
    """Content hash of the weights themselves.

    c012 cached `sha256_file` per path, so an overwritten checkpoint kept its old hash and
    'progress' was indistinguishable from a no-op. Hashing tensor bytes in sorted key order
    cannot be fooled that way.
    """
    h = hashlib.sha256()
    for k in sorted(sd):
        h.update(k.encode())
        h.update(np.ascontiguousarray(sd[k].detach().cpu().float().numpy()).tobytes())
    return h.hexdigest()


def load_data(prefix):
    npz = np.load(os.path.join(TRAJ, f"{prefix}_features.npz"))
    feats = {k: npz[k] for k in npz.files}
    rows = [json.loads(l) for l in
            gzip.open(os.path.join(TRAJ, f"{prefix}_trajectories.jsonl.gz"), "rt")]
    n = feats["global"].shape[0]
    if len(rows) != n:
        raise SystemExit(f"feature/trajectory misalignment: {n} feature rows vs {len(rows)} "
                         f"trajectory rows -- refusing to train on a guessed correspondence")
    trusted = set(int(i) for i in feats["trusted_rows"])
    # cross-check the npz index against the trajectory flag rather than trusting either alone
    flag = {i for i, r in enumerate(rows) if r.get("trusted")}
    return feats, rows, trusted, flag


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="scaled")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument("--tag", default="m02_distilled")
    a = ap.parse_args(argv)

    import c011_torch_model as tm

    os.makedirs(CKPT, exist_ok=True)
    os.makedirs(TRAIN, exist_ok=True)
    feats, rows, trusted_idx, trusted_flag = load_data(a.prefix)
    agree = trusted_idx == trusted_flag

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(1801)
    model = tm.TorchPolicy(dtype=torch.float32, device=dev)
    model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-5)

    T = {k: torch.tensor(np.asarray(v),
                         dtype=(torch.long if k in LONG else torch.float32), device=dev)
         for k, v in feats.items()
         if k not in ("n_options", "label_index", "final_outcome", "trusted_rows")}
    nopt = torch.tensor(feats["n_options"], dtype=torch.long, device=dev)
    label = torch.tensor(feats["label_index"], dtype=torch.long, device=dev)
    value = torch.tensor(feats["final_outcome"], dtype=torch.float32, device=dev)
    K = T["opt_dense"].shape[1]
    mask = (torch.arange(K, device=dev)[None, :] < nopt[:, None]).float()
    T["opt_mask"] = mask

    # TRUSTED ROWS ONLY -- an untrusted (fallback) row carries a baseline action, not a
    # search verdict; training on it would teach the heuristic back to itself.
    # Rows whose chosen option index exceeds K_MAX were stored with label 0 -- a WRONG target,
    # not merely a truncated one. Two of 12,245 in the scaled set; excluded rather than left as
    # disclosed label noise, because "small" is not the same as "harmless".
    KM = int(T["opt_dense"].shape[1])
    mislabeled = {i for i, r in enumerate(rows)
                  if r["label_action"] and max(r["label_action"]) >= KM}
    by_split = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if i in trusted_idx and i not in mislabeled:
            by_split[r["split"]].append(i)
    tr, va, te = by_split["train"], by_split["validation"], by_split["test"]
    if not tr:
        raise SystemExit("no trusted training rows")

    sd0 = {k: v for k, v in model.state_dict().items()}
    hash_before = sha_state(sd0)
    hashes = [hash_before]

    def evaluate(idx):
        if not idx:
            return None
        model.eval()
        tot_p = tot_v = corr = n = legal_ok = 0
        with torch.no_grad():
            for s in range(0, len(idx), 512):
                sel = torch.tensor(idx[s:s + 512], dtype=torch.long, device=dev)
                sc, val, _ = model({k: v[sel] for k, v in T.items()})
                m = mask[sel]
                logits = sc.masked_fill(m == 0, -1e9)
                tot_p += float(F.cross_entropy(logits, label[sel], reduction="sum"))
                tot_v += float(F.mse_loss(val.reshape(-1), value[sel], reduction="sum"))
                pred = logits.argmax(dim=1)
                corr += int((pred == label[sel]).sum())
                # a prediction outside the live option set would be an unplayable action
                legal_ok += int((m.gather(1, pred[:, None]).reshape(-1) > 0).sum())
                n += len(sel)
        return {"n": n, "policy_loss": round(tot_p / n, 6), "value_mse": round(tot_v / n, 6),
                "top1_agreement": round(corr / n, 4),
                "legal_prediction_rate": round(legal_ok / n, 6)}

    steps = 0
    hist = []
    all_finite = True
    t0 = time.time()
    best = (-1.0, None)
    for ep in range(a.epochs):
        model.train()
        perm = np.random.default_rng(1801 + ep).permutation(len(tr))
        ep_p = ep_v = nb = 0
        for s in range(0, len(perm), a.batch):
            sel = torch.tensor([tr[i] for i in perm[s:s + a.batch]],
                               dtype=torch.long, device=dev)
            sc, val, _ = model({k: v[sel] for k, v in T.items()})
            m = mask[sel]
            logits = sc.masked_fill(m == 0, -1e9)
            p_loss = F.cross_entropy(logits, label[sel])
            v_loss = F.mse_loss(val.reshape(-1), value[sel])
            loss = p_loss + a.value_weight * v_loss
            if not torch.isfinite(loss):
                all_finite = False
                continue
            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0))
            if not np.isfinite(gn):
                all_finite = False
                opt.zero_grad(set_to_none=True)
                continue
            opt.step()
            steps += 1
            ep_p += float(p_loss.detach())
            ep_v += float(v_loss.detach())
            nb += 1
        vm = evaluate(va)
        h = sha_state(model.state_dict())
        hashes.append(h)
        hist.append({"epoch": ep, "optimizer_steps_cumulative": steps, "batches": nb,
                     "train_policy_loss": round(ep_p / max(1, nb), 6),
                     "train_value_loss": round(ep_v / max(1, nb), 6),
                     "validation": vm, "checkpoint_sha256": h,
                     "elapsed_s": round(time.time() - t0, 1)})
        if vm and vm["top1_agreement"] > best[0]:
            best = (vm["top1_agreement"],
                    {k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
        print(f"[c018 distill] ep={ep} steps={steps} "
              f"train_p={hist[-1]['train_policy_loss']:.4f} "
              f"val_top1={(vm or {}).get('top1_agreement')} {h[:10]}", flush=True)

    if best[1] is not None:
        model.load_state_dict(best[1])
    ckpt = os.path.join(CKPT, f"{a.tag}.pt")
    torch.save({"state_dict": model.state_dict(), "cfg": model.cfg,
                "trained_on": a.prefix, "trusted_rows_only": True}, ckpt)
    hash_after = sha_state(model.state_dict())

    # P10 — exact reload: metrics must be identical from a cold load of the saved file.
    m2 = tm.TorchPolicy(dtype=torch.float32, device=dev)
    m2.load_state_dict(torch.load(ckpt, map_location=dev)["state_dict"])
    m2.to(dev)
    reload_hash = sha_state(m2.state_dict())
    saved = model
    model = m2
    test_reload = evaluate(te)
    model = saved
    test_direct = evaluate(te)

    rep = {
        "milestone": "M02", "probe_ids": ["P09", "P10"],
        "device": dev, "cuda_available": torch.cuda.is_available(),
        "torch_version": torch.__version__,
        "data_prefix": a.prefix,
        "trusted_rows_only": True,
        "trusted_index_agrees_with_flag": bool(agree),
        "rows_total": int(feats["global"].shape[0]),
        "rows_trusted": len(trusted_idx),
        "rows_excluded_label_beyond_kmax": len(mislabeled),
        "k_max": KM,
        "train_rows": len(tr), "validation_rows": len(va), "test_rows": len(te),
        "epochs": a.epochs, "batch_size": a.batch, "lr": a.lr,
        "optimizer_steps": steps,
        "losses_finite": bool(all_finite),
        "checkpoint_sha256_before": hash_before,
        "checkpoint_sha256_after": hash_after,
        "checkpoint_changed": hash_before != hash_after,
        "distinct_epoch_hashes": len(set(hashes)),
        "reload_hash_matches": reload_hash == hash_after,
        "reload_metrics_identical": test_reload == test_direct,
        "checkpoint_file": os.path.relpath(ckpt, _REPO),
        "checkpoint_file_sha256": sha_file(ckpt),
        "continues_c017_checkpoint": False,
        "uses_c017_labels": False,
        "final_validation": evaluate(va),
        "held_out_test": test_direct,
        "metric_note": ("top1_agreement is FIRST-PICK agreement: the stored label is "
                        "label_action[0], so multi-select decisions are scored on their first "
                        "chosen option only, not on the whole selection."),
        "multiselect_rows": sum(1 for r in rows if len(r["label_action"]) > 1),
        "held_out_test_from_reload": test_reload,
        "history": hist,
        "wall_clock_s": round(time.time() - t0, 1),
    }
    json.dump(rep, open(os.path.join(TRAIN, f"{a.tag}_distillation_report.json"), "w"),
              indent=2, default=str)
    if a.tag == "m02_distilled":          # canonical alias, never written by a smoke tag
        json.dump(rep, open(os.path.join(TRAIN, "distillation_report.json"), "w"), indent=2,
                  default=str)
    print(json.dumps({k: rep[k] for k in
                      ("device", "optimizer_steps", "losses_finite", "checkpoint_changed",
                       "distinct_epoch_hashes", "reload_metrics_identical", "rows_trusted",
                       "held_out_test")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
