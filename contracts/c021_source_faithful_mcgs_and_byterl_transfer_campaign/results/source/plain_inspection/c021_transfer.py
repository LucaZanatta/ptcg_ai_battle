"""c021 — the transfer lab: ByteRL components moved into MCGS, ONE AT A TIME.

The contract requires transfer tests that start with policy priors and change exactly one thing
per arm, so any change in strength is attributable. It also forbids an uncontrolled full hybrid
and forbids adding a third method. So this module defines a small, closed set of arms:

    T0  MCGS_2019_OFFICIAL_SOURCE_PORT, unchanged                  (the control)
    T1  ByteRL policy orders EXPANSION among untested actions      (the policy prior)
    T2  ByteRL policy drives the ROLLOUT instead of uniform random  (the default policy)
    T3  T1 + T2 together                                            (the only combination arm)

What is deliberately NOT here, because `FIDELITY_RULES §3` forbids it in the primary branch:

  * no neural value replacing the rollout return -- that is the handcrafted-leaf-evaluator
    substitution c020 made;
  * no baseline override gate on the search's chosen move;
  * no PUCT prior term added to `Edge.Value`. MCGS selection is UCB1. T1 changes the ORDER in
    which untested actions are expanded, which is `Node.TreePolicy`'s uniform-random draw --
    a documented, separable component -- and leaves the selection formula untouched.

T1 is the honest reading of "policy prior" for a UCB1 searcher: it decides what gets tried first
under a finite budget, which is exactly what a prior is for, without smuggling PUCT into a method
the contract requires to remain UCB1.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

ARMS = {
    "T0_control":          {"expansion_prior": False, "rollout_policy": False},
    "T1_policy_prior":     {"expansion_prior": True,  "rollout_policy": False},
    "T2_rollout_policy":   {"expansion_prior": False, "rollout_policy": True},
    "T3_prior_and_rollout": {"expansion_prior": True, "rollout_policy": True},
}


class ByteRLPriorProvider:
    """Wraps a trained ByteRL network so MCGS can query it for option scores.

    The provider is DEFENSIVE by construction: any failure returns None and the search falls
    straight back to its source behaviour. A transfer arm that silently degrades to the control
    on error would report the control's score under the arm's name.
    """

    def __init__(self, checkpoint_path: str, pool=None, device: str = "cpu",
                 temperature: float = 1.0):
        import torch
        from cg import c021_byterl_deck as DK
        from cg import c021_byterl_encode as EN
        from cg import c021_byterl_model as M

        self.torch = torch
        self.EN = EN
        self.M = M
        self.device = device
        self.temperature = temperature
        self.pool = pool or DK.CardPool.from_archetypes()
        dims = EN.dims()
        state = torch.load(checkpoint_path, map_location=device, weights_only=True)
        width = int(state["global_proj.weight"].shape[0])
        blocks = len({k.split(".")[1] for k in state if k.startswith("torso.")})
        self.net = M.ByteRLNet(dims["global_dim"], dims["slot_dim"], dims["option_dim"],
                               self.pool.size(), width=width, blocks=blocks)
        self.net.load_state_dict(state)
        self.net.eval()
        self.checkpoint = checkpoint_path
        self.calls = 0
        self.failures = 0

    def option_scores(self, observation, n_options: int) -> Optional[np.ndarray]:
        """Probabilities over the first `n_options` legal options, or None on any failure."""
        self.calls += 1
        try:
            enc = self.EN.encode_battle(observation, None, None)
            n = min(int(enc["n_options"]), n_options)
            if n <= 0:
                self.failures += 1
                return None
            tt = self.EN.to_torch(enc, self.device)
            legal = tt["opt_mask"].clone()
            legal[:, n:] = 0.0
            with self.torch.no_grad():
                h = self.net.encode(tt["global"], tt["board"], tt["roles"], tt["indices"],
                                    tt["sides"], tt["stage"])
                logits = self.net.battle_logits(h, tt["opt"]) / max(self.temperature, 1e-6)
                lp = self.M.masked_log_softmax(logits, legal)
                p = lp.exp()[0].cpu().numpy().astype(np.float64)
            p = p[:n_options]
            if not np.isfinite(p).all() or p.sum() <= 0:
                self.failures += 1
                return None
            return p / p.sum()
        except Exception:  # noqa: BLE001
            self.failures += 1
            return None

    def stats(self) -> Dict[str, Any]:
        return {"checkpoint": os.path.basename(self.checkpoint),
                "calls": self.calls, "failures": self.failures,
                "failure_rate": round(self.failures / max(1, self.calls), 4),
                "temperature": self.temperature}


def sample_untested(rng, provider, node, arm: Dict[str, bool],
                    stats: Dict[str, Any]) -> int:
    """T1. Choose WHICH untested action to expand.

    Source behaviour (`Node.TreePolicy`) is a uniform random draw from `UntestedActionIndices`.
    Under T1 the ByteRL policy supplies the distribution instead, restricted to the untested set
    and renormalised. Every action still gets expanded eventually -- the prior changes the ORDER,
    which under a finite budget is what decides which lines get searched at all.
    """
    untested = node.untested_action_indices
    if not untested:
        return -1
    if not arm.get("expansion_prior") or provider is None or node.obs is None:
        return int(rng.integers(len(untested)))
    p_all = provider.option_scores(node.obs, len(node.legal_options))
    if p_all is None:
        stats["transfer_prior_fallbacks"] = stats.get("transfer_prior_fallbacks", 0) + 1
        return int(rng.integers(len(untested)))
    p = np.asarray([p_all[i] if i < len(p_all) else 0.0 for i in untested], dtype=np.float64)
    if p.sum() <= 0:
        stats["transfer_prior_fallbacks"] = stats.get("transfer_prior_fallbacks", 0) + 1
        return int(rng.integers(len(untested)))
    stats["transfer_prior_used"] = stats.get("transfer_prior_used", 0) + 1
    return int(rng.choice(len(untested), p=p / p.sum()))


def rollout_pick(rng, provider, obs, opts, arm: Dict[str, bool],
                 stats: Dict[str, Any]) -> int:
    """T2. Choose the rollout action.

    Source behaviour is `UniformRandomRollout`. Under T2 the ByteRL policy plays the rollout.
    This replaces the DEFAULT POLICY, which the source treats as a pluggable component
    (`src/DefaultPolicy/Policy.cs`), and does not touch selection, expansion or backup. It is
    still a rollout to a real terminal -- NOT a neural value substituted for one, which is the
    substitution FIDELITY_RULES forbids.
    """
    # THROUGHPUT NOTE, recorded before the arm is run so its result is not misread. A network
    # forward per rollout step is expensive: rollouts run ~1800 steps per decision, so T2 spends
    # its entire per-decision budget on far fewer simulations than T0. The wall clock is bounded
    # either way -- the budget caps it -- but a weaker T2 field score may reflect SIMULATION
    # STARVATION rather than a worse default policy. `sims_per_decision` distinguishes the two
    # and must be read alongside the score.
    if not arm.get("rollout_policy") or provider is None or obs is None:
        return int(rng.integers(len(opts)))
    p = provider.option_scores(obs, len(opts))
    if p is None or p.sum() <= 0:
        stats["transfer_rollout_fallbacks"] = stats.get("transfer_rollout_fallbacks", 0) + 1
        return int(rng.integers(len(opts)))
    stats["transfer_rollout_used"] = stats.get("transfer_rollout_used", 0) + 1
    return int(rng.choice(len(p), p=p))


def arm_config(name: str) -> Dict[str, bool]:
    if name not in ARMS:
        raise ValueError(f"unknown transfer arm {name!r}; known: {sorted(ARMS)}")
    return dict(ARMS[name])
