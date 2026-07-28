"""c020 B1/B2 — slot-aware observation and option-to-object encoding.

c019 pooled active and bench Pokemon into one bag of board tokens (audit #7) and dropped energy
types, statuses, tools and the relationship between an option and the objects it references
(audit #8). Both are fatal for a card game: "attach energy to the thing in bench slot 3" and
"attach energy to the thing in bench slot 4" become the same instruction if slot identity is
destroyed before option scoring.

Layout here (`IMPLEMENTATION_GUIDE §6`):

    board_tokens[12] = our active, our bench 1-5, opp active, opp bench 1-5   -- FIXED positions
    hand_tokens[N]
    discard summaries per side
    context token

Every board token carries an explicit slot id and an owner flag, so slot identity survives into
the option scorer. Each legal option stores INDICES into those tokens (`OptionRef.source_index`,
`target_index`), which is what lets the policy score "this attack, from this Pokemon, at that
Pokemon" rather than a bare action type.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_cards as CD  # noqa: E402

BENCH_SLOTS = 5
BOARD_SLOTS = 2 * (1 + BENCH_SLOTS)          # 12 fixed positions
N_HAND = 12
N_DISCARD_SUMMARY = 8
N_OPT = 40
N_ENERGY_TYPES = 12

# per-token feature widths
BOARD_DIM = (
    1 +          # occupied
    1 +          # owner (1 = ours)
    1 +          # is_active
    1 +          # slot index normalized
    1 +          # card id normalized
    2 +          # hp fraction, max hp normalized
    1 +          # damage fraction
    N_ENERGY_TYPES +   # attached energy BY TYPE
    1 +          # total attached
    1 +          # energy shortfall to enable any attack
    1 +          # has legal attack now
    1 +          # best legal damage normalized
    1 +          # max potential damage normalized
    1 +          # retreat cost
    1 +          # prize value
    1 +          # tool attached
    5 +          # status: poison/burn/asleep/paralyzed/confused
    1 +          # evolution stage
    1            # can be KO'd by opposing active
)
HAND_DIM = 8
GLOBAL_DIM = 24
OPT_DIM = 28


def _f(x, d=0.0) -> float:
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _status_vec(player, pokemon) -> List[float]:
    """Status flags. c019 had none of these (audit #8)."""
    out = []
    for attr in ("poisoned", "burned", "asleep", "paralyzed", "confused"):
        v = getattr(player, attr, None)
        try:
            out.append(1.0 if (v and getattr(pokemon, "id", None) in
                               (v if isinstance(v, (list, tuple)) else [v])) else
                       (1.0 if v is True else 0.0))
        except Exception:  # noqa: BLE001
            out.append(0.0)
    return out


def encode_board_token(pokemon, owner_is_mine: bool, is_active: bool, slot: int,
                       player=None, opposing_active=None) -> np.ndarray:
    v = np.zeros(BOARD_DIM, dtype=np.float32)
    if pokemon is None:
        return v
    i = 0
    v[i] = 1.0; i += 1                                   # occupied
    v[i] = 1.0 if owner_is_mine else 0.0; i += 1
    v[i] = 1.0 if is_active else 0.0; i += 1
    v[i] = slot / float(BENCH_SLOTS); i += 1             # EXPLICIT slot identity (B1)
    v[i] = _f(getattr(pokemon, "id", 0)) / 2000.0; i += 1
    hp, mx = CD.hp_now(pokemon)
    v[i] = (hp / mx) if mx else 0.0; i += 1
    v[i] = mx / 400.0; i += 1
    v[i] = ((mx - hp) / mx) if mx else 0.0; i += 1
    att = CD.attached_energy(pokemon)                     # BY TYPE (B2)
    for t in range(N_ENERGY_TYPES):
        v[i + t] = min(att.get(t, 0), 6) / 6.0
    i += N_ENERGY_TYPES
    v[i] = min(sum(att.values()), 8) / 8.0; i += 1
    short = CD.energy_shortfall(pokemon)
    v[i] = min(short, 5) / 5.0 if short < 99 else 1.0; i += 1
    legal = CD.legal_attacks(pokemon)
    v[i] = 1.0 if legal else 0.0; i += 1
    v[i] = CD.best_damage(pokemon) / 300.0; i += 1
    v[i] = CD.max_damage_potential(pokemon) / 300.0; i += 1
    v[i] = min(CD.retreat_cost(pokemon), 4) / 4.0; i += 1
    v[i] = CD.prize_value(pokemon) / 3.0; i += 1
    tools = getattr(pokemon, "tools", None) or []
    v[i] = 1.0 if tools else 0.0; i += 1
    for s in _status_vec(player, pokemon):
        v[i] = s; i += 1
    cd = CD.card_of(pokemon)
    stage = 0.0
    if cd is not None:
        stage = 2.0 if getattr(cd, "stage2", False) else (
            1.0 if getattr(cd, "stage1", False) else 0.0)
    v[i] = stage / 2.0; i += 1
    if opposing_active is not None:
        ko, _d = CD.can_ko(opposing_active, pokemon)
        v[i] = 1.0 if ko else 0.0
    i += 1
    return v


@dataclass
class OptionRef:
    """B2: what an option DOES, and to WHICH objects.

    `source_index` and `target_index` point into `board_tokens`, so the scorer gathers the actual
    Pokemon representations rather than guessing from an action type.
    """

    option_index: int
    key: Tuple
    select_type: int
    context: int
    source_index: int = -1        # -1 = none, resolved to a learned null token
    target_index: int = -1
    hand_index: int = -1
    attack_id: int = -1
    energy_type: int = -1
    card_id: int = -1
    ordinal: int = 0
    remaining: int = 0

    def features(self) -> np.ndarray:
        v = np.zeros(OPT_DIM, dtype=np.float32)
        v[0] = min(self.select_type, 20) / 20.0
        v[1] = min(self.context, 30) / 30.0
        v[2] = 1.0 if self.source_index >= 0 else 0.0
        v[3] = 1.0 if self.target_index >= 0 else 0.0
        v[4] = (self.source_index + 1) / float(BOARD_SLOTS + 1)
        v[5] = (self.target_index + 1) / float(BOARD_SLOTS + 1)
        v[6] = 1.0 if self.hand_index >= 0 else 0.0
        v[7] = (self.hand_index + 1) / float(N_HAND + 1)
        v[8] = self.card_id / 2000.0 if self.card_id >= 0 else 0.0
        v[9] = 1.0 if self.attack_id >= 0 else 0.0
        v[10] = self.attack_id / 2000.0 if self.attack_id >= 0 else 0.0
        if 0 <= self.energy_type < N_ENERGY_TYPES:
            v[11 + self.energy_type] = 1.0
        v[11 + N_ENERGY_TYPES] = min(self.ordinal, 8) / 8.0
        v[12 + N_ENERGY_TYPES] = min(self.remaining, 8) / 8.0
        v[13 + N_ENERGY_TYPES] = min(self.option_index, 60) / 60.0
        return v


def _board_list(view) -> List[Tuple[Optional[Any], bool, bool, int]]:
    """The 12 FIXED positions. Order is part of the contract with the option refs."""
    out = []
    for side, mine in (("mine", True), ("theirs", False)):
        b = view.board(side)
        act = (b.get("active") or [None])
        out.append(((act[0] if act else None), mine, True, 0))
        bench = [x for x in (b.get("bench") or [])]
        for s in range(BENCH_SLOTS):
            out.append(((bench[s] if s < len(bench) else None), mine, False, s + 1))
    return out


# Positions of the fields we resolve, inside CanonicalOption.fields (c019_core.OPTION_FIELDS).
# Read by NAME here rather than by literal index so a reordering of OPTION_FIELDS cannot silently
# repoint them at the wrong values.
_F = {n: i for i, n in enumerate(K.OPTION_FIELDS)}

# cg.api.AreaType
AREA_ACTIVE, AREA_BENCH, AREA_HAND, AREA_DISCARD = 4, 5, 2, 3


def _slot_index(area: int, idx: int, player_is_mine: bool) -> int:
    """Board-token index for (area, index, owner). Layout is fixed by `_board_list`:

        0                = our active
        1..5             = our bench 1..5
        6                = opponent active
        7..11            = opponent bench 1..5
    """
    base = 0 if player_is_mine else (1 + BENCH_SLOTS)
    if area == AREA_ACTIVE:
        return base
    if area == AREA_BENCH:
        if 0 <= idx < BENCH_SLOTS:
            return base + 1 + idx
    return -1


def build_option_refs(sel, view, board, your_index: Optional[int] = None) -> List[OptionRef]:
    """Resolve each canonical option to the board/hand objects it references (B2).

    The engine gives this structurally -- `area`, `index`, `playerIndex`, `inPlayArea`,
    `inPlayIndex`, `cardId`, `attackId` -- so it is read directly. An earlier version scraped
    integers out of the canonical key's top level and resolved 0 of 556 options, because the
    key nests those values inside a tuple that an `isinstance(x, int)` filter skips. The mechanism
    existed and was inert, which is exactly the failure mode
    `references/C019_AUDIT_FINDINGS.md` #17 warns about.
    """
    opts = K.canonical_options(sel)
    hand = view.my_hand()
    hand_ids = [int(getattr(c, "id", -1) or -1) for c in hand]
    me = int(your_index if your_index is not None else getattr(view, "_yi", 0) or 0)

    st = int(getattr(sel, "selectType", None) or getattr(sel, "type", -1) or -1)
    ctx = int(getattr(sel, "context", -1) or -1)
    mn = int(getattr(sel, "minCount", 0) or 0)
    mx = int(getattr(sel, "maxCount", 1) or 1)

    refs = []
    for o in opts:
        f = o.fields
        def fld(name, default=-1):
            i = _F.get(name)
            return int(f[i]) if (i is not None and i < len(f)) else default

        area = fld("area")
        idx = fld("index")
        owner = fld("playerIndex")
        in_area = fld("inPlayArea")
        in_idx = fld("inPlayIndex")
        mine = (owner < 0) or (owner == me)

        r = OptionRef(option_index=int(o.option_index), key=o.key(), select_type=st,
                      context=ctx, remaining=max(mn, mx),
                      card_id=int(o.referenced_card_id or -1),
                      attack_id=int(o.referenced_attack_id or -1),
                      ordinal=0)
        # SOURCE: where the option acts FROM -- a hand card, or a board slot
        if area == AREA_HAND and idx >= 0:
            r.hand_index = idx if idx < N_HAND else -1
            if r.card_id < 0 and 0 <= idx < len(hand_ids):
                r.card_id = hand_ids[idx]
        else:
            r.source_index = _slot_index(area, idx, mine)
        # TARGET: the in-play object the option acts ON
        if in_area >= 0:
            r.target_index = _slot_index(in_area, in_idx, mine)
        # an attack names its own attacker when no explicit source was given
        if r.source_index < 0 and r.attack_id >= 0:
            r.source_index = _slot_index(AREA_ACTIVE, 0, True)
        # energy type, when the option names one
        r.energy_type = fld("energyIndex")
        refs.append(r)
    return refs


def encode(observation, your_index: Optional[int] = None) -> Dict[str, np.ndarray]:
    """Full slot-aware encoding. Board objects keep identity all the way to option scoring."""
    v = K.visible_view(observation, your_index)
    counts = v.counts()
    board = _board_list(v)
    my_active = board[0][0]
    op_active = board[1 + BENCH_SLOTS][0]

    bt = np.zeros((BOARD_SLOTS, BOARD_DIM), dtype=np.float32)
    for i, (pk, mine, act, slot) in enumerate(board):
        opposing = op_active if mine else my_active
        bt[i] = encode_board_token(pk, mine, act, slot,
                                   player=(v.me if mine else v.opp),
                                   opposing_active=opposing)

    hand = v.my_hand()[:N_HAND]
    ht = np.zeros((N_HAND, HAND_DIM), dtype=np.float32)
    for i, c in enumerate(hand):
        cid = int(getattr(c, "id", 0) or 0)
        cd = CD.card(cid)
        ht[i, 0] = 1.0
        ht[i, 1] = cid / 2000.0
        ht[i, 2] = _f(getattr(cd, "cardType", 0)) / 8.0 if cd else 0.0
        ht[i, 3] = 1.0 if (cd and getattr(cd, "basic", False)) else 0.0
        ht[i, 4] = 1.0 if (cd and getattr(cd, "ex", False)) else 0.0
        ht[i, 5] = _f(getattr(cd, "hp", 0)) / 400.0 if cd else 0.0
        ht[i, 6] = _f(getattr(cd, "energyType", 0)) / 12.0 if cd else 0.0
        ht[i, 7] = i / float(N_HAND)

    g = np.zeros(GLOBAL_DIM, dtype=np.float32)
    g[0] = counts["my_prize"] / 6.0
    g[1] = counts["opp_prize"] / 6.0
    g[2] = counts["my_hand"] / 12.0
    g[3] = counts["opp_hand"] / 12.0
    g[4] = counts["my_deck"] / 60.0
    g[5] = counts["opp_deck"] / 60.0
    g[6] = len(v.discard("mine")) / 60.0
    g[7] = len(v.discard("theirs")) / 60.0
    g[8] = 1.0 if my_active is not None else 0.0
    g[9] = 1.0 if op_active is not None else 0.0
    if my_active is not None and op_active is not None:
        ko, dmg = CD.can_ko(my_active, op_active)
        g[10] = 1.0 if ko else 0.0
        g[11] = dmg / 300.0
        oko, odmg = CD.can_ko(op_active, my_active)
        g[12] = 1.0 if oko else 0.0
        g[13] = odmg / 300.0
    g[14] = sum(1 for p, _m, _a, _s in board[:1 + BENCH_SLOTS] if p is not None) / 6.0
    g[15] = sum(1 for p, _m, _a, _s in board[1 + BENCH_SLOTS:] if p is not None) / 6.0

    sel = getattr(observation, "select", None)
    refs = (build_option_refs(sel, v, board, getattr(v, '_yi', None))
            if sel is not None else [])
    n_opt = min(len(refs), N_OPT)
    ot = np.zeros((N_OPT, OPT_DIM), dtype=np.float32)
    src = np.full(N_OPT, BOARD_SLOTS, dtype=np.int64)      # BOARD_SLOTS = learned null token
    tgt = np.full(N_OPT, BOARD_SLOTS, dtype=np.int64)
    mask = np.zeros(N_OPT, dtype=np.float32)
    for i, r in enumerate(refs[:N_OPT]):
        ot[i] = r.features()
        if r.source_index >= 0:
            src[i] = r.source_index
        if r.target_index >= 0:
            tgt[i] = r.target_index
        mask[i] = 1.0
    if sel is not None:
        g[16] = int(getattr(sel, "minCount", 0) or 0) / 8.0
        g[17] = int(getattr(sel, "maxCount", 1) or 1) / 8.0
        g[18] = int(getattr(sel, "selectType", 0) or 0) / 20.0
        g[19] = int(getattr(sel, "context", 0) or 0) / 30.0
        g[20] = n_opt / float(N_OPT)

    return {"board": bt, "hand": ht, "global": g, "opt": ot, "opt_mask": mask,
            "opt_src": src, "opt_tgt": tgt,
            "n_options": np.int64(n_opt),
            "min_count": np.int64(int(getattr(sel, "minCount", 0) or 0) if sel is not None else 0),
            "max_count": np.int64(int(getattr(sel, "maxCount", 1) or 1) if sel is not None else 0)}


def option_refs(observation, your_index: Optional[int] = None) -> List[OptionRef]:
    v = K.visible_view(observation, your_index)
    sel = getattr(observation, "select", None)
    if sel is None:
        return []
    return build_option_refs(sel, v, _board_list(v), getattr(v, "_yi", None))


def schema() -> Dict[str, Any]:
    return {"version": "c020.enc.v1", "board_slots": BOARD_SLOTS, "bench_slots": BENCH_SLOTS,
            "board_dim": BOARD_DIM, "hand_dim": HAND_DIM, "global_dim": GLOBAL_DIM,
            "opt_dim": OPT_DIM, "n_opt": N_OPT, "n_hand": N_HAND,
            "energy_types": N_ENERGY_TYPES,
            "slot_order": ["my_active"] + [f"my_bench_{i}" for i in range(1, BENCH_SLOTS + 1)]
                          + ["opp_active"] + [f"opp_bench_{i}" for i in range(1, BENCH_SLOTS + 1)],
            "null_token_index": BOARD_SLOTS,
            "corrects": ["#7 active/bench pooled", "#8 energy type/status/tool/target refs"]}
