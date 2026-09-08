"""c007 AC-03: State Encoder v2 — a materially richer, loss-audited representation.

Fixes the c006 diagnosis (lossy dynamic state, averaged zones, weak card semantics,
independent option scoring, incomplete previous-action identity). Consumes the raw
cabt observation dict (identical offline and at runtime) and emits FIXED-shape numpy
arrays so the pure-numpy v2 model can train on dense batched tensors:

  - Per-slot in-play board: self active + self bench 0..4 + opp active + opp bench 0..4
    (12 explicit slots, NEVER averaged), each with dynamic HP/energy/status/KO/evo
    features + a card ROW index for the model's card encoder.
  - Exact hand & discard multisets (set-encoder inputs, not averaged), with duplicate
    counts and a derivable hand-playability mask.
  - Deck/prize/game knowledge and hidden-information discipline (opponent hand is a
    count only; prizes face-down).
  - History: previous context + the ACTUAL previous selected option identity
    (card id / attack id / option type), threaded per game, reset at game start.
  - Legal options encoded separately with card/target semantics for a cross-option
    set encoder (see policy_model_v2).

Card semantics are the deterministic card_vocab feature matrix (52 dims); the model
adds a ZERO-initialised id-embedding residual, so unseen legal cards fall back to
feature-derived semantics (no random untrained id vectors) — §7.6.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cg import card_vocab
from cg.api import AreaType, CardType, EnergyType, OptionType, SelectContext

CARD_FEAT = card_vocab.FEAT_DIM  # 52

# ---- enum sizing (one-hots indexed by int value) ----
N_OPTTYPE = 17     # OptionType 0..16
N_AREA = 13        # AreaType up to 12
N_CTX = 49         # SelectContext up to 48
N_ENERGY = 12      # EnergyType 0..11
N_CARDTYPE = 7     # CardType 0..6

# ---- board ----
N_SELF_BENCH = 5
N_OPP_BENCH = 5
N_BOARD = 1 + N_SELF_BENCH + 1 + N_OPP_BENCH  # 12 explicit slots

# per-slot dynamic feature layout (indices)
_S = {}
def _reg(name, width=1):
    off = _reg.n
    _S[name] = (off, width)
    _reg.n += width
_reg.n = 0
_reg("present"); _reg("is_self"); _reg("is_active"); _reg("slot_index_norm")
_reg("hp_norm"); _reg("maxhp_norm"); _reg("damage_norm"); _reg("remaining_frac")
_reg("n_energy_norm"); _reg("energy_type_counts", N_ENERGY)
_reg("n_energy_cards_norm"); _reg("n_tools_norm"); _reg("has_tool"); _reg("n_preevo_norm")
_reg("appear_this_turn")
_reg("status", 5)  # poisoned burned asleep paralyzed confused (active only)
_reg("ko_hp_le_200"); _reg("ko_hp_le_60"); _reg("prize_yield_norm")
_reg("is_ex"); _reg("is_megaex")
SLOT_DYN = _reg.n  # 36

# ---- hand / discard ----
N_HAND = 12
HAND_DYN = 2       # [dup_count_norm, playable]
N_DISCARD = 16

# ---- options ----
OPT_DENSE = (N_OPTTYPE + N_AREA + N_AREA + 2 + 1 + 1 + 1 + 1 + 1 + 1)  # 51
OPT_ROWS = 2       # [primary card row, in-play target row]

# ---- global ----
_GAME_SCALARS = 26
_DISCARD_TYPE = 2 * N_CARDTYPE  # self + opp discard card-type counts
_HIST = N_CTX + N_OPTTYPE + CARD_FEAT + 2 + 1 + 1
GLOBAL = N_CTX + _GAME_SCALARS + _DISCARD_TYPE + _HIST

_HP = 380.0

# feature-name indices into the card_vocab feature matrix for ex / megaEx / prize
_FEAT_NAMES = card_vocab.build_vocab()["feature_names"]
_IDX_EX = _FEAT_NAMES.index("is_ex") if "is_ex" in _FEAT_NAMES else None
_IDX_MEGA = _FEAT_NAMES.index("is_megaEx") if "is_megaEx" in _FEAT_NAMES else None


def feature_dims() -> Dict[str, int]:
    return {"CARD_FEAT": CARD_FEAT, "N_BOARD": N_BOARD, "SLOT_DYN": SLOT_DYN,
            "N_HAND": N_HAND, "HAND_DYN": HAND_DYN, "N_DISCARD": N_DISCARD,
            "OPT_DENSE": OPT_DENSE, "OPT_ROWS": OPT_ROWS, "GLOBAL": GLOBAL,
            "N_CTX": N_CTX, "N_OPTTYPE": N_OPTTYPE, "N_AREA": N_AREA,
            "vocab_size": card_vocab.build_vocab()["vocab_size"]}


# -------------------- helpers --------------------

def _row(card_id: Optional[int]) -> int:
    if card_id is None:
        return card_vocab.PAD
    return card_vocab.row_for_id(int(card_id))


def _get(d, k, default=None):
    if d is None:
        return default
    return d.get(k, default) if isinstance(d, dict) else getattr(d, k, default)


def resolve_card(obs: dict, area: Any, index: Optional[int], player_index: int) -> Optional[dict]:
    """Resolve an option's referenced card dict from any zone (mirrors teacher get_card)."""
    if area is None or index is None:
        return None
    cur = obs["current"]
    sel = obs["select"]
    try:
        a = int(area)
    except (TypeError, ValueError):
        return None
    try:
        if a == int(AreaType.DECK):
            deck = sel.get("deck")
            return deck[index] if deck and 0 <= index < len(deck) else None
        if a == int(AreaType.STADIUM):
            st = cur.get("stadium") or []
            return st[index] if 0 <= index < len(st) else None
        if a == int(AreaType.LOOKING):
            lk = cur.get("looking") or []
            return lk[index] if lk and 0 <= index < len(lk) else None
        ps = cur["players"][player_index]
        zone = {int(AreaType.HAND): "hand", int(AreaType.DISCARD): "discard",
                int(AreaType.ACTIVE): "active", int(AreaType.BENCH): "bench",
                int(AreaType.PRIZE): "prize"}.get(a)
        if zone is None:
            return None
        lst = ps.get(zone)
        if not lst or index < 0 or index >= len(lst):
            return None
        return lst[index]
    except (KeyError, IndexError, TypeError):
        return None


def _energy_type_counts(poke: dict) -> np.ndarray:
    out = np.zeros(N_ENERGY)
    for e in (poke.get("energies") or []):
        try:
            ei = int(e)
        except (TypeError, ValueError):
            continue
        if 0 <= ei < N_ENERGY:
            out[ei] += 1
    return out / 4.0


def _slot_vec(poke: Optional[dict], is_self: bool, is_active: bool, slot_idx: int,
              status: Optional[List[int]]) -> Tuple[int, np.ndarray]:
    v = np.zeros(SLOT_DYN)
    if poke is None:
        return card_vocab.PAD, v
    o, _w = _S["present"]; v[o] = 1.0
    v[_S["is_self"][0]] = 1.0 if is_self else 0.0
    v[_S["is_active"][0]] = 1.0 if is_active else 0.0
    v[_S["slot_index_norm"][0]] = slot_idx / 6.0
    hp = float(poke.get("hp") or 0)
    mhp = float(poke.get("maxHp") or hp or 1.0)
    v[_S["hp_norm"][0]] = hp / _HP
    v[_S["maxhp_norm"][0]] = mhp / _HP
    v[_S["damage_norm"][0]] = max(0.0, mhp - hp) / _HP
    v[_S["remaining_frac"][0]] = hp / mhp if mhp > 0 else 0.0
    energies = poke.get("energies") or []
    v[_S["n_energy_norm"][0]] = len(energies) / 6.0
    o, w = _S["energy_type_counts"]; v[o:o + w] = _energy_type_counts(poke)
    v[_S["n_energy_cards_norm"][0]] = len(poke.get("energyCards") or []) / 6.0
    tools = poke.get("tools") or []
    v[_S["n_tools_norm"][0]] = len(tools) / 2.0
    v[_S["has_tool"][0]] = 1.0 if tools else 0.0
    v[_S["n_preevo_norm"][0]] = len(poke.get("preEvolution") or []) / 3.0
    v[_S["appear_this_turn"][0]] = 1.0 if poke.get("appearThisTurn") else 0.0
    if is_active and status is not None:
        o, w = _S["status"]; v[o:o + w] = np.asarray(status[:w], dtype=float)
    v[_S["ko_hp_le_200"][0]] = 1.0 if 0 < hp <= 200 else 0.0
    v[_S["ko_hp_le_60"][0]] = 1.0 if 0 < hp <= 60 else 0.0
    feats = card_vocab.features_for_id(int(poke["id"])) if poke.get("id") else None
    ex = mega = 0.0
    if feats is not None:
        if _IDX_EX is not None:
            ex = float(feats[_IDX_EX])
        if _IDX_MEGA is not None:
            mega = float(feats[_IDX_MEGA])
    v[_S["prize_yield_norm"][0]] = (3.0 if mega else 2.0 if ex else 1.0) / 3.0
    v[_S["is_ex"][0]] = ex
    v[_S["is_megaex"][0]] = mega
    return _row(poke.get("id")), v


def _player_status(ps: dict) -> List[int]:
    return [int(bool(ps.get("poisoned"))), int(bool(ps.get("burned"))),
            int(bool(ps.get("asleep"))), int(bool(ps.get("paralyzed"))),
            int(bool(ps.get("confused")))]


def _first(lst):
    return lst[0] if lst else None


# -------------------- history --------------------

def initial_prev_state() -> Dict[str, Any]:
    return {"present": False, "context": None, "action_type": None,
            "card_id": None, "attack_id": None, "selected_count": 0}


def derive_prev_state(obs: dict, selected_indices: List[int]) -> Dict[str, Any]:
    """Compute the history state to feed the NEXT decision from this obs + chosen action."""
    sel = obs.get("select")
    if sel is None or not selected_indices:
        return initial_prev_state()
    opts = sel.get("option") or []
    i0 = selected_indices[0]
    if i0 < 0 or i0 >= len(opts):
        return {"present": True, "context": sel.get("context"), "action_type": None,
                "card_id": None, "attack_id": None, "selected_count": len(selected_indices)}
    o = opts[i0]
    my = obs["current"]["yourIndex"]
    card = resolve_card(obs, o.get("area"), o.get("index"), o.get("playerIndex", my))
    cid = _get(card, "id")
    if cid is None and o.get("cardId"):
        cid = o.get("cardId")
    return {"present": True, "context": sel.get("context"), "action_type": o.get("type"),
            "card_id": cid, "attack_id": o.get("attackId"),
            "selected_count": len(selected_indices)}


def _history_vec(prev: Dict[str, Any]) -> np.ndarray:
    v = np.zeros(_HIST)
    off = 0
    if prev and prev.get("present"):
        c = prev.get("context")
        if c is not None and 0 <= int(c) < N_CTX:
            v[off + int(c)] = 1.0
    off += N_CTX
    at = prev.get("action_type") if prev else None
    if at is not None and 0 <= int(at) < N_OPTTYPE:
        v[off + int(at)] = 1.0
    off += N_OPTTYPE
    cid = prev.get("card_id") if prev else None
    if cid:
        v[off:off + CARD_FEAT] = card_vocab.features_for_id(int(cid))
    off += CARD_FEAT
    aid = prev.get("attack_id") if prev else None
    v[off] = 1.0 if aid == 154 else 0.0
    v[off + 1] = 1.0 if aid else 0.0
    off += 2
    v[off] = (prev.get("selected_count", 0) if prev else 0) / 3.0
    off += 1
    v[off] = 1.0 if (prev and prev.get("present")) else 0.0
    return v


# -------------------- global scalars --------------------

def _game_scalars(obs: dict) -> np.ndarray:
    cur = obs["current"]; sel = obs["select"]
    my = cur["yourIndex"]
    me = cur["players"][my]; op = cur["players"][1 - my]
    opts = sel.get("option") or []
    types = [o.get("type") for o in opts]
    has_attack = int(OptionType.ATTACK) in types
    has_end = int(OptionType.END) in types
    phantom = any(o.get("type") == int(OptionType.ATTACK) and o.get("attackId") == 154 for o in opts)
    my_prize = len(me.get("prize") or [])
    op_prize = len(op.get("prize") or [])
    v = np.array([
        cur.get("turn", 0) / 25.0,
        cur.get("turnActionCount", 0) / 10.0,
        my_prize / 6.0, op_prize / 6.0, (my_prize - op_prize) / 6.0,
        len(me.get("bench") or []) / 5.0, len(op.get("bench") or []) / 5.0,
        (me.get("handCount") or 0) / 12.0, (op.get("handCount") or 0) / 12.0,
        (me.get("deckCount") or 0) / 40.0, (op.get("deckCount") or 0) / 40.0,
        1.0 if cur.get("supporterPlayed") else 0.0,
        1.0 if cur.get("stadiumPlayed") else 0.0,
        1.0 if cur.get("energyAttached") else 0.0,
        1.0 if cur.get("retreated") else 0.0,
        1.0 if cur.get("firstPlayer") == my else 0.0,
        float(my),
        (sel.get("minCount") or 0) / 6.0, (sel.get("maxCount") or 0) / 6.0,
        len(opts) / 32.0,
        (sel.get("remainDamageCounter") or 0) / 6.0,
        (sel.get("remainEnergyCost") or 0) / 6.0,
        1.0 if (cur.get("stadium")) else 0.0,
        float(has_attack), float(has_end), float(phantom),
    ])
    assert v.shape[0] == _GAME_SCALARS, (v.shape[0], _GAME_SCALARS)
    return v


def _discard_type_counts(ps: dict) -> np.ndarray:
    out = np.zeros(N_CARDTYPE)
    for c in (ps.get("discard") or []):
        feats = card_vocab.features_for_id(int(c["id"])) if c.get("id") else None
        # card-type one-hot lives in the vocab feature matrix; approximate via id lookup
        cid = c.get("id")
        if cid is None:
            continue
        ct = _card_type(cid)
        if ct is not None and 0 <= ct < N_CARDTYPE:
            out[ct] += 1
    return out / 8.0


_CARD_TYPE_CACHE: Dict[int, Optional[int]] = {}


def _card_type(card_id: int) -> Optional[int]:
    if card_id in _CARD_TYPE_CACHE:
        return _CARD_TYPE_CACHE[card_id]
    from cg.api import all_card_data
    global _ALL_CARDS
    try:
        _ALL_CARDS
    except NameError:
        _ALL_CARDS = {c.cardId: c for c in all_card_data()}
    c = _ALL_CARDS.get(card_id)
    ct = int(c.cardType) if c is not None else None
    _CARD_TYPE_CACHE[card_id] = ct
    return ct


# -------------------- options --------------------

def _hand_playable_mask(obs: dict) -> set:
    """Hand indices referenced by any legal PLAY/ATTACH/EVOLVE/ABILITY option."""
    out = set()
    sel = obs.get("select") or {}
    my = obs["current"]["yourIndex"]
    for o in (sel.get("option") or []):
        t = o.get("type")
        if t in (int(OptionType.PLAY), int(OptionType.ATTACH), int(OptionType.EVOLVE)):
            if o.get("area") in (None, int(AreaType.HAND)) and o.get("index") is not None:
                out.add(o.get("index"))
    return out


def _opt_dense(o: dict, my_index: int) -> np.ndarray:
    v = np.zeros(OPT_DENSE)
    off = 0
    t = o.get("type")
    if t is not None and 0 <= int(t) < N_OPTTYPE:
        v[off + int(t)] = 1.0
    off += N_OPTTYPE
    a = o.get("area")
    if a is not None and 0 <= int(a) < N_AREA:
        v[off + int(a)] = 1.0
    off += N_AREA
    ipa = o.get("inPlayArea")
    if ipa is not None and 0 <= int(ipa) < N_AREA:
        v[off + int(ipa)] = 1.0
    off += N_AREA
    pi = o.get("playerIndex")
    v[off] = 1.0 if pi == my_index else 0.0
    v[off + 1] = 1.0 if (pi is not None and pi != my_index) else 0.0
    off += 2
    v[off] = (o.get("index") or 0) / 12.0; off += 1
    v[off] = (o.get("count") or 0) / 6.0; off += 1
    v[off] = (o.get("number") or 0) / 10.0; off += 1
    v[off] = 1.0 if o.get("attackId") == 154 else 0.0; off += 1
    v[off] = 1.0 if o.get("attackId") else 0.0; off += 1
    v[off] = (o.get("inPlayIndex") or 0) / 6.0; off += 1
    return v


def _opt_rows(obs: dict, o: dict, my_index: int) -> Tuple[int, int]:
    pi = o.get("playerIndex", my_index)
    card = resolve_card(obs, o.get("area"), o.get("index"), pi if pi is not None else my_index)
    cid = _get(card, "id")
    if cid is None and o.get("cardId"):
        cid = o.get("cardId")
    target = resolve_card(obs, o.get("inPlayArea"), o.get("inPlayIndex"), my_index)
    tid = _get(target, "id")
    return _row(cid), _row(tid)


# -------------------- main entry --------------------

def encode(obs: dict, prev_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Encode one decision. Returns fixed-shape board/hand/discard/global arrays plus
    per-option arrays (padded at collate). ``prev_state`` supplies history; obtain the
    next one via :func:`derive_prev_state`."""
    cur = obs["current"]; sel = obs["select"]
    my = cur["yourIndex"]
    me = cur["players"][my]; op = cur["players"][1 - my]
    my_status = _player_status(me)
    op_status = _player_status(op)

    board_rows = np.zeros(N_BOARD, dtype=np.int64)
    board_dyn = np.zeros((N_BOARD, SLOT_DYN))
    slot = 0
    # self active
    r, v = _slot_vec(_first(me.get("active")), True, True, 0, my_status)
    board_rows[slot] = r; board_dyn[slot] = v; slot += 1
    # self bench
    bench = me.get("bench") or []
    for k in range(N_SELF_BENCH):
        r, v = _slot_vec(bench[k] if k < len(bench) else None, True, False, k + 1, None)
        board_rows[slot] = r; board_dyn[slot] = v; slot += 1
    # opp active
    r, v = _slot_vec(_first(op.get("active")), False, True, 0, op_status)
    board_rows[slot] = r; board_dyn[slot] = v; slot += 1
    # opp bench
    obench = op.get("bench") or []
    for k in range(N_OPP_BENCH):
        r, v = _slot_vec(obench[k] if k < len(obench) else None, False, False, k + 1, None)
        board_rows[slot] = r; board_dyn[slot] = v; slot += 1

    # hand (own; opponent hand is hidden -> count only)
    hand = me.get("hand") or []
    id_counts: Dict[int, int] = {}
    for c in hand:
        cid = c.get("id")
        if cid is not None:
            id_counts[cid] = id_counts.get(cid, 0) + 1
    playable = _hand_playable_mask(obs)
    hand_rows = np.zeros(N_HAND, dtype=np.int64)
    hand_dyn = np.zeros((N_HAND, HAND_DYN))
    hand_mask = np.zeros(N_HAND)
    for k in range(min(N_HAND, len(hand))):
        c = hand[k]
        hand_rows[k] = _row(c.get("id"))
        hand_dyn[k, 0] = id_counts.get(c.get("id"), 1) / 4.0
        hand_dyn[k, 1] = 1.0 if k in playable else 0.0
        hand_mask[k] = 1.0

    # discard (own recent window)
    disc = me.get("discard") or []
    disc_rows = np.zeros(N_DISCARD, dtype=np.int64)
    disc_mask = np.zeros(N_DISCARD)
    recent = disc[-N_DISCARD:]
    for k, c in enumerate(recent):
        disc_rows[k] = _row(c.get("id"))
        disc_mask[k] = 1.0

    # global
    g = np.zeros(GLOBAL)
    off = 0
    ctx = sel.get("context")
    if ctx is not None and 0 <= int(ctx) < N_CTX:
        g[off + int(ctx)] = 1.0
    off += N_CTX
    g[off:off + _GAME_SCALARS] = _game_scalars(obs); off += _GAME_SCALARS
    g[off:off + N_CARDTYPE] = _discard_type_counts(me); off += N_CARDTYPE
    g[off:off + N_CARDTYPE] = _discard_type_counts(op); off += N_CARDTYPE
    g[off:off + _HIST] = _history_vec(prev_state or initial_prev_state()); off += _HIST
    assert off == GLOBAL, (off, GLOBAL)

    # options
    opts = sel.get("option") or []
    n = len(opts)
    opt_dense = np.zeros((max(n, 1), OPT_DENSE))
    opt_rows = np.zeros((max(n, 1), OPT_ROWS), dtype=np.int64)
    for i, o in enumerate(opts):
        opt_dense[i] = _opt_dense(o, my)
        r0, r1 = _opt_rows(obs, o, my)
        opt_rows[i, 0] = r0; opt_rows[i, 1] = r1

    return {
        "board_rows": board_rows, "board_dyn": board_dyn,
        "hand_rows": hand_rows, "hand_dyn": hand_dyn, "hand_mask": hand_mask,
        "disc_rows": disc_rows, "disc_mask": disc_mask,
        "global": g, "opt_dense": opt_dense, "opt_rows": opt_rows,
        "n_options": n,
    }
