"""c022 B4 — V-trace, UPGO, and the published b3 objective.

`MANDATORY_IMPLEMENTATION B4` names five hard failures: ordinary PPO, one-sided V-trace,
first-token-only ratios, zeroed recurrent starts, and a missing independent numerical reference.
This module supplies the production versions; `tests/test_c022_byterl_objectives.py` supplies
reference implementations written from the equations alone and asserts agreement.

Authority: IMPALA (arXiv:1802.01561) for V-trace, AlphaStar via the ByteRL papers for UPGO, and
the Hearthstone improvements paper (arXiv:2303.05197) for the b3 change. `FIDELITY_RULES §4` fixes
the disclosed settings.

## The b3 change, stated precisely

`FIDELITY_RULES §4` defines the ladder's top rung as "B2 with two-sided clipped V-trace and
PPO-style clipped policy objective", with `importance-ratio bounds = [0.001, 1.007]` and
`PPO-style clip epsilon = 0.2`. Two distinct things follow, and conflating them is the failure
`B4` calls "ordinary PPO":

1. **Two-sided importance-ratio clipping.** Standard V-trace clips only from above:
   `rho_t = min(rho_bar, pi/mu)`. The b3 form clips from BOTH sides:
   `rho_t = clip(pi/mu, 0.001, 1.007)`. The lower bound stops a sample the current policy has
   nearly abandoned from contributing a vanishing but nonzero correction with unbounded variance;
   the upper bound of 1.007 is far tighter than IMPALA's usual 1.0-and-above convention and makes
   the value target strongly on-policy.
2. **A PPO-style clipped surrogate driven by the V-trace advantage.** Ordinary PPO uses a GAE
   advantage from the same trajectory. Here the advantage is V-trace's —
   `rho_t * (r_t + gamma * v_{t+1} - V(s_t))` — and the surrogate is
   `min(ratio * A, clip(ratio, 1-eps, 1+eps) * A)`. Using a GAE advantage, or dropping the
   V-trace ratio from the advantage, is the hard failure.

Both bounds are applied to the COMPLETE autoregressive joint ratio — the sum of every token's
log-probability for the decision — never to the first token alone.
"""

from __future__ import annotations

import copy
import hashlib
import io
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------- disclosed settings
# FIDELITY_RULES §4 "Minimum disclosed Hearthstone settings to preserve".
GAMMA_B0 = 0.99                # B0's discount; B1 changes it to 1.0 and that IS the B1 delta
GAMMA_B1_PLUS = 1.0
LEARNING_RATE = 7e-5
SAMPLE_REUSE = 2
ENTROPY_COEF = 0.01
VALUE_COEF = 1.0
PPO_COEF = 1.0
UPGO_COEF = 1.0
RHO_LOWER_B3 = 0.001
RHO_UPPER_B3 = 1.007
PPO_CLIP_EPS = 0.2
OSFP_SELFPLAY_PROB = 0.6
OSFP_PROMOTION_THRESHOLD = 0.55
OSFP_MAX_PERIODS_WITHOUT_PROMOTION = 6

# B0/B1/B1.5/B2 use standard one-sided V-trace clipping. IMPALA's default is 1.0 for both bars;
# the papers do not restate it for the lower rungs, so it is recorded in
# UNRESOLVED_REFERENCE_CHOICES and set to IMPALA's value here.
RHO_BAR_DEFAULT = 1.0
C_BAR_DEFAULT = 1.0


@dataclass
class LossConfig:
    gamma: float = GAMMA_B1_PLUS
    rho_bar: float = RHO_BAR_DEFAULT
    c_bar: float = C_BAR_DEFAULT
    two_sided: bool = False               # b3
    rho_lower: float = RHO_LOWER_B3
    rho_upper: float = RHO_UPPER_B3
    ppo_clip: bool = False                # b3
    ppo_eps: float = PPO_CLIP_EPS
    value_coef: float = VALUE_COEF
    ppo_coef: float = PPO_COEF
    upgo_coef: float = UPGO_COEF
    entropy_coef: float = ENTROPY_COEF
    max_grad_norm: float = 40.0


# ============================================================================ V-trace
def importance_ratio(target_logp: torch.Tensor, behaviour_logp: torch.Tensor,
                     cfg: LossConfig) -> Tuple[torch.Tensor, torch.Tensor]:
    """`(rho, c)` from the COMPLETE joint log-probabilities.

    `target_logp` and `behaviour_logp` are joint log-probabilities over the whole autoregressive
    decision. Passing a first-token log-probability here is `MANDATORY_IMPLEMENTATION B4`'s
    "first-token-only ratios" hard failure, and nothing downstream could detect it — the shapes
    are identical. Probe B05 checks the joint at its source instead.
    """
    ratio = torch.exp(torch.clamp(target_logp - behaviour_logp, min=-20.0, max=20.0))
    if cfg.two_sided:
        # b3: clip from BOTH sides.
        rho = torch.clamp(ratio, min=cfg.rho_lower, max=cfg.rho_upper)
        c = torch.clamp(ratio, min=cfg.rho_lower, max=cfg.rho_upper)
    else:
        rho = torch.clamp(ratio, max=cfg.rho_bar)
        c = torch.clamp(ratio, max=cfg.c_bar)
    return rho, c


def vtrace(target_logp: torch.Tensor, behaviour_logp: torch.Tensor,
           values: torch.Tensor, rewards: torch.Tensor,
           bootstrap_value: torch.Tensor, discounts: torch.Tensor,
           cfg: LossConfig) -> Dict[str, torch.Tensor]:
    """V-trace targets and the policy-gradient advantage (IMPALA eq. 1).

        delta_t = rho_t * (r_t + gamma * V(s_{t+1}) - V(s_t))
        v_t     = V(s_t) + delta_t + gamma * c_t * (v_{t+1} - V(s_{t+1}))
        A_t     = rho_t * (r_t + gamma * v_{t+1} - V(s_t))

    The advantage uses **v_{t+1}**, not v_t. Using v_t leaks the current action's own return into
    its own baseline and shrinks every advantage toward zero.
    """
    T = values.shape[0]
    rho, c = importance_ratio(target_logp, behaviour_logp, cfg)
    values_tp1 = torch.cat([values[1:], bootstrap_value.reshape(1)], dim=0)
    deltas = rho * (rewards + discounts * values_tp1 - values)

    vs_minus_v = torch.zeros_like(values)
    acc = torch.zeros((), dtype=values.dtype, device=values.device)
    for t in range(T - 1, -1, -1):
        acc = deltas[t] + discounts[t] * c[t] * acc
        vs_minus_v[t] = acc
    vs = vs_minus_v + values
    vs_tp1 = torch.cat([vs[1:], bootstrap_value.reshape(1)], dim=0)
    pg_adv = rho * (rewards + discounts * vs_tp1 - values)
    return {"vs": vs, "pg_advantage": pg_adv, "rho": rho, "c": c,
            "ratio": torch.exp(torch.clamp(target_logp - behaviour_logp, -20.0, 20.0))}


# ============================================================================ UPGO
def upgo_returns(rewards: torch.Tensor, values: torch.Tensor,
                 bootstrap_value: torch.Tensor, discounts: torch.Tensor) -> torch.Tensor:
    """AlphaStar's upgoing return, adopted by ByteRL.

        G_t = r_t + gamma * (G_{t+1}  if  Q_{t+1} >= V(s_{t+1})  else  V(s_{t+1}))
        Q_{t+1} = r_{t+1} + gamma * V(s_{t+2})

    The conditional switch IS the method: always following the trajectory makes this Monte-Carlo,
    always cutting makes it one-step TD.
    """
    T = values.shape[0]
    values_tp1 = torch.cat([values[1:], bootstrap_value.reshape(1)], dim=0)
    rewards_tp1 = torch.cat([rewards[1:], torch.zeros(1, dtype=rewards.dtype,
                                                      device=rewards.device)], dim=0)
    values_tp2 = torch.cat([values[2:], bootstrap_value.reshape(1),
                            bootstrap_value.reshape(1)], dim=0)[:T]
    discounts_tp1 = torch.cat([discounts[1:], discounts[-1:].detach()], dim=0)
    q_tp1 = rewards_tp1 + discounts_tp1 * values_tp2

    g = torch.zeros_like(values)
    nxt = bootstrap_value
    for t in range(T - 1, -1, -1):
        follow = (q_tp1[t] >= values_tp1[t])
        target = torch.where(follow, nxt, values_tp1[t])
        g[t] = rewards[t] + discounts[t] * target
        nxt = g[t]
    return g


# ============================================================================ b3 objective
def byterl_losses(target_logp: torch.Tensor, behaviour_logp: torch.Tensor,
                  entropies: torch.Tensor, values: torch.Tensor, rewards: torch.Tensor,
                  bootstrap_value: torch.Tensor, discounts: torch.Tensor,
                  cfg: LossConfig) -> Tuple[torch.Tensor, Dict[str, float]]:
    """The full objective.

        L = L_policy + upgo_coef * L_upgo + value_coef * L_value + entropy_coef * L_entropy

    `L_policy` is `-A_t * log pi` under B0-B2, and the PPO-style clipped surrogate under b3:

        L_policy = -min( ratio * A,  clip(ratio, 1-eps, 1+eps) * A )

    with `A` the V-TRACE advantage. Ordinary PPO with a GAE advantage is the hard failure `B4`
    names; the difference is the advantage, not just the clip.
    """
    v = vtrace(target_logp, behaviour_logp, values, rewards, bootstrap_value, discounts, cfg)
    adv = v["pg_advantage"].detach()

    if cfg.ppo_clip:
        ratio = torch.exp(torch.clamp(target_logp - behaviour_logp, -20.0, 20.0))
        unclipped = ratio * adv
        clipped = torch.clamp(ratio, 1.0 - cfg.ppo_eps, 1.0 + cfg.ppo_eps) * adv
        pg_loss = -torch.min(unclipped, clipped).mean()
        clip_frac = float((torch.abs(ratio - 1.0) > cfg.ppo_eps).float().mean().item())
    else:
        pg_loss = -(adv * target_logp).mean()
        clip_frac = 0.0

    g = upgo_returns(rewards, values.detach(), bootstrap_value.detach(), discounts)
    upgo_adv = torch.clamp(g - values.detach(), min=0.0) * v["rho"].detach()
    upgo_loss = -(upgo_adv * target_logp).mean()

    value_loss = 0.5 * ((values - v["vs"].detach()) ** 2).mean()
    entropy_loss = -entropies.mean()

    total = (cfg.ppo_coef * pg_loss + cfg.upgo_coef * upgo_loss
             + cfg.value_coef * value_loss + cfg.entropy_coef * entropy_loss)

    stats = {
        "pg_loss": float(pg_loss.item()),
        "upgo_loss": float(upgo_loss.item()),
        "value_loss": float(value_loss.item()),
        "entropy": float(entropies.mean().item()),
        "total": float(total.item()),
        "rho_mean": float(v["rho"].mean().item()),
        "ratio_mean": float(v["ratio"].mean().item()),
        "rho_clipped_upper_frac": float(
            (v["ratio"] > (cfg.rho_upper if cfg.two_sided else cfg.rho_bar)).float()
            .mean().item()),
        "rho_clipped_lower_frac": float(
            (v["ratio"] < cfg.rho_lower).float().mean().item()) if cfg.two_sided else 0.0,
        "ppo_clip_frac": clip_frac,
        "vs_mean": float(v["vs"].mean().item()),
        "upgo_mean": float(g.mean().item()),
        "advantage_mean": float(adv.mean().item()),
    }
    return total, stats


def clip_grads(model, max_norm: float) -> float:
    return float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm))


# ============================================================================ OSFP
def _state_bytes(state: Dict[str, torch.Tensor]) -> bytes:
    """Serialize a state dict to bytes, for the byte-immutability probe B16."""
    buf = io.BytesIO()
    torch.save({k: v.detach().cpu() for k, v in state.items()}, buf)
    return buf.getvalue()


@dataclass
class HistoricalPolicy:
    """A frozen opponent. Immutable by construction, and provably so.

    c021's defect was that its "frozen" checkpoint was a VIEW of the live network: `.numpy()`
    shares storage with the source tensor, so the historical opponent mutated as the learner
    trained and every self-play measurement against it was against a moving target.
    `MANDATORY_IMPLEMENTATION B5` therefore requires "no mutable object aliasing between learner
    and history", and this class holds SERIALIZED BYTES rather than tensors, so aliasing is not
    merely avoided — it is impossible.
    """

    label: str
    period: int
    blob: bytes = field(repr=False)
    sha256: str = ""

    @staticmethod
    def freeze(model, label: str, period: int) -> "HistoricalPolicy":
        b = _state_bytes(model.state_dict())
        return HistoricalPolicy(label=label, period=period, blob=b,
                                sha256=hashlib.sha256(b).hexdigest())

    def verify(self) -> bool:
        return hashlib.sha256(self.blob).hexdigest() == self.sha256

    def load_into(self, model):
        buf = io.BytesIO(self.blob)
        model.load_state_dict(torch.load(buf, map_location="cpu", weights_only=False))
        return model


class OSFP:
    """Optimistic Smooth Fictitious Play, as the ByteRL papers describe it.

    `MANDATORY_IMPLEMENTATION B5`:

      * immutable historical policies                     -> `HistoricalPolicy` (bytes)
      * self-play probability 0.6                         -> `sample_opponent`
      * period-local payoff and count accumulators        -> `G`, `C`, reset by `reset_period`
      * promotion threshold 0.55                          -> `should_promote`
      * forced promotion after six periods without one    -> `should_promote`
      * frozen evaluation checkpoint per promotion        -> `promote`

    Period-locality is the detail the Hearthstone paper is explicit about and the one c019 and
    c020 both got wrong: `G` and `C` accumulate WITHIN the current learning period and are reset
    on promotion, so the meta-strategy tracks who is beating the CURRENT policy rather than a
    lifetime average that can never change.
    """

    def __init__(self, max_history: int = 16, eta: float = 0.1,
                 selfplay_prob: float = OSFP_SELFPLAY_PROB,
                 promotion_threshold: float = OSFP_PROMOTION_THRESHOLD,
                 max_periods_without_promotion: int = OSFP_MAX_PERIODS_WITHOUT_PROMOTION):
        self.max_history = int(max_history)
        self.eta = float(eta)
        self.selfplay_prob = float(selfplay_prob)
        self.promotion_threshold = float(promotion_threshold)
        self.max_periods_without_promotion = int(max_periods_without_promotion)
        self.history: List[HistoricalPolicy] = []
        self.period = 0
        self.periods_without_promotion = 0
        self.G: List[float] = []
        self.C: List[int] = []
        self.promotions: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- population
    def promote(self, model, label: Optional[str] = None) -> HistoricalPolicy:
        """Freeze the current weights into history and start a new period."""
        hp = HistoricalPolicy.freeze(model, label or f"period{self.period}", self.period)
        self.history.append(hp)
        if len(self.history) > self.max_history:
            # Evicting the OLDEST is a choice, not a paper statement; recorded in
            # UNRESOLVED_REFERENCE_CHOICES with the alternative (reservoir sampling) and a
            # sensitivity test. Whatever is evicted, what remains is still byte-immutable.
            self.history.pop(0)
        self.promotions.append({"period": self.period, "label": hp.label,
                                "sha256": hp.sha256, "history_size": len(self.history)})
        self.period += 1
        self.periods_without_promotion = 0
        self.reset_period()
        return hp

    def reset_period(self):
        """Period-local accumulators. Reset on every promotion (B15)."""
        self.G = [0.0] * len(self.history)
        self.C = [0] * len(self.history)

    def record(self, opponent_index: int, payoff: float):
        if opponent_index is None or opponent_index < 0:
            return                      # self-play games do not score a historical opponent
        while len(self.G) < len(self.history):
            self.G.append(0.0)
            self.C.append(0)
        if opponent_index < len(self.G):
            self.G[opponent_index] += float(payoff)
            self.C[opponent_index] += 1

    def mean_payoff(self, i: int) -> float:
        return (self.G[i] / self.C[i]) if (i < len(self.C) and self.C[i] > 0) else 0.0

    def opponent_distribution(self) -> np.ndarray:
        """sigma ∝ exp(-mean_payoff / eta): weight the opponents we are LOSING to.

        Uniform before any game in a period, which is what makes the meta-strategy optimistic:
        a newly promoted opponent is played before there is evidence about it.
        """
        n = len(self.history)
        if n == 0:
            return np.zeros(0)
        if not any(c > 0 for c in self.C[:n]):
            return np.ones(n) / n
        m = np.array([self.mean_payoff(i) for i in range(n)], dtype=np.float64)
        w = np.exp(-(m - m.min()) / max(self.eta, 1e-6))
        s = w.sum()
        return (w / s) if s > 0 else np.ones(n) / n

    def sample_opponent(self, rng) -> Optional[int]:
        """`None` means self-play. Self-play probability is 0.6 (FIDELITY_RULES §4)."""
        if not self.history or rng.random() < self.selfplay_prob:
            return None
        d = self.opponent_distribution()
        return int(rng.choice(len(d), p=d))

    def should_promote(self, win_rate: float, games: int, min_games: int = 32) -> Tuple[bool, str]:
        """Threshold 0.55, or forced after six periods without promotion."""
        if games >= min_games and win_rate >= self.promotion_threshold:
            return True, f"win_rate {win_rate:.3f} >= {self.promotion_threshold}"
        if self.periods_without_promotion >= self.max_periods_without_promotion:
            return True, (f"forced: {self.periods_without_promotion} periods without promotion "
                          f">= {self.max_periods_without_promotion}")
        return False, f"win_rate {win_rate:.3f} < {self.promotion_threshold}"

    def end_period_without_promotion(self):
        self.periods_without_promotion += 1

    # ---------------------------------------------------------------- evidence
    def verify_history_immutable(self) -> Dict[str, Any]:
        """B16. Every frozen checkpoint must still hash to what it hashed at freeze time."""
        rows = [{"label": h.label, "period": h.period, "sha256": h.sha256, "ok": h.verify()}
                for h in self.history]
        return {"n": len(rows), "all_ok": all(r["ok"] for r in rows), "checkpoints": rows}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "history_size": len(self.history),
            "periods_without_promotion": self.periods_without_promotion,
            "selfplay_prob": self.selfplay_prob,
            "promotion_threshold": self.promotion_threshold,
            "max_periods_without_promotion": self.max_periods_without_promotion,
            "G": list(self.G), "C": list(self.C),
            "mean_payoffs": [round(self.mean_payoff(i), 4) for i in range(len(self.history))],
            "distribution": [round(float(x), 4) for x in self.opponent_distribution()],
            "promotions": list(self.promotions),
            "history_sha256": [h.sha256 for h in self.history],
        }
