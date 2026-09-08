"""c022 — observation encoding with CARD IDENTITY for the shared embedding table.

`FIDELITY_RULES §1` says c019–c021 code is "infrastructure or negative evidence, never the
algorithmic authority". The feature extraction in `c020_byterl_encode` / `c021_byterl_encode` is
infrastructure: it reads the observation and produces float vectors, and it carries c021's fixes
(the energy-type feature wired to a type rather than a position; distinct active/bench slot
identity; an honest option-truncation counter). Reusing it is legitimate and reimplementing it
would only risk losing those fixes.

What it does NOT carry is what `MANDATORY_IMPLEMENTATION B1` requires and c021 had no use for:
**card identity**. c021's network scored options from hand-rolled float features alone, so two
different Trainers with identical feature vectors were the same object to it. The published
system uses shared card/Pokémon embeddings, which need integer card ids everywhere a card
appears. This module adds exactly that, on top of the existing tensors.

Card ids are remapped into a dense contiguous range. Raw engine card ids are sparse, and an
embedding table sized to the maximum raw id would be mostly dead rows; worse, `n_cards` would
change if the engine's id space ever moved, silently invalidating every checkpoint. Index 0 is
reserved for EMPTY, so an absent slot is a learned token rather than a zero vector colliding with
a real card.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c020_byterl_encode as E20  # noqa: E402
from cg import c021_byterl_encode as E21  # noqa: E402
from cg import c021_byterl_deck as DK  # noqa: E402

BENCH_SLOTS = E21.BENCH_SLOTS
BOARD_SLOTS = E21.BOARD_SLOTS
BOARD_DIM = E21.BOARD_DIM
GLOBAL_DIM = E21.GLOBAL_DIM
OPT_DIM = E21.OPT_DIM
MAX_OPTIONS = E21.MAX_OPTIONS
STAGE_BATTLE = E21.STAGE_BATTLE
STAGE_CONSTRUCTION = E21.STAGE_CONSTRUCTION

N_HAND = 12          # hand slots encoded by card id
N_DISCARD = 24       # discard slots encoded by card id

EMPTY_CARD = 0       # reserved dense index


class CardIndex:
    """Dense, stable card-id remapping.

    Built ONCE from the shipped card database and frozen. `n_cards` is a property of the database,
    not of whichever cards a particular run happened to see, so a checkpoint trained on one deck
    pool loads against another without silently reindexing every embedding row.
    """

    def __init__(self):
        from cg import c020_cards as CD
        ids = []
        # `c020_cards` exposes lookup by id; enumerate the id space it actually populates.
        for cid in range(0, 4096):
            try:
                if CD.card(cid) is not None:
                    ids.append(cid)
            except Exception:  # noqa: BLE001
                continue
        self.ids = sorted(set(ids))
        self.to_dense = {c: i + 1 for i, c in enumerate(self.ids)}   # 0 reserved for EMPTY
        self.n_cards = len(self.ids)

    def dense(self, card_id: Optional[int]) -> int:
        if card_id is None or int(card_id) < 0:
            return EMPTY_CARD
        return self.to_dense.get(int(card_id), EMPTY_CARD)

    def dense_array(self, card_ids, length: int) -> np.ndarray:
        out = np.zeros(length, dtype=np.int64)
        for i, c in enumerate(list(card_ids)[:length]):
            out[i] = self.dense(c)
        return out

    def schema(self) -> Dict[str, Any]:
        return {"n_cards": self.n_cards, "empty_index": EMPTY_CARD,
                "min_raw_id": min(self.ids) if self.ids else None,
                "max_raw_id": max(self.ids) if self.ids else None}


_INDEX: Optional[CardIndex] = None


def card_index() -> CardIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CardIndex()
    return _INDEX


def _card_id_of(obj) -> int:
    for attr in ("cardId", "card_id", "cardID", "id"):
        v = getattr(obj, attr, None)
        if v is not None:
            try:
                return int(v)
            except Exception:  # noqa: BLE001
                continue
    return -1


def _board_card_ids(view) -> np.ndarray:
    """Card id per board slot, in the SAME slot order `c021_byterl_encode` uses.

    Order matters: the slot features and the slot card ids are consumed side by side in
    `SlotEncoder`, and a mismatch would attach every Pokémon's identity to the wrong slot. The
    order is taken from `E20._board_list`, the one function that defines it, rather than
    re-derived here -- re-deriving it is exactly how a position-pairing defect gets shipped.
    """
    idx = card_index()
    out = np.zeros(BOARD_SLOTS, dtype=np.int64)
    try:
        rows = E20._board_list(view)
    except Exception:  # noqa: BLE001
        return out
    for pokemon, owner_is_mine, is_active, slot in rows:
        s = E20._slot_index(0 if is_active else 1, slot, owner_is_mine)
        if 0 <= s < BOARD_SLOTS and pokemon is not None:
            out[s] = idx.dense(_card_id_of(pokemon))
    return out


def encode_battle(observation, your_index: Optional[int] = None,
                  stats: Optional[E21.EncodeStats] = None) -> Dict[str, np.ndarray]:
    """c021's battle encoding plus card ids for slots, hand, discard and options."""
    from cg import c019_core as K
    enc = E21.encode_battle(observation, your_index, stats)
    idx = card_index()
    view = K.visible_view(observation, your_index)

    enc["slot_cards"] = _board_card_ids(view)
    try:
        enc["hand_cards"] = idx.dense_array([_card_id_of(c) for c in view.my_hand()], N_HAND)
    except Exception:  # noqa: BLE001
        enc["hand_cards"] = np.zeros(N_HAND, dtype=np.int64)
    try:
        disc = list(view.discard("mine")) + list(view.discard("theirs"))
        enc["discard_cards"] = idx.dense_array([_card_id_of(c) for c in disc], N_DISCARD)
    except Exception:  # noqa: BLE001
        enc["discard_cards"] = np.zeros(N_DISCARD, dtype=np.int64)

    oc = np.zeros(MAX_OPTIONS, dtype=np.int64)
    sel = getattr(observation, "select", None)
    if sel is not None:
        refs = E20.option_refs(observation, your_index)
        for i, r in enumerate(refs[:MAX_OPTIONS]):
            oc[i] = idx.dense(r.card_id)
    enc["option_cards"] = oc
    return enc


def encode_construction(partial: List[int], pool: DK.CardPool) -> Dict[str, np.ndarray]:
    """c021's construction encoding plus card ids for the partial deck.

    The construction stage sees the deck it has built so far through the SAME shared card
    embeddings the battle stage uses. That sharing is the mechanism by which a terminal game
    result can teach construction anything at all: without it, "this card won games" and "this
    card was chosen" live in disjoint parameters.
    """
    enc = E21.encode_construction(partial, pool)
    idx = card_index()
    enc["slot_cards"] = np.zeros(BOARD_SLOTS, dtype=np.int64)
    enc["hand_cards"] = idx.dense_array(list(reversed(partial)), N_HAND)   # most recent picks
    enc["discard_cards"] = np.zeros(N_DISCARD, dtype=np.int64)
    enc["option_cards"] = np.zeros(MAX_OPTIONS, dtype=np.int64)
    return enc


def to_torch(enc: Dict[str, np.ndarray], device: str = "cpu"):
    return E21.to_torch(enc, device)


def obs_parts(tt: Dict[str, Any]) -> Dict[str, Any]:
    """The exact keyword set `ByteRLRecurrentNet.observe` expects, from a torch batch.

    One function, used by BOTH the actor and the learner replay, so the two cannot assemble the
    observation differently. Probe B06 checks the resulting hidden states agree; this makes the
    agreement structural rather than coincidental.
    """
    return {"g": tt["global"], "slots": tt["board"], "roles": tt["roles"],
            "indices": tt["indices"], "sides": tt["sides"],
            "slot_cards": tt["slot_cards"], "hand_cards": tt["hand_cards"],
            "discard_cards": tt["discard_cards"], "stage": tt["stage"]}


def dims() -> Dict[str, int]:
    d = dict(E21.dims())
    d.update({"n_cards": card_index().n_cards, "n_hand": N_HAND, "n_discard": N_DISCARD,
              "pool_dim": None})
    return d


def schema() -> Dict[str, Any]:
    return {"base": E20.schema(), "cards": card_index().schema(),
            "n_hand": N_HAND, "n_discard": N_DISCARD, "max_options": MAX_OPTIONS,
            "board_slots": BOARD_SLOTS}
