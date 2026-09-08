"""c008 PPO update (one implementation for all arms, §10).

Clipped surrogate policy loss + clipped value loss + decayed entropy bonus over masked
action distributions, GAE(gamma, lambda) per episode. R2 adds a decayed offline
teacher-replay NLL (c007 train split only) and a decayed KL anchor to the frozen initial
V2-A policy on on-policy states. AdamW. Consecutive trainable steps are treated as adjacent
for discounting (forced steps carry no decision value) — registered choice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cg import micrograd as mg
from cg import rl_policy as rlp


# -------------------- GAE --------------------

def compute_gae(games: List[List[Dict[str, Any]]], gamma: float, lam: float):
    """Annotate each transition with 'advantage' and 'ret' (return). Each game is a list of
    trainable transitions with 'reward','done','value'. Bootstrap value at episode end = 0
    (terminal). Returns flat transition list."""
    flat = []
    for g in games:
        if not g:
            continue
        adv = 0.0
        for t in reversed(range(len(g))):
            v = g[t]["value"]
            v_next = g[t + 1]["value"] if t + 1 < len(g) else 0.0
            nonterminal = 1.0 - g[t]["done"]
            delta = g[t]["reward"] + gamma * v_next * nonterminal - v
            adv = delta + gamma * lam * nonterminal * adv
            g[t]["advantage"] = adv
            g[t]["ret"] = adv + v
        flat.extend(g)
    return flat


def explained_variance(values, returns):
    values = np.asarray(values); returns = np.asarray(returns)
    var = returns.var()
    return float(1.0 - (returns - values).var() / var) if var > 1e-12 else 0.0


# -------------------- AdamW --------------------

class AdamW:
    def __init__(self, params, lr, betas=(0.9, 0.999), eps=1e-8, wd=1e-5):
        self.params = params; self.lr = lr; self.b1, self.b2 = betas; self.eps = eps; self.wd = wd
        self.m = [np.zeros_like(p.data) for p in params]
        self.v = [np.zeros_like(p.data) for p in params]
        self.t = 0

    def step(self, max_grad_norm=None):
        # global grad-norm clip
        gnorm = np.sqrt(sum(float((p.grad ** 2).sum()) for p in self.params if p.grad is not None))
        scale = 1.0
        if max_grad_norm is not None and gnorm > max_grad_norm:
            scale = max_grad_norm / (gnorm + 1e-8)
        self.t += 1
        for i, p in enumerate(self.params):
            if p.grad is None:
                continue
            g = p.grad * scale
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * (g * g)
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            p.data -= self.lr * (mh / (np.sqrt(vh) + self.eps) + self.wd * p.data)
        return gnorm


# -------------------- masked KL / replay helpers --------------------

# -------------------- PPO update --------------------

def ppo_update(policy, games, cfg, opt: AdamW, entropy_coef: float,
               ref_policy=None, replay_pool=None, replay_coef: float = 0.0,
               kl_coef: float = 0.0, rng=None) -> Dict[str, Any]:
    flat = compute_gae(games, cfg["gamma"], cfg["lam"])
    if not flat:
        return {"n_decisions": 0, "skipped": True}
    adv = np.array([t["advantage"] for t in flat])
    ret = np.array([t["ret"] for t in flat])
    oldv = np.array([t["value"] for t in flat])
    oldlp = np.array([t["logprob"] for t in flat])
    adv_norm = (adv - adv.mean()) / (adv.std() + 1e-8)
    for i, t in enumerate(flat):
        t["adv_n"] = adv_norm[i]; t["ret_"] = ret[i]; t["oldv"] = oldv[i]; t["oldlp"] = oldlp[i]
    N = len(flat)
    mb = cfg["minibatch"]
    order = np.arange(N)
    diag = {"policy_loss": [], "value_loss": [], "entropy": [], "approx_kl": [],
            "clip_frac": [], "grad_norm": [], "replay_loss": [], "ref_kl": []}
    all_new_v = np.zeros(N)
    for epoch in range(cfg["epochs"]):
        rng.shuffle(order)
        for s in range(0, N, mb):
            idx = order[s:s + mb]
            sub = [flat[i] for i in idx]
            b, arr = rlp.collate_rl(sub)
            newlp, ent, val, first_logp = policy.evaluate(b, arr)
            a = mg.Node(adv_norm[idx]); ol = mg.Node(oldlp[idx])
            ratio = mg.exp(newlp + ol * mg.Node(-1.0))
            clipped = mg.clamp(ratio, 1 - cfg["clip"], 1 + cfg["clip"])
            s1 = ratio * a; s2 = clipped * a
            use1 = (s1.data <= s2.data).astype(np.float64)
            pol_loss = mg.reduce_sum(s1 * mg.Node(use1) + s2 * mg.Node(1 - use1), 0) * mg.Node(-1.0 / len(idx))
            # clipped value loss
            r = mg.Node(ret[idx]); ov = mg.Node(oldv[idx])
            v_clip = ov + mg.clamp(val + ov * mg.Node(-1.0), -cfg["clip"], cfg["clip"])
            ve1 = (val + r * mg.Node(-1.0)); ve2 = (v_clip + r * mg.Node(-1.0))
            l1 = ve1 * ve1; l2 = ve2 * ve2
            usev = (l1.data >= l2.data).astype(np.float64)
            v_loss = mg.reduce_sum(l1 * mg.Node(usev) + l2 * mg.Node(1 - usev), 0) * mg.Node(0.5 / len(idx))
            ent_mean = mg.reduce_sum(ent, 0) * mg.Node(1.0 / len(idx))
            loss = pol_loss + v_loss * mg.Node(cfg["vf_coef"]) + ent_mean * mg.Node(-entropy_coef)
            # R2 anchors
            replay_val = 0.0; refkl_val = 0.0
            if replay_coef > 0 and replay_pool is not None:
                rl_loss = _replay_loss(policy, replay_pool, rng, cfg.get("replay_mb", 256))
                loss = loss + rl_loss * mg.Node(replay_coef)
                replay_val = float(rl_loss.data)
            if kl_coef > 0 and ref_policy is not None:
                ref_logp = ref_policy.first_logp_np(b, arr["aug_mask"])   # frozen ref, numpy
                p = mg.exp(first_logp)
                kl = mg.reduce_sum(mg.reduce_sum(
                    p * (first_logp + mg.Node(-ref_logp)) * mg.Node(arr["aug_mask"]), axis=1), 0)
                refkl = kl * mg.Node(1.0 / len(idx))
                loss = loss + refkl * mg.Node(kl_coef)
                refkl_val = float(refkl.data)
            loss.backward()
            gn = opt.step(cfg["max_grad_norm"])
            # diagnostics
            with np.errstate(over="ignore"):
                rr = np.exp(newlp.data - oldlp[idx])
            diag["policy_loss"].append(float(pol_loss.data)); diag["value_loss"].append(float(v_loss.data))
            diag["entropy"].append(float(ent_mean.data)); diag["grad_norm"].append(float(gn))
            diag["approx_kl"].append(float(np.mean((rr - 1) - np.log(rr + 1e-12))))
            diag["clip_frac"].append(float(np.mean(np.abs(rr - 1) > cfg["clip"])))
            diag["replay_loss"].append(replay_val); diag["ref_kl"].append(refkl_val)
            if epoch == cfg["epochs"] - 1:
                all_new_v[idx] = val.data
    return {
        "n_decisions": N, "skipped": False,
        "policy_loss": float(np.mean(diag["policy_loss"])), "value_loss": float(np.mean(diag["value_loss"])),
        "entropy": float(np.mean(diag["entropy"])), "approx_kl": float(np.mean(diag["approx_kl"])),
        "clip_frac": float(np.mean(diag["clip_frac"])), "grad_norm": float(np.mean(diag["grad_norm"])),
        "explained_variance": explained_variance(all_new_v, ret),
        "return_mean": float(ret.mean()), "advantage_mean": float(adv.mean()),
        "replay_loss": float(np.mean(diag["replay_loss"])), "ref_kl": float(np.mean(diag["ref_kl"])),
    }


def _replay_loss(policy, pool, rng, mb):
    """Offline teacher-replay: masked NLL of the teacher action on c007 train decisions."""
    idx = rng.integers(0, len(pool), min(mb, len(pool)))
    sub = [pool[i] for i in idx]
    b, arr = rlp.collate_rl(sub)
    newlp, _, _, _ = policy.evaluate(b, arr)
    return mg.reduce_sum(newlp, 0) * mg.Node(-1.0 / len(sub))   # NLL
