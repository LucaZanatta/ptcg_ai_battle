"""c018 M04 — learned guidance inside the SAME real search tree.

Two uses of the trained model, and only two:

  * **ordering** — one forward on the root observation ranks the live options, deciding which of
    them fit inside the candidate budget. It never prunes the baseline and never picks the
    answer; the winner is still whichever candidate the *real* successors score highest.
  * **leaf value** — one batched forward over all candidate leaves replaces the hand-written
    `leaf_value` heuristic.

Both are deliberately cheap: two forwards per decision, not one per node. A per-node model call
sits in the innermost loop of a beam search and would spend the entire 2500 ms budget on
inference. Because the tree is byte-identical guided or unguided, a guided/unguided comparison
(P15) isolates the guidance instead of confounding it with a different searcher.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from typing import Any, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

KMAX = 32
FEAT_KEYS = ("global", "board_rows", "board_dyn", "hand_rows", "hand_dyn", "hand_mask",
             "disc_rows", "disc_mask", "opt_dense", "opt_rows")


class Guide:
    """Learned ordering + learned leaf values, backed by the numpy RLPolicy.

    The numpy backend is deliberate: search runs inside the game loop in a rollout worker, and
    initialising CUDA per worker would cost more than the forwards save.
    """

    def __init__(self, npz_path: str, leaf_scale: float = 1.0,
                 use_learned_leaf: bool = True):
        from cg.rl_policy import RLPolicy
        self.pol = RLPolicy.load(npz_path)
        self.path = npz_path
        self.leaf_scale = leaf_scale
        # P10 measured the value head losing to a constant baseline (MSE 0.267 vs 0.216,
        # correlation 0.146). Ordering and leaf valuation are therefore separable questions,
        # and a single "guided" candidate would confound a possibly-useful policy ordering
        # with a measurably weak value head.
        self.use_learned_leaf = use_learned_leaf
        self.provides_leaf_values = use_learned_leaf
        self.stats = {"order_calls": 0, "order_failed": 0, "leaf_calls": 0,
                      "leaf_rows_ok": 0, "leaf_rows_failed": 0, "leaf_skipped": 0}

    # ---------------------------------------------------------------- featurization
    @staticmethod
    def _encode(obs_dict) -> Optional[dict]:
        from cg import state_encoder_v2 as enc
        from cg.episode_capture import normalize_observation
        fd = enc.encode(normalize_observation(obs_dict)[0], None)
        out = {}
        for k in FEAT_KEYS:
            v = np.asarray(fd[k])
            if k in ("opt_dense", "opt_rows"):
                pad = np.zeros((KMAX,) + v.shape[1:], dtype=v.dtype)
                m = min(KMAX, v.shape[0])
                pad[:m] = v[:m]
                v = pad
            out[k] = v
        out["_n_opt"] = min(KMAX, int(np.asarray(fd["opt_dense"]).shape[0]))
        return out

    @staticmethod
    def _obs_to_dict(observation) -> Any:
        """Search successors arrive as `Observation` dataclasses; the encoder wants the dict
        form the live agent sees. `asdict` is the exact inverse of `to_observation_class`."""
        return dataclasses.asdict(observation)

    def _batch(self, rows: List[dict]) -> dict:
        b = {k: np.asarray([r[k] for r in rows]) for k in FEAT_KEYS}
        n = np.asarray([r["_n_opt"] for r in rows])
        b["opt_mask"] = (np.arange(KMAX)[None, :] < n[:, None]).astype(np.float64)
        return b

    # ---------------------------------------------------------------- guidance
    def order(self, obs, n_opt: int) -> List[int]:
        """Option indices ranked best-first by the learned policy."""
        self.stats["order_calls"] += 1
        try:
            r = self._encode(obs)
        except Exception:  # noqa: BLE001
            self.stats["order_failed"] += 1
            return list(range(n_opt))
        scores, _v, _c = self.pol.forward(self._batch([r]))
        s = np.asarray(scores.data if hasattr(scores, "data") else scores).reshape(-1)
        k = min(n_opt, KMAX)
        ranked = list(np.argsort(-s[:k]))
        # options beyond K_MAX are unscored, so they keep their natural order at the back
        return [int(i) for i in ranked] + list(range(k, n_opt))

    def leaf_values(self, leaves: List[Any], your_index: int) -> List[Optional[float]]:
        """Value-head estimate for each candidate leaf; None where featurization fails."""
        if not self.use_learned_leaf:
            self.stats["leaf_skipped"] += 1
            return [None] * len(leaves)
        self.stats["leaf_calls"] += 1
        rows, slots = [], []
        for i, lf in enumerate(leaves):
            if lf is None:
                continue
            try:
                rows.append(self._encode(self._obs_to_dict(lf)))
                slots.append(i)
            except Exception:  # noqa: BLE001
                self.stats["leaf_rows_failed"] += 1
        out: List[Optional[float]] = [None] * len(leaves)
        if not rows:
            return out
        _s, val, _c = self.pol.forward(self._batch(rows))
        v = np.asarray(val.data if hasattr(val, "data") else val).reshape(-1)
        for j, i in enumerate(slots):
            # value head is trained on win/draw/loss in [0,1]; the beam ranks in [-1,1]
            out[i] = float(np.clip((v[j] - 0.5) * 2.0 * self.leaf_scale, -1.0, 1.0))
            self.stats["leaf_rows_ok"] += 1
        return out
