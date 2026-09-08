"""c006 AC-06: registered reproducible training of S1 and S2 (3 seeds each).

Adam, importance-weighted masked losses, early stopping + checkpoint selection on
the validation importance-weighted teacher-action-agreement. The test split is
NEVER read here. Deterministic given seed + OMP_NUM_THREADS=1.
"""

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.policy_data import (collate_ff, collate_game, evaluate_agreement,
                            featurize_records, group_by_game, load_split)
from cg.policy_model import PolicyModel, policy_loss

ARCH_CFG = {
    "S1_STATELESS": {"recurrent": False, "cfg": {"emb": 32, "h": 160, "h2": 128}, "seeds": [101, 202, 303],
                     "max_epochs": 40},
    "S2_RECURRENT": {"recurrent": True, "cfg": {"emb": 32, "h": 160, "h2": 128, "cc": 64, "hr": 128},
                     "seeds": [111, 222, 333], "max_epochs": 30},
}
HP = {"lr": 1.5e-3, "betas": (0.9, 0.999), "eps": 1e-8, "batch": 256, "patience": 6}


class Adam:
    def __init__(self, params, lr, betas, eps):
        self.params = params; self.lr = lr; self.b1, self.b2 = betas; self.eps = eps
        self.m = [np.zeros_like(p.data) for p in params]
        self.v = [np.zeros_like(p.data) for p in params]
        self.t = 0

    def step(self):
        self.t += 1
        for i, p in enumerate(self.params):
            if p.grad is None:
                continue
            g = p.grad
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * (g * g)
            mhat = self.m[i] / (1 - self.b1 ** self.t)
            vhat = self.v[i] / (1 - self.b2 ** self.t)
            p.data -= self.lr * mhat / (np.sqrt(vhat) + self.eps)

    def zero_grad(self):
        for p in self.params:
            p.grad = None


def _loss(model, batch, recurrent):
    sc = model.forward_game(batch) if recurrent else model.forward_ff(batch)
    loss, _ = policy_loss(sc, batch["single"], batch["target"], batch["multi"],
                          batch["legal_mask"], batch["weight"])
    return loss


def train_one(arch, seed, tr_dec, va_dec, tr_gi, va_gi, log):
    spec = ARCH_CFG[arch]
    recurrent = spec["recurrent"]
    model = PolicyModel({**spec["cfg"], "recurrent": recurrent}, seed=seed)
    opt = Adam(model.params(), HP["lr"], HP["betas"], HP["eps"])
    rng = np.random.default_rng(seed)
    best = {"metric": -1.0, "epoch": -1, "state": None, "val": None}
    history = []
    no_improve = 0
    gids = list(tr_gi.keys())
    for epoch in range(spec["max_epochs"]):
        t0 = time.time()
        if recurrent:
            order = rng.permutation(len(gids))
            for gi in order:
                sub = [tr_dec[i] for i in tr_gi[gids[gi]]]
                _loss(model, collate_game(sub), True).backward()
                opt.step(); opt.zero_grad()
        else:
            idx = rng.permutation(len(tr_dec))
            for s in range(0, len(idx), HP["batch"]):
                sub = [tr_dec[i] for i in idx[s:s + HP["batch"]]]
                _loss(model, collate_ff(sub), False).backward()
                opt.step(); opt.zero_grad()
        m = evaluate_agreement(model, va_dec, va_gi, recurrent)
        metric = m["importance_weighted_agreement"]
        rec = {"epoch": epoch, "val_iw_agreement": round(metric, 5),
               "val_overall": round(m["overall_exact_agreement"], 5),
               "val_nonforced": round(m["nonforced_exact_agreement"], 5),
               "secs": round(time.time() - t0, 1)}
        history.append(rec)
        log(f"  [{arch} seed={seed}] epoch {epoch:2d} iw_agree={metric:.4f} "
            f"overall={m['overall_exact_agreement']:.4f} ({rec['secs']}s)")
        if metric > best["metric"] + 1e-5:
            best = {"metric": metric, "epoch": epoch, "state": model.state_dict(), "val": m}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= HP["patience"]:
                log(f"  [{arch} seed={seed}] early stop at epoch {epoch}")
                break
    model.load_state(best["state"])
    return model, best, history


def run(args):
    ds = os.path.join(args.in_dir, "sequence_dataset")
    ckpt_dir = os.path.join(args.in_dir, "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    logdir = args.log_dir
    os.makedirs(logdir, exist_ok=True)

    tr_dec = featurize_records(load_split(ds, "train"))
    va_dec = featurize_records(load_split(ds, "validation"))
    tr_gi = group_by_game(tr_dec)
    va_gi = group_by_game(va_dec)

    archs = ["S1_STATELESS", "S2_RECURRENT"] if args.arch == "both" else [args.arch]
    runs = {"contract": "c006_distilled_policy_baseline", "hp": HP, "architectures": {}}
    for arch in archs:
        logpath = os.path.join(logdir, f"training_{'S1' if arch.startswith('S1') else 'S2'}.txt")
        lines = []

        def log(s, _l=lines):
            print(s); _l.append(s)

        log(f"=== training {arch} (seeds {ARCH_CFG[arch]['seeds']}) ===")
        seed_results = []
        for seed in ARCH_CFG[arch]["seeds"]:
            model, best, history = train_one(arch, seed, tr_dec, va_dec, tr_gi, va_gi, log)
            cpath = os.path.join(ckpt_dir, f"{arch}_seed{seed}.npz")
            model.save(cpath)
            csha = hashlib.sha256(open(cpath, "rb").read()).hexdigest()
            seed_results.append({"seed": seed, "best_epoch": best["epoch"],
                                 "best_val_iw_agreement": best["metric"],
                                 "best_val": {k: v for k, v in best["val"].items()
                                              if isinstance(v, (int, float))},
                                 "checkpoint": os.path.relpath(cpath, _REPO),
                                 "checkpoint_sha256": csha, "param_count": model.param_count(),
                                 "history": history})
            log(f"  [{arch} seed={seed}] BEST val_iw_agreement={best['metric']:.4f} "
                f"@epoch {best['epoch']} sha={csha[:12]}")
        # select best seed
        best_seed = max(seed_results, key=lambda r: r["best_val_iw_agreement"])
        sel_path = os.path.join(ckpt_dir, f"{arch}_selected.npz")
        model = PolicyModel.load(os.path.join(_REPO, best_seed["checkpoint"]))
        model.save(sel_path)
        sel_sha = hashlib.sha256(open(sel_path, "rb").read()).hexdigest()
        log(f"=== {arch}: SELECTED seed={best_seed['seed']} "
            f"val_iw_agreement={best_seed['best_val_iw_agreement']:.4f} sha={sel_sha[:12]} ===")
        runs["architectures"][arch] = {
            "seeds": seed_results, "selected_seed": best_seed["seed"],
            "selected_checkpoint": os.path.relpath(sel_path, _REPO),
            "selected_checkpoint_sha256": sel_sha,
            "selected_val_iw_agreement": best_seed["best_val_iw_agreement"],
            "param_count": best_seed["param_count"],
        }
        open(logpath, "w").write("\n".join(lines) + "\n")

    # merge into training_runs.json (preserve any arch already present)
    runs_path = os.path.join(args.in_dir, "training_runs.json")
    if os.path.exists(runs_path) and args.arch != "both":
        prev = json.load(open(runs_path))
        prev.setdefault("architectures", {}).update(runs["architectures"])
        runs = prev
    json.dump(runs, open(runs_path, "w"), indent=2)
    print(json.dumps({a: {"selected_seed": runs["architectures"][a]["selected_seed"],
                          "val_iw_agreement": round(runs["architectures"][a]["selected_val_iw_agreement"], 4)}
                      for a in runs["architectures"]}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arch", default="both", choices=["both", "S1_STATELESS", "S2_RECURRENT"])
    p.add_argument("--in-dir", required=True)
    p.add_argument("--log-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
