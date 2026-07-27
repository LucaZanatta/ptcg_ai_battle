"""c020 B5 — V-trace and UPGO over COMPLETE JOINT action probabilities.

The c019 audit does not fault the V-trace mathematics (#11 is about the inputs, not the recursion)
and c019's implementation was verified against hand-computed fixtures. So the recursion is reused
from `c019_vtrace` deliberately — reimplementing verified math would add risk without adding
correctness — and c020's contribution is the part that was wrong:

  * `rho_t = exp(target_joint_logp_t - behavior_joint_logp_t)` where BOTH are joint log
    probabilities over the complete multi-select action (audit #9), and
  * both are computed under the SAME observation, legal mask and recurrent state (audit #11).

`assert_same_context` makes the second condition checkable rather than assumed: the learner passes
the context fingerprint the actor recorded, and a mismatch raises instead of silently producing a
plausible-looking ratio.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_vtrace as V19  # noqa: E402

# registered source values (arXiv 2303.05197 Table III), unchanged in c020
GAMMA = 1.0
RHO_LOWER, RHO_UPPER = V19.RHO_LOWER, V19.RHO_UPPER
C_LOWER, C_UPPER = V19.C_LOWER, V19.C_UPPER
PPO_EPS = 0.2

vtrace_reference = V19.vtrace_reference
upgo_reference = V19.upgo_reference
vtrace_torch = V19.vtrace_torch
upgo_torch = V19.upgo_torch
ppo_clipped_policy_loss = V19.ppo_clipped_policy_loss


class RecurrentContextMismatch(Exception):
    """Raised when target and behavior probabilities would be compared under different state."""


def assert_same_context(behavior_ctx: List[str], target_ctx: List[str]) -> None:
    """B5/audit #11: the two policies must be evaluated in the SAME recurrent context.

    The actor records a fingerprint per timestep (observation hash + mask hash + h0/c0 hash of the
    unroll it belongs to). The learner recomputes it during replay. If they differ, the importance
    ratio is meaningless and the update is refused rather than applied.
    """
    if len(behavior_ctx) != len(target_ctx):
        raise RecurrentContextMismatch(
            f"context length {len(behavior_ctx)} != {len(target_ctx)}")
    bad = [i for i, (a, b) in enumerate(zip(behavior_ctx, target_ctx)) if a != b]
    if bad:
        raise RecurrentContextMismatch(
            f"{len(bad)} timesteps replayed under a different recurrent context, first at {bad[0]}")


def losses(target_joint_logp: torch.Tensor, behavior_joint_logp: torch.Tensor,
           values: torch.Tensor, bootstrap_value: torch.Tensor,
           rewards: torch.Tensor, discounts: torch.Tensor, entropy: torch.Tensor,
           vf_coef: float = 0.5, ent_coef: float = 0.01,
           upgo_coef: float = 1.0) -> Dict[str, torch.Tensor]:
    """Full objective. Inputs are JOINT log probabilities of complete actions (B3/B5)."""
    return V19.losses(target_joint_logp, behavior_joint_logp, values, bootstrap_value,
                      rewards, discounts, entropy,
                      weights={"policy": 1.0, "upgo": upgo_coef, "value": vf_coef,
                               "entropy": ent_coef})


# ------------------------------------------------------------------ B5 fixtures

def fixture_single_action() -> Dict[str, Any]:
    b = np.array([-0.7, -1.2, -0.4])
    t = np.array([-0.5, -1.5, -0.4])
    r = np.array([0.0, 0.0, 1.0])
    v = np.array([0.1, 0.2, 0.3])
    d = np.array([1.0, 1.0, 0.0])
    out = vtrace_reference(b, t, v, 0.0, r, d)
    return {"name": "single_action", "behavior_logp": b.tolist(), "target_logp": t.tolist(),
            "rho": out["rho"].tolist(), "vs": out["vs"].tolist(),
            "pg_advantage": out["pg_advantage"].tolist()}


def fixture_multiselect_joint() -> Dict[str, Any]:
    """The fixture c019 could not have produced: joint probabilities of 2- and 3-pick actions.

    Step probabilities are multiplied, so the joint log probability is the SUM of the per-pick log
    probabilities. Storing only pick 1 (audit #9) would give the first column alone, and the
    resulting ratio would be wrong by the product of the remaining picks.
    """
    steps_b = [[-0.4, -0.9], [-0.3, -0.7, -1.1], [-0.5]]
    steps_t = [[-0.6, -0.8], [-0.2, -0.9, -1.0], [-0.4]]
    b = np.array([sum(s) for s in steps_b])
    t = np.array([sum(s) for s in steps_t])
    first_only_b = np.array([s[0] for s in steps_b])
    first_only_t = np.array([s[0] for s in steps_t])
    r = np.array([0.0, 0.0, -1.0])
    v = np.array([0.05, -0.1, 0.2])
    d = np.array([1.0, 1.0, 0.0])
    joint = vtrace_reference(b, t, v, 0.0, r, d)
    frag = vtrace_reference(first_only_b, first_only_t, v, 0.0, r, d)
    return {"name": "multiselect_joint",
            "per_step_behavior": steps_b, "per_step_target": steps_t,
            "joint_behavior_logp": b.tolist(), "joint_target_logp": t.tolist(),
            "joint_rho": joint["rho"].tolist(), "joint_vs": joint["vs"].tolist(),
            "first_pick_only_rho": frag["rho"].tolist(),
            "first_pick_only_vs": frag["vs"].tolist(),
            "differs_from_first_pick_only": bool(
                np.abs(joint["vs"] - frag["vs"]).max() > 1e-9),
            "note": "c019 stored the first pick only; these two rows show the resulting targets "
                    "are numerically different, so the c019 ratio was wrong wherever k > 1"}


def fixture_terminal_sequence() -> Dict[str, Any]:
    b = np.array([-0.3, -0.3])
    t = np.array([-0.3, -0.3])
    r = np.array([0.0, 1.0])
    v = np.array([0.0, 0.0])
    d = np.array([1.0, 0.0])            # terminal: discount 0 at the last step
    out = vtrace_reference(b, t, v, 0.0, r, d)
    return {"name": "terminal_sequence", "vs": out["vs"].tolist(),
            "on_policy_rho_is_one": bool(np.allclose(out["rho"], 1.0)),
            "vs_equals_return": bool(abs(out["vs"][0] - 1.0) < 1e-9)}


def fixture_truncated_unroll() -> Dict[str, Any]:
    """A mid-game unroll that does NOT end the episode: bootstrap value must carry the tail."""
    b = np.array([-0.5, -0.5, -0.5])
    t = np.array([-0.5, -0.5, -0.5])
    r = np.array([0.0, 0.0, 0.0])
    v = np.array([0.2, 0.2, 0.2])
    d = np.array([1.0, 1.0, 1.0])       # NOT terminal
    out = vtrace_reference(b, t, v, 0.42, r, d)
    return {"name": "truncated_unroll", "bootstrap_value": 0.42,
            "vs": out["vs"].tolist(),
            "carries_bootstrap": bool(abs(out["vs"][-1] - 0.42) < 1e-6)}


def fixture_clipping_bounds() -> Dict[str, Any]:
    b = np.array([-5.0, 0.0])
    t = np.array([0.0, -5.0])           # huge ratio, then tiny ratio
    r = np.array([0.0, 0.0])
    v = np.array([0.0, 0.0])
    d = np.array([1.0, 1.0])
    out = vtrace_reference(b, t, v, 0.0, r, d)
    return {"name": "clipping_bounds", "raw_rho": np.exp(t - b).tolist(),
            "clipped_rho": np.clip(np.exp(t - b), RHO_LOWER, RHO_UPPER).tolist(),
            "bounds": [RHO_LOWER, RHO_UPPER],
            "upper_binds": bool(np.exp(t - b)[0] > RHO_UPPER),
            "lower_binds": bool(np.exp(t - b)[1] < RHO_LOWER)}


def fixture_upgo() -> Dict[str, Any]:
    t = np.array([-0.4, -0.4, -0.4])
    v = np.array([0.1, 0.5, 0.2])
    r = np.array([0.0, 0.0, 1.0])
    d = np.array([1.0, 1.0, 0.0])
    out = upgo_reference(t, v, 0.0, r, d)
    return {"name": "upgo_recursion", "returns": out["returns"].tolist(),
            "advantage": out["advantage"].tolist(),
            "nonzero": bool(np.abs(out["advantage"]).max() > 0)}


def all_fixtures() -> List[Dict[str, Any]]:
    return [fixture_single_action(), fixture_multiselect_joint(), fixture_terminal_sequence(),
            fixture_truncated_unroll(), fixture_clipping_bounds(), fixture_upgo()]
