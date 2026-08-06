"""c011 §12 — the registered PPO update, in PyTorch. Backend only; the algorithm is c010 Arm C.

Every element mirrors `starter_kit/ppo.py` exactly:

  * GAE(gamma, lambda) computed by the legacy function on the legacy records, so advantages
    and returns are literally the same numbers;
  * advantage normalisation ONCE per update over the whole batch, before the epoch loop;
  * clipped surrogate with the branch chosen by a HARD 0/1 mask taken from detached values
    (`use1 = (s1 <= s2)`), not by a differentiable min -- legacy takes no gradient through
    the selector, and torch.min would;
  * clipped value loss with the same detached `usev = (l1 >= l2)` selector and 0.5 factor;
  * entropy bonus with the scheduled coefficient;
  * global grad-norm clip with legacy's 1e-8 epsilon (torch's clip_grad_norm_ uses 1e-6);
  * AdamW: torch's decoupled update is algebraically identical to the legacy step
    `p -= lr * (mhat / (sqrt(vhat) + eps) + wd * p)`, verified by the parity test.

The minibatch permutation is PASSED IN rather than regenerated, so a parity run consumes the
identical shuffle sequence the legacy path consumed (§10.4 "same minibatch order and seed").
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import ppo as legacy_ppo, rl_policy as rlp  # noqa: E402
import c011_torch_model as tm  # noqa: E402


def make_optimizer(model, lr: float, wd: float, betas=(0.9, 0.999), eps: float = 1e-8):
    return torch.optim.AdamW(model.parameters(), lr=lr, betas=betas, eps=eps, weight_decay=wd)


def clip_grad_norm_legacy(params, max_norm: float) -> float:
    """Legacy global clip: scale = max_norm / (gnorm + 1e-8). Returns the pre-clip norm."""
    grads = [p.grad for p in params if p.grad is not None]
    if not grads:
        return 0.0
    total = torch.sqrt(sum((g.detach() ** 2).sum() for g in grads))
    gnorm = float(total)
    if max_norm is not None and gnorm > max_norm:
        scale = max_norm / (gnorm + 1e-8)
        for g in grads:
            g.mul_(scale)
    return gnorm


def precompute_order(n: int, epochs: int, rng) -> List[np.ndarray]:
    """Reproduce legacy's per-epoch shuffle sequence from the same Generator."""
    order = np.arange(n)
    seq = []
    for _ in range(epochs):
        rng.shuffle(order)
        seq.append(order.copy())
    return seq


def ppo_update_torch(model: tm.TorchPolicy, games, cfg: Dict[str, Any], opt, entropy_coef: float,
                     rng=None, orders: Optional[Sequence[np.ndarray]] = None,
                     device: str = "cpu", flat=None,
                     autocast_dtype=None) -> Dict[str, Any]:
    """One registered PPO update. `orders` (optional) forces the exact minibatch permutation."""
    if flat is None:
        flat = legacy_ppo.compute_gae(games, cfg["gamma"], cfg["lam"])
    if not flat:
        return {"n_decisions": 0, "skipped": True}

    adv = np.array([t["advantage"] for t in flat])
    ret = np.array([t["ret"] for t in flat])
    oldv = np.array([t["value"] for t in flat])
    oldlp = np.array([t["logprob"] for t in flat])
    adv_norm = (adv - adv.mean()) / (adv.std() + 1e-8)

    N = len(flat)
    mb = cfg["minibatch"]
    epochs = cfg["epochs"]
    if orders is None:
        orders = precompute_order(N, epochs, rng)

    dt = model.dt
    diag = {"policy_loss": [], "value_loss": [], "entropy": [], "approx_kl": [],
            "clip_frac": [], "grad_norm": []}
    all_new_v = np.zeros(N)
    params = [p for p in model.parameters() if p.requires_grad]

    for ep in range(epochs):
        order = orders[ep]
        for s in range(0, N, mb):
            idx = order[s:s + mb]
            sub = [flat[i] for i in idx]
            b, arr = rlp.collate_rl(sub)
            tb = tm.to_torch_batch(b, dt, device)
            ta = tm.to_torch_act(arr, dt, device)
            a = torch.as_tensor(adv_norm[idx], dtype=dt, device=device)
            ol = torch.as_tensor(oldlp[idx], dtype=dt, device=device)
            r = torch.as_tensor(ret[idx], dtype=dt, device=device)
            ov = torch.as_tensor(oldv[idx], dtype=dt, device=device)

            ctx = (torch.autocast("cuda", dtype=autocast_dtype)
                   if (autocast_dtype is not None and device.startswith("cuda"))
                   else _null_ctx())
            with ctx:
                newlp, ent, val, _ = tm.evaluate(model, tb, ta)
            newlp = newlp.to(dt); ent = ent.to(dt); val = val.to(dt)

            ratio = torch.exp(newlp - ol)
            clipped = torch.clamp(ratio, 1 - cfg["clip"], 1 + cfg["clip"])
            s1 = ratio * a
            s2 = clipped * a
            use1 = (s1.detach() <= s2.detach()).to(dt)          # hard selector, no gradient
            pol_loss = -(s1 * use1 + s2 * (1 - use1)).sum() / len(idx)

            v_clip = ov + torch.clamp(val - ov, -cfg["clip"], cfg["clip"])
            l1 = (val - r) ** 2
            l2 = (v_clip - r) ** 2
            usev = (l1.detach() >= l2.detach()).to(dt)
            v_loss = (l1 * usev + l2 * (1 - usev)).sum() * (0.5 / len(idx))

            ent_mean = ent.sum() / len(idx)
            loss = pol_loss + v_loss * cfg["vf_coef"] - ent_mean * entropy_coef

            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = clip_grad_norm_legacy(params, cfg["max_grad_norm"])
            opt.step()

            # Legacy diagnostics computed from the numpy ratio: the k3 KL estimator
            # (r - 1) - log(r), NOT (oldlp - newlp). Matched exactly so parity is meaningful.
            with torch.no_grad(), np.errstate(over="ignore"):
                rr = np.exp(newlp.detach().double().cpu().numpy() - oldlp[idx])
                approx_kl = float(np.mean((rr - 1) - np.log(rr + 1e-12)))
                clip_frac = float(np.mean(np.abs(rr - 1) > cfg["clip"]))
            diag["policy_loss"].append(float(pol_loss.detach()))
            diag["value_loss"].append(float(v_loss.detach()))
            diag["entropy"].append(float(ent_mean.detach()))
            diag["approx_kl"].append(approx_kl)
            diag["clip_frac"].append(clip_frac)
            diag["grad_norm"].append(gn)
            if ep == epochs - 1:
                all_new_v[idx] = val.detach().double().cpu().numpy()

    ev = legacy_ppo.explained_variance(all_new_v, ret)   # legacy argument order
    return {"n_decisions": N,
            "policy_loss": float(np.mean(diag["policy_loss"])),
            "value_loss": float(np.mean(diag["value_loss"])),
            "entropy": float(np.mean(diag["entropy"])),
            "approx_kl": float(np.mean(diag["approx_kl"])),
            "clip_frac": float(np.mean(diag["clip_frac"])),
            "grad_norm": float(np.mean(diag["grad_norm"])),
            "explained_variance": ev,
            "return_mean": float(ret.mean()),
            "advantage_mean": float(adv.mean()),
            "skipped": False}


class _null_ctx:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False
