"""Full legal-card vocabulary + structured card features (c006 AC-04).

Built deterministically from ``cg.api.all_card_data()`` — the complete
competition-legal card pool the engine exposes (1267 cards, ids 1..1267). Every
legal card gets its OWN vocabulary row (a distinct learnable-embedding slot) and
its OWN fixed structured-feature vector, so a legal card never seen in training
does NOT collapse to a generic ``<UNK>`` — it is still distinguishable by row and,
crucially, generalizable through its structured features.

Reserved rows (technical only): ``PAD``, ``MASK``, ``UNKNOWN_INVALID_ID``.

The vocabulary is a pure function of the engine metadata, so training and the
Kaggle-runtime agent rebuild the identical table (no serialization needed at
inference); a content hash pins it for evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

import numpy as np

PAD, MASK, UNKNOWN_INVALID_ID = 0, 1, 2
_N_RESERVED = 3
MIN_CARD_ID, MAX_CARD_ID = 1, 1267

# categorical cardinalities from engine enums
_N_CARDTYPE = 7      # POKEMON..SPECIAL_ENERGY
_N_ENERGYTYPE = 11   # 0..10
_N_WEAKRES = 9       # none + 8 energy types (1..8)

_HP_SCALE = 380.0
_RETREAT_SCALE = 4.0

_FEATURE_NAMES: List[str] = (
    ["is_reserved", "is_pokemon", "hp_norm", "retreat_norm"]
    + [f"cardType_{i}" for i in range(_N_CARDTYPE)]
    + [f"energyType_{i}" for i in range(_N_ENERGYTYPE)]
    + [f"weakness_{i}" for i in range(_N_WEAKRES)]     # index 0 = none
    + [f"resistance_{i}" for i in range(_N_WEAKRES)]
    + ["stage_basic", "stage_1", "stage_2"]
    + ["is_ex", "is_megaEx", "is_tera", "is_aceSpec"]
    + ["has_evolvesFrom", "n_attacks_norm", "n_skills_norm", "has_attack", "has_ability"]
)
FEAT_DIM = len(_FEATURE_NAMES)

_CACHE: Dict[str, Any] = {}


def _card_features(c: Any) -> np.ndarray:
    v = np.zeros(FEAT_DIM, dtype=np.float32)
    i = 0
    v[i] = 0.0; i += 1                                   # is_reserved
    v[i] = 1.0 if (c.hp or 0) > 0 else 0.0; i += 1        # is_pokemon
    v[i] = float(c.hp or 0) / _HP_SCALE; i += 1
    v[i] = float(c.retreatCost or 0) / _RETREAT_SCALE; i += 1
    ct = int(c.cardType)
    if 0 <= ct < _N_CARDTYPE:
        v[i + ct] = 1.0
    i += _N_CARDTYPE
    et = int(c.energyType or 0)
    if 0 <= et < _N_ENERGYTYPE:
        v[i + et] = 1.0
    i += _N_ENERGYTYPE
    w = c.weakness
    v[i + (0 if w is None else (w if 1 <= w <= 8 else 0))] = 1.0
    i += _N_WEAKRES
    r = c.resistance
    v[i + (0 if r is None else (r if 1 <= r <= 8 else 0))] = 1.0
    i += _N_WEAKRES
    v[i] = 1.0 if c.basic else 0.0; i += 1
    v[i] = 1.0 if c.stage1 else 0.0; i += 1
    v[i] = 1.0 if c.stage2 else 0.0; i += 1
    v[i] = 1.0 if c.ex else 0.0; i += 1
    v[i] = 1.0 if c.megaEx else 0.0; i += 1
    v[i] = 1.0 if c.tera else 0.0; i += 1
    v[i] = 1.0 if c.aceSpec else 0.0; i += 1
    v[i] = 1.0 if c.evolvesFrom else 0.0; i += 1
    na = len(c.attacks or [])
    ns = len(c.skills or [])
    v[i] = min(na, 2) / 2.0; i += 1
    v[i] = min(ns, 2) / 2.0; i += 1
    v[i] = 1.0 if na > 0 else 0.0; i += 1
    v[i] = 1.0 if ns > 0 else 0.0; i += 1
    assert i == FEAT_DIM
    return v


def build_vocab() -> Dict[str, Any]:
    if _CACHE:
        return _CACHE
    from cg.api import all_card_data
    cards = sorted(all_card_data(), key=lambda c: c.cardId)
    vocab_size = _N_RESERVED + len(cards)
    feats = np.zeros((vocab_size, FEAT_DIM), dtype=np.float32)
    # reserved rows: mark is_reserved
    for row in (PAD, MASK, UNKNOWN_INVALID_ID):
        feats[row, 0] = 1.0
    id_to_row: Dict[int, int] = {}
    hasher = hashlib.sha256()
    for c in cards:
        row = _N_RESERVED + (c.cardId - MIN_CARD_ID)
        id_to_row[c.cardId] = row
        feats[row] = _card_features(c)
        hasher.update(json.dumps([
            c.cardId, int(c.cardType), int(c.hp or 0), int(c.energyType or 0),
            int(c.retreatCost or 0), c.weakness, c.resistance,
            bool(c.basic), bool(c.stage1), bool(c.stage2),
            bool(c.ex), bool(c.megaEx), bool(c.tera), bool(c.aceSpec),
            bool(c.evolvesFrom), sorted(int(a) for a in (c.attacks or [])),
            len(c.skills or []),
        ], sort_keys=True).encode())
    _CACHE.update({
        "vocab_size": vocab_size,
        "feat_dim": FEAT_DIM,
        "feature_names": _FEATURE_NAMES,
        "feature_matrix": feats,
        "id_to_row": id_to_row,
        "n_cards": len(cards),
        "n_reserved": _N_RESERVED,
        "min_card_id": MIN_CARD_ID,
        "max_card_id": MAX_CARD_ID,
        "source": "cg.api.all_card_data()",
        "source_hash": hasher.hexdigest(),
    })
    return _CACHE


def row_for_id(card_id: Any) -> int:
    """Vocab row for a card id; legal ids get their own row, else UNKNOWN_INVALID_ID."""
    v = build_vocab()
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return UNKNOWN_INVALID_ID
    return v["id_to_row"].get(cid, UNKNOWN_INVALID_ID)


def features_for_id(card_id: Any) -> np.ndarray:
    v = build_vocab()
    return v["feature_matrix"][row_for_id(card_id)]


def validate_decks(deck_ids) -> Dict[str, Any]:
    v = build_vocab()
    missing = sorted({int(c) for c in deck_ids} - set(v["id_to_row"]))
    return {"all_present": not missing, "missing": missing, "n_checked": len(set(deck_ids))}


def dump_artifacts(vocab_path: str, schema_path: str) -> Dict[str, Any]:
    v = build_vocab()
    meta = {
        "contract": "c006_distilled_policy_baseline",
        "source": v["source"],
        "source_hash": v["source_hash"],
        "vocab_size": v["vocab_size"],
        "n_legal_cards": v["n_cards"],
        "n_reserved": v["n_reserved"],
        "reserved_tokens": {"PAD": PAD, "MASK": MASK, "UNKNOWN_INVALID_ID": UNKNOWN_INVALID_ID},
        "card_id_range": [v["min_card_id"], v["max_card_id"]],
        "id_to_row_rule": "row = 3 + (card_id - 1) for legal ids; unseen/invalid -> UNKNOWN_INVALID_ID(2)",
        "no_generic_unk_collapse": True,
        "feat_dim": v["feat_dim"],
    }
    json.dump(meta, open(vocab_path, "w"), indent=2)
    schema = {
        "feature_names": v["feature_names"],
        "feat_dim": v["feat_dim"],
        "hp_scale": _HP_SCALE,
        "retreat_scale": _RETREAT_SCALE,
        "notes": "attack/ability energy costs are not exposed as structured metadata "
                 "(only attack/ability IDs); represented via counts + presence flags. "
                 "attackId is used as a per-option feature in the featurizer, not here.",
    }
    json.dump(schema, open(schema_path, "w"), indent=2)
    return meta


if __name__ == "__main__":
    import sys
    m = dump_artifacts(sys.argv[1], sys.argv[2])
    print(json.dumps(m, indent=2))
