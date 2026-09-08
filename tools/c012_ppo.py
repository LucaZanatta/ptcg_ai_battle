"""c012 §7/§21 — the exact c011 PPO update, with the minibatch permutation drawn from the
LIVE Generator rather than supplied precomputed.

The mathematics is c011's, unchanged (§21 forbids changing PPO mathematics). The only
difference is where the permutation comes from: `c011_torch_ppo.ppo_update_torch` accepts an
`orders=` argument so parity tests could pin it, and c011's continuation test used that. §7
declares such a test insufficient, because pinning the permutation hides exactly the RNG
divergence the test is supposed to detect.

Here the update consumes `rng` directly, so the permutation is part of the stochastic stream
that must survive save/restore. The returned diagnostics include the permutations actually
used, so a continuation test can compare them.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c011_torch_ppo as tp  # noqa: E402  (c011 backend reused verbatim)
from cg import ppo as legacy_ppo  # noqa: E402


def draw_orders(rng: np.random.Generator, n: int, epochs: int) -> List[np.ndarray]:
    """Per-epoch permutations drawn from the live Generator, mirroring the legacy loop's
    `rng.shuffle(order)` on a persistent array."""
    order = np.arange(n)
    out = []
    for _ in range(epochs):
        rng.shuffle(order)
        out.append(order.copy())
    return out


def ppo_update(model, games, cfg: Dict[str, Any], opt, entropy_coef: float,
               rng: np.random.Generator, device: str = "cuda") -> Dict[str, Any]:
    """One registered PPO update. Identical math to c011; permutation from `rng`."""
    flat = legacy_ppo.compute_gae(games, cfg["gamma"], cfg["lam"])
    if not flat:
        return {"n_decisions": 0, "skipped": True, "orders_digest": None}
    orders = draw_orders(rng, len(flat), cfg["epochs"])
    diag = tp.ppo_update_torch(model, games, cfg, opt, entropy_coef, orders=orders,
                               device=device, flat=flat)
    # compact fingerprint of the permutations, so continuation tests can compare them
    diag["orders_digest"] = [int(o[:8].sum()) for o in orders]
    diag["orders_first8"] = [o[:8].tolist() for o in orders]
    return diag
