"""c021 B4 — observation encoding for ByteRL, adapting the c020 slot-aware featurizer.

The c020 encoder is reused deliberately: its option references were repaired in c020 (they had
been scraping integers from the top level of a canonical key while the references lived in a
nested tuple, so 0/556 resolved), and re-deriving it would discard a verified component. What
this module adds is what c021 needs and c020 did not have:

  * **Slot role / index / side tensors** for `SlotEncoder`, so the network sees active and bench
    as DISTINCT roles rather than as twelve interchangeable rows.
  * **A raised option cap with an explicit truncation counter.** c020 capped at 40 options and
    said nothing when a select exceeded it; a truncated option is a legal action the policy can
    never take, and silently dropping it is the difference between "the policy did not choose it"
    and "the policy could not". Every truncation is counted and reported.
  * **Construction-stage encoding** on the same tensors, carrying the stage flag (B2).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c020_byterl_encode as E20  # noqa: E402
from cg import c021_byterl_deck as DK  # noqa: E402

BENCH_SLOTS = E20.BENCH_SLOTS
BOARD_SLOTS = E20.BOARD_SLOTS
BOARD_DIM = E20.BOARD_DIM
GLOBAL_DIM = E20.GLOBAL_DIM
OPT_DIM = E20.OPT_DIM
HAND_DIM = E20.HAND_DIM

# c020 used 40. Raised so ordinary PTCG selects are never clipped; overflow is still counted.
MAX_OPTIONS = 128

STAGE_BATTLE = 0
STAGE_CONSTRUCTION = 1

# Slot role tokens. These are the tokens c020 did not have.
ROLE_ACTIVE, ROLE_BENCH = 0, 1
SIDE_MINE, SIDE_THEIRS = 0, 1


def slot_layout() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fixed (role, index, side) for the 12 board positions, matching `_board_list` order.

    Order is: my active, my bench 0..4, opponent active, opponent bench 0..4.
    """
    roles, indices, sides = [], [], []
    for side in (SIDE_MINE, SIDE_THEIRS):
        roles.append(ROLE_ACTIVE); indices.append(0); sides.append(side)
        for b in range(BENCH_SLOTS):
            roles.append(ROLE_BENCH); indices.append(b + 1); sides.append(side)
    return (np.asarray(roles, dtype=np.int64),
            np.asarray(indices, dtype=np.int64),
            np.asarray(sides, dtype=np.int64))


ROLES, INDICES, SIDES = slot_layout()


class EncodeStats:
    """Counts what the encoder had to drop. Silent truncation is the thing being prevented."""

    def __init__(self):
        self.encodes = 0
        self.option_truncations = 0
        self.options_dropped = 0
        self.max_options_seen = 0

    def as_dict(self) -> Dict[str, int]:
        return {"encodes": self.encodes, "option_truncations": self.option_truncations,
                "options_dropped": self.options_dropped,
                "max_options_seen": self.max_options_seen}


def encode_battle(observation, your_index: Optional[int] = None,
                  stats: Optional[EncodeStats] = None) -> Dict[str, np.ndarray]:
    """Battle-stage encoding: c020 tensors plus slot identity and an honest option cap."""
    from cg import c019_core as K
    base = E20.encode(observation, your_index)

    sel = getattr(observation, "select", None)
    refs = E20.option_refs(observation, your_index) if sel is not None else []
    n_all = len(refs)
    n = min(n_all, MAX_OPTIONS)
    if stats is not None:
        stats.encodes += 1
        stats.max_options_seen = max(stats.max_options_seen, n_all)
        if n_all > MAX_OPTIONS:
            stats.option_truncations += 1
            stats.options_dropped += n_all - MAX_OPTIONS

    ot = np.zeros((MAX_OPTIONS, OPT_DIM), dtype=np.float32)
    mask = np.zeros(MAX_OPTIONS, dtype=np.float32)
    src = np.full(MAX_OPTIONS, BOARD_SLOTS, dtype=np.int64)
    tgt = np.full(MAX_OPTIONS, BOARD_SLOTS, dtype=np.int64)
    for i, r in enumerate(refs[:MAX_OPTIONS]):
        ot[i] = r.features()
        if r.source_index >= 0:
            src[i] = r.source_index
        if r.target_index >= 0:
            tgt[i] = r.target_index
        mask[i] = 1.0

    return {"board": base["board"], "global": base["global"],
            "roles": ROLES, "indices": INDICES, "sides": SIDES,
            "opt": ot, "opt_mask": mask, "opt_src": src, "opt_tgt": tgt,
            "n_options": np.int64(n), "n_options_true": np.int64(n_all),
            "min_count": base["min_count"], "max_count": base["max_count"],
            "stage": np.int64(STAGE_BATTLE)}


def encode_construction(partial: List[int], pool: DK.CardPool) -> Dict[str, np.ndarray]:
    """Construction-stage encoding on the SAME tensor shapes, with the stage flag set.

    The board is empty during construction; zeroing it rather than inventing a synthetic board
    keeps the two stages on one network without leaking fake battle state into the torso.
    """
    feats = DK.construction_features(partial, pool)
    g = np.zeros(GLOBAL_DIM, dtype=np.float32)
    src = feats["global"]
    g[:min(len(src), GLOBAL_DIM)] = src[:GLOBAL_DIM]
    return {"board": np.zeros((BOARD_SLOTS, BOARD_DIM), dtype=np.float32),
            "global": g, "roles": ROLES, "indices": INDICES, "sides": SIDES,
            "pool_mask": feats["mask"], "chosen": feats["chosen"],
            "stage": np.int64(STAGE_CONSTRUCTION)}


def to_torch(enc: Dict[str, np.ndarray], device: str = "cpu"):
    """Batch of one, as the actor needs it."""
    import torch
    out = {}
    for k, v in enc.items():
        if isinstance(v, np.ndarray):
            t = torch.from_numpy(np.ascontiguousarray(v))
            out[k] = t.unsqueeze(0).to(device)
        else:
            out[k] = torch.tensor([int(v)], device=device)
    return out


def dims() -> Dict[str, int]:
    return {"global_dim": GLOBAL_DIM, "slot_dim": BOARD_DIM, "option_dim": OPT_DIM,
            "board_slots": BOARD_SLOTS, "max_options": MAX_OPTIONS,
            "bench_slots": BENCH_SLOTS}
