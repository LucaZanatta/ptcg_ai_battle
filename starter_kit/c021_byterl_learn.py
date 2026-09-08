"""c021 B5/B6 — V-trace, UPGO and the OSFP outer loop.

From arXiv:2303.04096 (LOCM ByteRL) and arXiv:2303.05197 (Hearthstone improvements). No author
implementation exists, so every formula below is transcribed from the papers and from the
IMPALA / AlphaStar results they cite; each unresolved choice is recorded in
`results/fidelity/UNRESOLVED_REFERENCE_CHOICES.md` rather than silently picked.

`FIDELITY_RULES §4` allows the hardware to reduce actor count, sample count, duration and
achieved learning periods -- and nothing else. So all three algorithmic components are here in
full:

  * **V-trace** (Espeholt et al., used by ByteRL) with clipped importance weights rho-bar and
    c-bar, correcting for the lag between the actor's behaviour policy and the learner.
  * **UPGO** (AlphaStar, adopted by ByteRL) whose return bootstraps from the value only when the
    value EXCEEDS the one-step return, so the policy is pulled toward better-than-expected play
    rather than toward the mean.
  * **OSFP** with PERIOD-LOCAL G and C matrices and frozen-checkpoint promotion. Fictitious play
    against the running average of past opponents; the payoff bookkeeping must be reset per
    period or the meta-strategy converges to the whole of history rather than to the period.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F


# ====================================================================== V-trace
@dataclass
class VTraceOutput:
    vs: torch.Tensor              # corrected value targets
    pg_advantage: torch.Tensor    # advantage for the policy gradient
    rho: torch.Tensor
    clipped_rho: torch.Tensor
    clipped_c: torch.Tensor


def vtrace(behaviour_logp: torch.Tensor,
           target_logp: torch.Tensor,
           rewards: torch.Tensor,
           values: torch.Tensor,
           bootstrap_value: torch.Tensor,
           discounts: torch.Tensor,
           rho_bar: float = 1.0,
           c_bar: float = 1.0) -> VTraceOutput:
    """V-trace, computed backwards over a trajectory of length T.

        rho_t   = min(rho_bar, pi(a_t|s_t) / mu(a_t|s_t))
        c_t     = min(c_bar,   pi(a_t|s_t) / mu(a_t|s_t))
        dV_t    = rho_t * (r_t + gamma * V(s_{t+1}) - V(s_t))
        vs_t    = V(s_t) + dV_t + gamma * c_t * (vs_{t+1} - V(s_{t+1}))

    The policy-gradient advantage uses vs_{t+1}, NOT vs_t -- using vs_t leaks the current action's
    own return into its baseline and shrinks every advantage toward zero.

    All tensors are (T,) for one trajectory or (T, B) for a batch.
    """
    with torch.no_grad():
        log_ratio = target_logp - behaviour_logp
        rho = torch.exp(log_ratio)
        clipped_rho = torch.clamp(rho, max=rho_bar)
        clipped_c = torch.clamp(rho, max=c_bar)

        vals_tp1 = torch.cat([values[1:], bootstrap_value.unsqueeze(0)], dim=0)
        deltas = clipped_rho * (rewards + discounts * vals_tp1 - values)

        T = values.shape[0]
        acc = torch.zeros_like(bootstrap_value)
        out = []
        for t in range(T - 1, -1, -1):
            acc = deltas[t] + discounts[t] * clipped_c[t] * acc
            out.append(acc)
        vs_minus_v = torch.stack(out[::-1], dim=0)
        vs = vs_minus_v + values

        vs_tp1 = torch.cat([vs[1:], bootstrap_value.unsqueeze(0)], dim=0)
        pg_adv = clipped_rho * (rewards + discounts * vs_tp1 - values)

    return VTraceOutput(vs=vs, pg_advantage=pg_adv, rho=rho,
                        clipped_rho=clipped_rho, clipped_c=clipped_c)


# ====================================================================== UPGO
def upgo_returns(rewards: torch.Tensor, values: torch.Tensor,
                 bootstrap_value: torch.Tensor, discounts: torch.Tensor) -> torch.Tensor:
    """UPGO (AlphaStar) return, backwards:

        G_t = r_t + gamma * ( G_{t+1}  if Q_{t+1} >= V(s_{t+1}) else V(s_{t+1}) )

    where Q_{t+1} = r_{t+1} + gamma * V(s_{t+2}) is the one-step return.

    The switch is the whole point: the target follows the trajectory only while the trajectory is
    doing BETTER than the value function expected, and otherwise cuts to the baseline. Always
    following the trajectory would make this plain Monte-Carlo; always cutting would make it
    one-step TD.
    """
    with torch.no_grad():
        T = values.shape[0]
        vals_tp1 = torch.cat([values[1:], bootstrap_value.unsqueeze(0)], dim=0)
        vals_tp2 = torch.cat([values[2:], bootstrap_value.unsqueeze(0),
                              bootstrap_value.unsqueeze(0)], dim=0)
        rew_tp1 = torch.cat([rewards[1:], torch.zeros_like(bootstrap_value).unsqueeze(0)], dim=0)
        q_tp1 = rew_tp1 + discounts * vals_tp2

        g = bootstrap_value
        out = []
        for t in range(T - 1, -1, -1):
            nxt = torch.where(q_tp1[t] >= vals_tp1[t], g, vals_tp1[t])
            g = rewards[t] + discounts[t] * nxt
            out.append(g)
        return torch.stack(out[::-1], dim=0)


# ====================================================================== losses
@dataclass
class LossConfig:
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    upgo_coef: float = 1.0
    policy_coef: float = 1.0
    rho_bar: float = 1.0
    c_bar: float = 1.0
    discount: float = 1.0        # PTCG terminal reward only; no per-step shaping
    max_grad_norm: float = 10.0


def byterl_losses(target_logp: torch.Tensor,
                  behaviour_logp: torch.Tensor,
                  entropy: torch.Tensor,
                  values: torch.Tensor,
                  rewards: torch.Tensor,
                  bootstrap_value: torch.Tensor,
                  discounts: torch.Tensor,
                  cfg: LossConfig) -> Tuple[torch.Tensor, Dict[str, float]]:
    """The combined ByteRL objective: V-trace policy gradient + UPGO + value + entropy."""
    vt = vtrace(behaviour_logp, target_logp, rewards, values.detach(),
                bootstrap_value, discounts, cfg.rho_bar, cfg.c_bar)

    pg_loss = -(vt.pg_advantage * target_logp).mean()

    g_upgo = upgo_returns(rewards, values.detach(), bootstrap_value, discounts)
    upgo_adv = (g_upgo - values.detach()).clamp(min=0.0) * vt.clipped_rho
    upgo_loss = -(upgo_adv * target_logp).mean()

    value_loss = 0.5 * (values - vt.vs).pow(2).mean()
    entropy_loss = -entropy.mean()

    total = (cfg.policy_coef * pg_loss
             + cfg.upgo_coef * upgo_loss
             + cfg.value_coef * value_loss
             + cfg.entropy_coef * entropy_loss)

    stats = {"pg_loss": float(pg_loss.item()), "upgo_loss": float(upgo_loss.item()),
             "value_loss": float(value_loss.item()), "entropy": float(entropy.mean().item()),
             "rho_mean": float(vt.rho.mean().item()),
             "rho_clipped_frac": float((vt.rho > cfg.rho_bar).float().mean().item()),
             "vs_mean": float(vt.vs.mean().item()),
             "upgo_mean": float(g_upgo.mean().item()),
             "total": float(total.item())}
    return total, stats


# ====================================================================== OSFP
class OSFP:
    """Outcome Sampling Fictitious Play with PERIOD-LOCAL payoff bookkeeping.

    `G` accumulates payoffs and `C` counts games, both **within the current learning period**.
    Resetting them at each promotion is not a detail: carrying them across periods makes the
    meta-strategy converge to the average over all of history, so a checkpoint that was strong
    twenty periods ago keeps dominating the opponent distribution long after the policy has moved
    past it. c019 and c020 both accumulated globally.

    The learner plays against FROZEN checkpoints. Promotion appends the current weights as a new
    frozen opponent and starts a new period.
    """

    def __init__(self, max_checkpoints: int = 16, eta: float = 0.1):
        self.max_checkpoints = max_checkpoints
        self.eta = eta
        self.checkpoints: List[Dict[str, Any]] = []
        self.G: Dict[int, float] = {}
        self.C: Dict[int, int] = {}
        self.period = 0
        # IMMUTABLE HISTORY. `checkpoints` is a bounded SAMPLING buffer -- old entries are
        # evicted so the meta-distribution does not go stale. `history` is append-only and is
        # never evicted or rewritten, so the promotion record stays auditable even after the
        # weights it refers to have left the buffer.
        self.history: List[Dict[str, Any]] = []

    def reset_period(self):
        """Called on promotion. G and C are PERIOD-LOCAL."""
        self.G.clear()
        self.C.clear()
        self.period += 1

    def add_checkpoint(self, state: Dict[str, Any], label: str):
        entry = {"state": state, "label": label, "period": self.period}
        self.checkpoints.append(entry)
        self.history.append({"label": label, "period": self.period,
                             "index": len(self.history),
                             "payoffs": {str(i): round(self.mean_payoff(i), 4)
                                         for i in sorted(self.C)},
                             "period_games": int(sum(self.C.values()))})
        if len(self.checkpoints) > self.max_checkpoints:
            evicted = self.checkpoints.pop(0)
            self.history.append({"label": evicted["label"], "period": evicted["period"],
                                 "index": len(self.history), "evicted_from_buffer": True})

    def record(self, opponent_index: int, payoff: float):
        self.G[opponent_index] = self.G.get(opponent_index, 0.0) + float(payoff)
        self.C[opponent_index] = self.C.get(opponent_index, 0) + 1

    def mean_payoff(self, i: int) -> float:
        return self.G.get(i, 0.0) / self.C[i] if self.C.get(i) else 0.0

    def opponent_distribution(self) -> np.ndarray:
        """Fictitious play: weight opponents the learner is doing WORST against.

        Uniform when no games have been played this period, which is the correct prior -- a
        freshly promoted checkpoint has no evidence yet.
        """
        n = len(self.checkpoints)
        if n == 0:
            return np.ones(1)
        scores = np.array([-self.mean_payoff(i) for i in range(n)], dtype=np.float64)
        if not self.C:
            return np.ones(n) / n
        z = scores / max(self.eta, 1e-6)
        z -= z.max()
        p = np.exp(z)
        return p / p.sum()

    def sample_opponent(self, rng) -> int:
        p = self.opponent_distribution()
        return int(rng.choice(len(p), p=p))

    def should_promote(self, win_rate: float, games: int, threshold: float = 0.55,
                       min_games: int = 200) -> bool:
        return games >= min_games and win_rate >= threshold

    def history_log(self) -> List[Dict[str, Any]]:
        """Append-only promotion record. Never rewritten."""
        return [dict(h) for h in self.history]

    def snapshot(self) -> Dict[str, Any]:
        return {"period": self.period, "checkpoints": len(self.checkpoints),
                "history_entries": len(self.history),
                "period_games": int(sum(self.C.values())),
                "mean_payoffs": {str(i): round(self.mean_payoff(i), 4) for i in self.C},
                "distribution": [round(float(x), 4) for x in self.opponent_distribution()]}


def clip_grads(model, max_norm: float) -> float:
    return float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm))
