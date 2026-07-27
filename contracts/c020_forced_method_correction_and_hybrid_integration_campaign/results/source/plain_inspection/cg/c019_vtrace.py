"""c019 Branch B — V-trace targets and UPGO auxiliary loss.

METHOD_FIDELITY B: real V-trace targets (not GAE renamed), a nonzero UPGO auxiliary policy loss,
and the paper's V-trace/PPO-clipped policy objective. Registered constants come from
arXiv 2303.05197 Table III: gamma 1.0, c and rho clipped to [0.001, 1.007], PPO epsilon 0.2.

Two implementations of each quantity are provided on purpose: a plain NumPy reference written
directly from the equations, and the torch path used in training. B04/B05 assert they agree. A
single implementation can be confidently wrong; two written from the same equations by different
means and compared numerically cannot be wrong in the same way silently.

Note on gamma = 1.0: the V-trace recursion `acc = delta + gamma * c * acc` does not contract at
gamma = 1, so targets can grow with horizon. That is what the source specifies, so it is kept —
but target magnitudes are logged from the first fixture onward so divergence is distinguishable
from a bug.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import torch

VTRACE_VERSION = "c019.vtrace.v1"

# Registered source constants (arXiv 2303.05197, Table III)
GAMMA = 1.0
C_LOWER, C_UPPER = 0.001, 1.007
RHO_LOWER, RHO_UPPER = 0.001, 1.007
PPO_CLIP_EPS = 0.2


# ---------------------------------------------------------------- NumPy reference

def vtrace_reference(behavior_logp: np.ndarray, target_logp: np.ndarray,
                     values: np.ndarray, bootstrap_value: float,
                     rewards: np.ndarray, discounts: np.ndarray) -> Dict[str, np.ndarray]:
    """Plain V-trace from the equations. [T] arrays for one trajectory."""
    T = len(rewards)
    rho = np.exp(target_logp - behavior_logp)
    c = np.clip(rho, C_LOWER, C_UPPER)
    rho_bar = np.clip(rho, RHO_LOWER, RHO_UPPER)

    values_tp1 = np.concatenate([values[1:], np.array([bootstrap_value])])
    delta = rho_bar * (rewards + discounts * values_tp1 - values)

    vs = np.zeros(T, dtype=np.float64)
    acc = 0.0
    for t in reversed(range(T)):
        acc = delta[t] + discounts[t] * c[t] * acc
        vs[t] = values[t] + acc

    vs_tp1 = np.concatenate([vs[1:], np.array([bootstrap_value])])
    # policy advantage uses the V-trace target at t+1, per the source
    pg_adv = rho_bar * (rewards + discounts * vs_tp1 - values)
    return {"vs": vs, "pg_advantage": pg_adv, "rho": rho, "rho_bar": rho_bar, "c": c,
            "delta": delta}


def upgo_reference(target_logp: np.ndarray, values: np.ndarray, bootstrap_value: float,
                   rewards: np.ndarray, discounts: np.ndarray) -> Dict[str, np.ndarray]:
    """UPGO returns: bootstrap from the better of Q and V, propagating upward-good returns.

    G_t = r_t + gamma * ( G_{t+1}  if  r_t + gamma*V_{t+1} >= V_t  else  V_{t+1} )
    """
    T = len(rewards)
    values_tp1 = np.concatenate([values[1:], np.array([bootstrap_value])])
    G = np.zeros(T, dtype=np.float64)
    nxt = bootstrap_value
    for t in reversed(range(T)):
        q_t = rewards[t] + discounts[t] * values_tp1[t]
        G[t] = rewards[t] + discounts[t] * (nxt if q_t >= values[t] else values_tp1[t])
        nxt = G[t]
    advantage = G - values
    return {"returns": G, "advantage": advantage}


# ---------------------------------------------------------------- torch training path

def vtrace_torch(behavior_logp: torch.Tensor, target_logp: torch.Tensor,
                 values: torch.Tensor, bootstrap_value: torch.Tensor,
                 rewards: torch.Tensor, discounts: torch.Tensor
                 ) -> Dict[str, torch.Tensor]:
    """V-trace over [T, B]. Importance ratios are detached: V-trace corrects off-policy
    sampling, it is not itself a differentiable path to the policy."""
    with torch.no_grad():
        rho = torch.exp(target_logp - behavior_logp)
        c = rho.clamp(C_LOWER, C_UPPER)
        rho_bar = rho.clamp(RHO_LOWER, RHO_UPPER)
        values_tp1 = torch.cat([values[1:], bootstrap_value.unsqueeze(0)], dim=0)
        delta = rho_bar * (rewards + discounts * values_tp1 - values)

        T = rewards.shape[0]
        vs_minus_v = torch.zeros_like(values)
        acc = torch.zeros_like(values[0])
        for t in reversed(range(T)):
            acc = delta[t] + discounts[t] * c[t] * acc
            vs_minus_v[t] = acc
        vs = values + vs_minus_v
        vs_tp1 = torch.cat([vs[1:], bootstrap_value.unsqueeze(0)], dim=0)
        pg_adv = rho_bar * (rewards + discounts * vs_tp1 - values)
    return {"vs": vs, "pg_advantage": pg_adv, "rho": rho, "rho_bar": rho_bar, "c": c}


def upgo_torch(values: torch.Tensor, bootstrap_value: torch.Tensor,
               rewards: torch.Tensor, discounts: torch.Tensor) -> Dict[str, torch.Tensor]:
    with torch.no_grad():
        values_tp1 = torch.cat([values[1:], bootstrap_value.unsqueeze(0)], dim=0)
        T = rewards.shape[0]
        G = torch.zeros_like(values)
        nxt = bootstrap_value
        for t in reversed(range(T)):
            q_t = rewards[t] + discounts[t] * values_tp1[t]
            G[t] = rewards[t] + discounts[t] * torch.where(q_t >= values[t], nxt,
                                                           values_tp1[t])
            nxt = G[t]
        adv = G - values
    return {"returns": G, "advantage": adv}


def ppo_clipped_policy_loss(target_logp: torch.Tensor, behavior_logp: torch.Tensor,
                            advantage: torch.Tensor, eps: float = PPO_CLIP_EPS
                            ) -> torch.Tensor:
    """The paper replaces V-trace's importance-sampling PG with PPO-style clipping.

    Ordinary PPO alone is NOT ByteRL; what makes this ByteRL is that `advantage` is the
    V-trace (or UPGO) advantage rather than GAE.
    """
    ratio = torch.exp(target_logp - behavior_logp)
    unclipped = ratio * advantage
    clipped = ratio.clamp(1.0 - eps, 1.0 + eps) * advantage
    return -torch.min(unclipped, clipped).mean()


def losses(target_logp, behavior_logp, values, bootstrap_value, rewards, discounts,
           entropy, weights=None) -> Dict[str, torch.Tensor]:
    """Full ByteRL objective: V-trace PG + UPGO + value + entropy, each reported separately."""
    w = {"policy": 1.0, "upgo": 1.0, "value": 1.0, "entropy": 0.01}
    if weights:
        w.update(weights)
    vt = vtrace_torch(behavior_logp, target_logp, values, bootstrap_value, rewards, discounts)
    ug = upgo_torch(values, bootstrap_value, rewards, discounts)
    pg = ppo_clipped_policy_loss(target_logp, behavior_logp, vt["pg_advantage"])
    upgo_loss = ppo_clipped_policy_loss(target_logp, behavior_logp, ug["advantage"])
    value_loss = 0.5 * ((values - vt["vs"]) ** 2).mean()
    ent_loss = -entropy.mean()
    total = (w["policy"] * pg + w["upgo"] * upgo_loss + w["value"] * value_loss
             + w["entropy"] * ent_loss)
    return {"total": total, "policy_vtrace": pg, "upgo": upgo_loss, "value": value_loss,
            "entropy": -ent_loss, "vs_mean": vt["vs"].mean(), "vs_absmax": vt["vs"].abs().max(),
            "rho_mean": vt["rho"].mean(), "rho_clipped_frac":
                ((vt["rho"] < RHO_LOWER) | (vt["rho"] > RHO_UPPER)).float().mean(),
            "upgo_adv_absmean": ug["advantage"].abs().mean()}
