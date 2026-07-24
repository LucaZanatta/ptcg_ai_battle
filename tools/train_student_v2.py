"""c007 AC-06: train the registered v2 advisory models (V2-A action-only, V2-B with
privileged planning auxiliary heads), three seeds each, pure numpy + Adam. Selection
is by validation importance-weighted teacher agreement only; test is opened once by
offline_eval_v2. OMP_NUM_THREADS=1 for byte-reproducible checkpoints.
"""

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import policy_model_v2 as pm  # noqa: E402
from cg import policy_data_v2 as pd  # noqa: E402

SEEDS = [101, 202, 303]
AUX_COEF = {"plan": 0.3, "support": 0.3, "value": 0.3}


class Adam:
    def __init__(self, params, lr=1.5e-3, b1=0.9, b2=0.999, eps=1e-8):
        self.params = params
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps
        self.m = [np.zeros_like(p.data) for p in params]
        self.v = [np.zeros_like(p.data) for p in params]
        self.t = 0

    def step(self):
        self.t += 1
        for i, p in enumerate(self.params):
            g = p.grad
            if g is None:
                continue
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * (g * g)
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            p.data -= self.lr * mh / (np.sqrt(vh) + self.eps)


def train_one(arch, seed, train_dec, val_dec, max_epochs, batch_size, patience, log_fh,
              lr=1.5e-3):
    aux = (arch == "V2_B")
    model = pm.ModelV2(seed=seed, aux=aux)
    opt = Adam(model.params(), lr=lr)
    rng = np.random.default_rng(seed)
    n = len(train_dec)
    order = np.arange(n)
    best = {"val_iw": -1.0, "epoch": -1, "state": None}
    history = []
    for ep in range(max_epochs):
        rng.shuffle(order)
        t0 = time.time()
        tot_loss = 0.0; nb = 0
        for s in range(0, n, batch_size):
            idx = order[s:s + batch_size]
            b = pd.collate([train_dec[i] for i in idx])
            out = model.forward(b)
            loss = pd.policy_loss(model, out, b, AUX_COEF)
            loss.backward()
            opt.step()
            tot_loss += float(loss.data); nb += 1
        val = pd.evaluate_agreement(model, val_dec)
        dt = time.time() - t0
        rec = {"epoch": ep, "train_loss": tot_loss / max(nb, 1),
               "val_iw_agreement": val["importance_weighted_agreement"],
               "val_exact": val["exact_agreement"], "sec": round(dt, 1)}
        history.append(rec)
        log_fh.write(f"  [{arch} seed {seed}] ep {ep} loss {rec['train_loss']:.4f} "
                     f"val_iw {rec['val_iw_agreement']:.4f} val_exact {rec['val_exact']:.4f} "
                     f"({rec['sec']}s)\n")
        log_fh.flush()
        if val["importance_weighted_agreement"] > best["val_iw"]:
            best = {"val_iw": val["importance_weighted_agreement"], "epoch": ep,
                    "state": model.state_dict()}
        if ep - best["epoch"] >= patience:
            log_fh.write(f"  [{arch} seed {seed}] early stop at ep {ep}\n")
            break
    model.load_state(best["state"])
    return model, best, history


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, help="v2 dataset dir with train/validation jsonl.gz")
    p.add_argument("--ckpt-dir", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--arch", default="both", choices=["V2_A", "V2_B", "both"])
    p.add_argument("--max-epochs", type=int, default=25)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--patience", type=int, default=5)
    p.add_argument("--seeds", default="")
    a = p.parse_args(argv)
    os.makedirs(a.ckpt_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else SEEDS

    t0 = time.time()
    train_recs = pd.load_split(os.path.join(a.data_dir, "train.jsonl.gz"))
    val_recs = pd.load_split(os.path.join(a.data_dir, "validation.jsonl.gz"))
    log_fh = open(a.log, "w")
    log_fh.write(f"featurizing train ({len(train_recs)}) + val ({len(val_recs)})...\n"); log_fh.flush()
    train_dec = pd.featurize_split(train_recs)
    val_dec = pd.featurize_split(val_recs)
    log_fh.write(f"featurized in {time.time()-t0:.1f}s; train_dec {len(train_dec)} val_dec {len(val_dec)}\n")
    log_fh.flush()

    archs = ["V2_A", "V2_B"] if a.arch == "both" else [a.arch]
    runs = {}
    for arch in archs:
        runs[arch] = {}
        best_seed = None
        for seed in seeds:
            model, best, hist = train_one(arch, seed, train_dec, val_dec, a.max_epochs,
                                          a.batch_size, a.patience, log_fh, lr=1.5e-3)
            ckpt = os.path.join(a.ckpt_dir, f"{arch}_seed{seed}.npz")
            model.save(ckpt)
            import hashlib
            sha = hashlib.sha256(open(ckpt, "rb").read()).hexdigest()
            runs[arch][str(seed)] = {"best_val_iw": best["val_iw"], "best_epoch": best["epoch"],
                                     "param_count": model.param_count(), "checkpoint": ckpt,
                                     "sha256": sha, "history": hist}
            if best_seed is None or best["val_iw"] > runs[arch][str(best_seed)]["best_val_iw"]:
                best_seed = seed
        # selected = best val seed
        sel_src = os.path.join(a.ckpt_dir, f"{arch}_seed{best_seed}.npz")
        sel_dst = os.path.join(a.ckpt_dir, f"{arch}_selected.npz")
        import shutil
        shutil.copyfile(sel_src, sel_dst)
        runs[arch]["selected_seed"] = best_seed
        runs[arch]["selected_checkpoint"] = sel_dst
        log_fh.write(f"[{arch}] selected seed {best_seed} "
                     f"(val_iw {runs[arch][str(best_seed)]['best_val_iw']:.4f})\n")
        log_fh.flush()

    out = {"contract": "c007", "seeds": seeds, "max_epochs": a.max_epochs,
           "batch_size": a.batch_size, "patience": a.patience, "lr": 1.5e-3,
           "aux_coef": AUX_COEF, "param_count": pm.ModelV2(seed=0).param_count(),
           "wall_seconds": round(time.time() - t0, 1), "runs": runs}
    json.dump(out, open(os.path.join(a.ckpt_dir, "..", "v2_training_runs.json"), "w"), indent=2)
    log_fh.write(f"DONE in {out['wall_seconds']}s\n")
    log_fh.close()
    print(json.dumps({k: {s: runs[k][s]["best_val_iw"] for s in runs[k] if s.isdigit()}
                      for k in runs}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
