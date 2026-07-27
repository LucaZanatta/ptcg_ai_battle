"""c019 Branch B — PTCG visible token encoder for ByteRL.

METHOD_FIDELITY B: canonicalize to CURRENT-PLAYER perspective, encode visible cards/zones/board/
global state and the current select context, and encode each currently legal option so the
scorer can rank a dynamic option set.

Every state read goes through `c019_core.VisibleObservation`, which raises on a hidden zone.
CONTRACT §7: "The ByteRL branch must never receive hidden sampled state as observation." That is
enforced structurally here rather than promised — the encoder cannot see opponent hand contents,
deck contents/order, or unrevealed prize IDs even if a caller wanted it to.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

ENCODER_VERSION = "c019.byterl.enc.v1"

# zone capacities -- fixed so tensors are static-shaped for the recurrent learner
N_HAND = 12
N_BOARD = 6          # active + up to 5 bench, per side
N_DISCARD = 16
N_OPT = 32           # legal options scored per decision; overflow is disclosed, not hidden

CARD_DYN = 10        # per-card dynamic scalars
GLOBAL_DIM = 32
OPT_DIM = 24

_VOCAB = None
_FEAT = None


def _vocab():
    global _VOCAB, _FEAT
    if _VOCAB is None:
        from cg import card_vocab
        v = card_vocab.build_vocab()
        _VOCAB = v
        _FEAT = np.asarray(v["feature_matrix"], dtype=np.float32)
    return _VOCAB, _FEAT


def vocab_size() -> int:
    return _vocab()[0]["vocab_size"]


def card_feature_dim() -> int:
    return int(_vocab()[1].shape[1])


def _row_index(card) -> int:
    v, _ = _vocab()
    if card is None:
        return 0
    cid = getattr(card, "id", None)
    idx = v.get("index") or v.get("id_to_index") or {}
    try:
        return int(idx.get(int(cid), 0))
    except (TypeError, ValueError):
        return 0


def _card_dyn(card) -> np.ndarray:
    """Dynamic per-card scalars: HP/damage/energy/status/tools/stage/position."""
    d = np.zeros(CARD_DYN, dtype=np.float32)
    if card is None:
        return d
    hp = float(getattr(card, "hp", 0) or 0)
    mx = float(getattr(card, "maxHp", 0) or 0)
    d[0] = hp / 340.0
    d[1] = mx / 340.0
    d[2] = (mx - hp) / 340.0                      # damage taken
    d[3] = (hp / mx) if mx > 0 else 0.0           # health fraction
    en = getattr(card, "energyCards", None) or getattr(card, "energies", None) or []
    d[4] = min(len(en), 8) / 8.0
    d[5] = min(len(getattr(card, "toolCards", None) or
                   ([getattr(card, "toolCard", None)] if getattr(card, "toolCard", None)
                    else [])), 3) / 3.0
    sc = getattr(card, "specialConditions", None) or []
    d[6] = min(len(sc), 4) / 4.0
    d[7] = float(bool(getattr(card, "basic", False)))
    d[8] = min(float(getattr(card, "stage", 0) or 0), 3.0) / 3.0
    d[9] = 1.0                                    # occupancy flag
    return d


def _zone(cards: List[Any], cap: int):
    rows = np.zeros(cap, dtype=np.int64)
    dyn = np.zeros((cap, CARD_DYN), dtype=np.float32)
    mask = np.zeros(cap, dtype=np.float32)
    for i, c in enumerate(cards[:cap]):
        rows[i] = _row_index(c)
        dyn[i] = _card_dyn(c)
        mask[i] = 1.0
    return rows, dyn, mask


def _option_features(o: K.CanonicalOption, ctx: int) -> np.ndarray:
    f = np.zeros(OPT_DIM, dtype=np.float32)
    f[0] = min(o.option_type, 20) / 20.0
    f[1] = min(max(o.select_context, 0), 40) / 40.0
    f[2] = min(max(ctx, 0), 40) / 40.0
    f[3] = float(o.referenced_card_id > 0)
    f[4] = float(o.referenced_attack_id > 0)
    for i, v in enumerate(o.fields[:11]):
        f[5 + i] = 0.0 if v < 0 else min(v, 20) / 20.0
    f[16] = float(o.option_type == 13)            # ATTACK
    f[17] = float(o.option_type == 8)             # ATTACH
    f[18] = float(o.option_type == 7)             # PLAY
    f[19] = float(o.option_type == 12)            # RETREAT
    f[20] = float(o.option_type == 14)            # END/other
    f[21] = float(o.option_type == 3)             # CARD
    f[22] = float(o.option_type in (1, 2))        # YES/NO
    f[23] = 1.0                                   # presence
    return f


def encode(observation, your_index: Optional[int] = None) -> Dict[str, np.ndarray]:
    """Visible observation + legal options -> model tensors, current-player perspective.

    "mine"/"theirs" are resolved through `yourIndex`, so both seats produce the same
    representation of "the player to move" and the network never has to learn seat parity.
    """
    v = K.visible_view(observation, your_index)
    sel = getattr(observation, "select", None)
    ctx = K._iv(getattr(sel, "context", None)) if sel is not None else -1
    opts = K.canonical_options(sel)

    mine = v.board("mine")
    theirs = v.board("theirs")
    my_board = list(mine["active"]) + list(mine["bench"])
    op_board = list(theirs["active"]) + list(theirs["bench"])

    hr, hd, hm = _zone(v.my_hand(), N_HAND)
    br, bd, bm = _zone(my_board, N_BOARD)
    orr, od, om = _zone(op_board, N_BOARD)
    dr, dd, dm = _zone(v.discard("mine"), N_DISCARD)
    er, ed, em = _zone(v.discard("theirs"), N_DISCARD)

    c = v.counts()
    g = np.zeros(GLOBAL_DIM, dtype=np.float32)
    g[0] = c["my_deck"] / 60.0
    g[1] = c["opp_deck"] / 60.0
    g[2] = c["my_hand"] / 12.0
    g[3] = c["opp_hand"] / 12.0
    g[4] = c["my_prize"] / 6.0
    g[5] = c["opp_prize"] / 6.0
    g[6] = (c["opp_prize"] - c["my_prize"]) / 6.0          # prize race, the win condition
    g[7] = len(v.discard("mine")) / 30.0
    g[8] = len(v.discard("theirs")) / 30.0
    g[9] = float(bm.sum()) / N_BOARD
    g[10] = float(om.sum()) / N_BOARD
    g[11] = (float(bm.sum()) - float(om.sum())) / N_BOARD
    if 0 <= ctx < 18:
        g[12 + ctx] = 1.0                                   # one-hot select context
    g[30] = min(len(opts), N_OPT) / N_OPT
    g[31] = 1.0

    od_feat = np.zeros((N_OPT, OPT_DIM), dtype=np.float32)
    o_card = np.zeros(N_OPT, dtype=np.int64)
    o_mask = np.zeros(N_OPT, dtype=np.float32)
    for i, o in enumerate(opts[:N_OPT]):
        od_feat[i] = _option_features(o, ctx)
        o_mask[i] = 1.0
        if o.referenced_card_id > 0:
            class _C:
                id = o.referenced_card_id
            o_card[i] = _row_index(_C())

    return {
        "global": g,
        "hand_rows": hr, "hand_dyn": hd, "hand_mask": hm,
        "board_rows": br, "board_dyn": bd, "board_mask": bm,
        "opp_rows": orr, "opp_dyn": od, "opp_mask": om,
        "disc_rows": dr, "disc_dyn": dd, "disc_mask": dm,
        "odisc_rows": er, "odisc_dyn": ed, "odisc_mask": em,
        "opt_feat": od_feat, "opt_rows": o_card, "opt_mask": o_mask,
        "n_options": np.int64(len(opts)),
        "options_truncated": np.int64(max(0, len(opts) - N_OPT)),
    }


TENSOR_KEYS = ("global", "hand_rows", "hand_dyn", "hand_mask", "board_rows", "board_dyn",
               "board_mask", "opp_rows", "opp_dyn", "opp_mask", "disc_rows", "disc_dyn",
               "disc_mask", "odisc_rows", "odisc_dyn", "odisc_mask", "opt_feat", "opt_rows",
               "opt_mask")
LONG_KEYS = {"hand_rows", "board_rows", "opp_rows", "disc_rows", "odisc_rows", "opt_rows"}


def stack(batch: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    return {k: np.stack([b[k] for b in batch]) for k in TENSOR_KEYS}
