"""Shared featurizer: (normalized observation, legal options) -> numeric features.

ONE featurizer used by BOTH offline dataset featurization and the runtime cabt
agent (the agent first passes the live obs through the same
``cg.episode_capture.normalize_observation`` so the two paths are byte-identical).
Produces:

  gdense : float32[GDENSE]                global scalar + context + card-feature block
  grows  : int32[2]                       vocab rows for my/opp active (embedding)
  odense : float32[n_opt, ODENSE]         per-option scalar + referenced-card features
  orows  : int32[n_opt, 2]                vocab rows for each option's two card slots
  prev   : float32[PREV]                  explicit previous-context/action inputs (S2)

Card ids are resolved from the observation exactly as the teacher's ``get_card``
does (hand/bench/active/discard/prize/deck/stadium/looking).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cg.card_vocab import FEAT_DIM as CARD_FEAT, features_for_id, row_for_id

# ---- enum-derived sizes ----
from cg.api import AreaType, OptionType, SelectContext  # noqa: E402

_CTX_INDEX = {int(m): i for i, m in enumerate(SelectContext)}
N_CTX = len(_CTX_INDEX) + 1                 # + unknown bucket
_CTX_UNK = N_CTX - 1
N_OPTTYPE = 17
N_AREA = 13                                 # AreaType 0..12 (0 = none)
_PHANTOM_DIVE = 154

# global scalar block (non-card)
_GLOBAL_SCALARS = 18
GDENSE = N_CTX + _GLOBAL_SCALARS + 5 * CARD_FEAT     # ctx + scalars + 5 card slots (active x2, 3 bags)
GROWS = 2

# option scalar block
_OPT_SCALARS = N_OPTTYPE + N_AREA + N_AREA + 3 + 2 + 3 + 2 + 1   # type,area,inPlayArea,player,idx,attack,number,count
ODENSE = _OPT_SCALARS + 2 * CARD_FEAT
OROWS = 2

PREV = N_CTX + 2                            # prev context one-hot + prev_count + prev_multiselect flag


def _onehot(vec: np.ndarray, idx: int, n: int, base: int):
    if idx is not None and 0 <= idx < n:
        vec[base + idx] = 1.0


def _card_id(card: Any) -> Optional[int]:
    if isinstance(card, dict):
        return card.get("id")
    if isinstance(card, int):
        return card
    return None


def get_card(obs: Dict[str, Any], area, index, player_index):
    cur = obs.get("current") or {}
    sel = obs.get("select") or {}
    try:
        if area == int(AreaType.DECK):
            deck = sel.get("deck")
            return deck[index] if deck else None
        if area == int(AreaType.STADIUM):
            return (cur.get("stadium") or [])[index]
        if area == int(AreaType.LOOKING):
            return (cur.get("looking") or [])[index]
        players = cur.get("players") or []
        ps = players[player_index]
        zone = {int(AreaType.HAND): "hand", int(AreaType.DISCARD): "discard",
                int(AreaType.ACTIVE): "active", int(AreaType.BENCH): "bench",
                int(AreaType.PRIZE): "prize"}.get(area)
        if zone is None:
            return None
        return (ps.get(zone) or [])[index]
    except (IndexError, TypeError, KeyError):
        return None


def _bag_features(cards: List[Any]) -> np.ndarray:
    ids = [_card_id(c) for c in (cards or [])]
    ids = [i for i in ids if i is not None]
    if not ids:
        return np.zeros(CARD_FEAT, dtype=np.float32)
    return np.mean([features_for_id(i) for i in ids], axis=0).astype(np.float32)


def _active_id(ps: Dict[str, Any]) -> Optional[int]:
    act = ps.get("active") or []
    for c in act:
        cid = _card_id(c)
        if cid is not None:
            return cid
    return None


def featurize_global(obs: Dict[str, Any]) -> (np.ndarray, np.ndarray):
    g = np.zeros(GDENSE, dtype=np.float32)
    sel = obs.get("select") or {}
    cur = obs.get("current") or {}
    yi = cur.get("yourIndex", 0) or 0
    players = cur.get("players") or [{}, {}]
    me = players[yi] if yi < len(players) else {}
    op = players[1 - yi] if (1 - yi) < len(players) else {}

    ci = _CTX_INDEX.get(sel.get("context"), _CTX_UNK)
    g[ci] = 1.0
    base = N_CTX
    n_opt = len(sel.get("option") or [])
    my_prize = len(me.get("prize") or [])
    op_prize = len(op.get("prize") or [])
    scal = [
        (sel.get("minCount") or 0) / 10.0,
        (sel.get("maxCount") or 0) / 10.0,
        n_opt / 10.0,
        (sel.get("remainDamageCounter") or 0) / 10.0,
        (sel.get("remainEnergyCost") or 0) / 5.0,
        (cur.get("turn") or 0) / 30.0,
        (cur.get("turnActionCount") or 0) / 20.0,
        my_prize / 6.0,
        op_prize / 6.0,
        len(me.get("bench") or []) / 8.0,
        len(op.get("bench") or []) / 8.0,
        len(me.get("hand") or []) / 15.0,
        1.0 if cur.get("supporterPlayed") else 0.0,
        1.0 if cur.get("energyAttached") else 0.0,
        1.0 if cur.get("retreated") else 0.0,
        1.0 if (cur.get("stadium") or []) else 0.0,
        1.0 if cur.get("firstPlayer") == yi else 0.0,
        (my_prize - op_prize) / 6.0,
    ]
    g[base:base + _GLOBAL_SCALARS] = np.asarray(scal, dtype=np.float32)
    base += _GLOBAL_SCALARS
    my_active = _active_id(me)
    op_active = _active_id(op)
    g[base:base + CARD_FEAT] = features_for_id(my_active); base += CARD_FEAT
    g[base:base + CARD_FEAT] = features_for_id(op_active); base += CARD_FEAT
    g[base:base + CARD_FEAT] = _bag_features(me.get("hand")); base += CARD_FEAT
    g[base:base + CARD_FEAT] = _bag_features(me.get("bench")); base += CARD_FEAT
    g[base:base + CARD_FEAT] = _bag_features(op.get("bench")); base += CARD_FEAT
    rows = np.array([row_for_id(my_active), row_for_id(op_active)], dtype=np.int32)
    return g, rows


def featurize_options(obs: Dict[str, Any]) -> (np.ndarray, np.ndarray):
    sel = obs.get("select") or {}
    cur = obs.get("current") or {}
    yi = cur.get("yourIndex", 0) or 0
    options = sel.get("option") or []
    n = len(options)
    od = np.zeros((n, ODENSE), dtype=np.float32)
    orows = np.full((n, 2), 0, dtype=np.int32)
    for i, o in enumerate(options):
        v = od[i]
        b = 0
        _onehot(v, o.get("type"), N_OPTTYPE, b); b += N_OPTTYPE
        area = o.get("area")
        _onehot(v, area if area is not None else 0, N_AREA, b); b += N_AREA
        ipa = o.get("inPlayArea")
        _onehot(v, ipa if ipa is not None else 0, N_AREA, b); b += N_AREA
        pidx = o.get("playerIndex")
        v[b] = 1.0 if pidx == yi else 0.0
        v[b + 1] = 1.0 if (pidx is not None and pidx != yi) else 0.0
        v[b + 2] = 1.0 if pidx is None else 0.0
        b += 3
        idx = o.get("index")
        v[b] = 1.0 if idx is not None else 0.0
        v[b + 1] = (idx or 0) / 10.0
        b += 2
        aid = o.get("attackId")
        v[b] = 1.0 if aid == _PHANTOM_DIVE else 0.0
        v[b + 1] = 1.0 if o.get("type") == int(OptionType.ATTACK) else 0.0
        v[b + 2] = (aid or 0) / 2000.0
        b += 3
        num = o.get("number")
        v[b] = 1.0 if num is not None else 0.0
        v[b + 1] = (num or 0) / 10.0
        b += 2
        v[b] = (o.get("count") or 0) / 5.0
        b += 1
        # referenced cards
        otype = o.get("type")
        if otype == int(OptionType.PLAY):
            c1 = get_card(obs, int(AreaType.HAND), idx, yi)
        elif area is not None and idx is not None:
            c1 = get_card(obs, area, idx, pidx if pidx is not None else yi)
        else:
            c1 = None
        c2 = None
        if ipa is not None and o.get("inPlayIndex") is not None:
            c2 = get_card(obs, ipa, o.get("inPlayIndex"), yi)
        id1, id2 = _card_id(c1), _card_id(c2)
        v[b:b + CARD_FEAT] = features_for_id(id1); b += CARD_FEAT
        v[b:b + CARD_FEAT] = features_for_id(id2); b += CARD_FEAT
        orows[i, 0] = row_for_id(id1)
        orows[i, 1] = row_for_id(id2)
    return od, orows


def featurize_prev(prev_context_value, prev_selected_count) -> np.ndarray:
    p = np.zeros(PREV, dtype=np.float32)
    if prev_context_value is not None:
        p[_CTX_INDEX.get(prev_context_value, _CTX_UNK)] = 1.0
    else:
        p[_CTX_UNK] = 1.0  # game start marker
    p[N_CTX] = (prev_selected_count or 0) / 3.0
    p[N_CTX + 1] = 1.0 if (prev_selected_count or 0) > 1 else 0.0
    return p


def featurize_decision(obs: Dict[str, Any], prev_context_value=None, prev_selected_count=0) -> Dict[str, Any]:
    gdense, grows = featurize_global(obs)
    odense, orows = featurize_options(obs)
    prev = featurize_prev(prev_context_value, prev_selected_count)
    return {"gdense": gdense, "grows": grows, "odense": odense, "orows": orows,
            "prev": prev, "n_options": odense.shape[0]}


FEATURE_DIMS = {"GDENSE": GDENSE, "GROWS": GROWS, "ODENSE": ODENSE, "OROWS": OROWS,
                "PREV": PREV, "N_CTX": N_CTX, "CARD_FEAT": CARD_FEAT}
