"""Decision-importance taxonomy + semantic decision typing (c006 AC-05).

Classifies each teacher decision into one of four importance classes using
structural + semantic signals (NOT SelectContext alone):

    FORCED      only one legal action exists (policy cannot change the outcome)
    ROUTINE     a real but low-leverage choice
    TACTICAL    a meaningful board/resource choice
    HIGH_IMPACT a pivotal choice (attacking, damage-counter placement, promotion,
                passing up an available attack, ...)

Also assigns a single ``semantic_type`` per decision from a fixed vocabulary that
treats the contract-required semantic cases explicitly (attack choice in MAIN,
attack target, promotion, energy attach, evolution, search/target, retreat/switch,
Dragapult damage counter, end-turn while attack available, multi-select discard).

Pure/deterministic. Option-type ints follow ``cg.api.OptionType``.
"""

from __future__ import annotations

from typing import Any, Dict, List

# OptionType ints
OT_NUMBER, OT_YES, OT_NO, OT_CARD, OT_TOOL_CARD, OT_ENERGY_CARD, OT_ENERGY = 0, 1, 2, 3, 4, 5, 6
OT_PLAY, OT_ATTACH, OT_EVOLVE, OT_ABILITY, OT_DISCARD, OT_RETREAT, OT_ATTACK, OT_END, OT_SKILL, OT_SPECIAL = \
    7, 8, 9, 10, 11, 12, 13, 14, 15, 16

FORCED, ROUTINE, TACTICAL, HIGH_IMPACT = "FORCED", "ROUTINE", "TACTICAL", "HIGH_IMPACT"
IMPORTANCE_CLASSES = [FORCED, ROUTINE, TACTICAL, HIGH_IMPACT]

_PHANTOM_DIVE = 154  # Dragapult ex signature attack

_PROMOTION_CTX = {"TO_ACTIVE", "SETUP_ACTIVE_POKEMON", "SWITCH"}
_DAMAGE_CTX = {"DAMAGE_COUNTER", "DAMAGE_COUNTER_ANY", "DAMAGE", "REMOVE_DAMAGE_COUNTER"}
_SEARCH_CTX = {"TO_HAND", "TO_DECK", "TO_DECK_BOTTOM", "LOOK", "TO_PRIZE", "TO_FIELD"}
_ATTACH_CTX = {"ATTACH_FROM", "ATTACH_TO"}


def _is_forced(n_options: int, lo: int, hi: int) -> bool:
    if n_options <= 1 and lo >= 1:
        return True
    if hi == 0:
        return True
    if lo == hi == n_options and n_options >= 1:  # must take all
        return True
    return False


def classify(rec: Dict[str, Any]) -> Dict[str, Any]:
    ctx = rec["select_context"]
    opts = rec["legal_options"]
    n = len(opts)
    lo = rec.get("min_count", 0) or 0
    hi = rec.get("max_count", 0) or 0
    types = [o.get("type") for o in opts]
    has_attack = OT_ATTACK in types
    has_end = OT_END in types
    has_evolve = OT_EVOLVE in types
    has_attach = OT_ATTACH in types
    has_retreat = OT_RETREAT in types
    attack_ids = [o.get("attackId") for o in opts if o.get("type") == OT_ATTACK]
    phantom_available = _PHANTOM_DIVE in attack_ids
    is_multiselect = hi > 1
    forced = _is_forced(n, lo, hi)

    # ---- semantic type (single primary label) ----
    if ctx == "MAIN":
        if has_attack:
            semantic = "attack_choice_in_MAIN"
        else:
            semantic = "main_board_action"
    elif ctx in _DAMAGE_CTX:
        semantic = "dragapult_damage_counter" if ctx.startswith("DAMAGE_COUNTER") else "damage_effect"
    elif ctx in ("TO_ACTIVE", "SETUP_ACTIVE_POKEMON"):
        semantic = "promotion_to_active"
    elif ctx == "SWITCH":
        semantic = "retreat_switch"
    elif ctx in _ATTACH_CTX:
        semantic = "energy_attachment_target"
    elif ctx == "EVOLVE":
        semantic = "evolution_target"
    elif ctx == "DISCARD" or (is_multiselect and ctx in ("TO_HAND", "DISCARD_ENERGY")):
        semantic = "multiselect_discard_resource"
    elif ctx in _SEARCH_CTX:
        semantic = "search_card_target"
    elif ctx in ("TO_BENCH", "SETUP_BENCH_POKEMON"):
        semantic = "bench_placement"
    elif ctx in ("DISCARD_ENERGY", "DISCARD_ENERGY_CARD", "DISCARD_TOOL_CARD",
                 "SWITCH_ENERGY", "ATTACH_FROM"):
        semantic = "resource_discard_or_move"
    elif ctx == "ATTACK":
        semantic = "attack_target"
    elif ctx in ("IS_FIRST", "COIN_HEAD", "MULLIGAN"):
        semantic = "coin_or_setup_flag"
    elif ctx.endswith("_COUNT") or ctx == "DRAW_COUNT":
        semantic = "count_choice"
    elif ctx == "ACTIVATE":
        semantic = "ability_activation"
    else:
        semantic = "other"

    # ---- importance class ----
    if forced:
        importance = FORCED
    else:
        high = False
        if ctx == "MAIN" and has_attack:
            high = True                                   # choosing to attack / which attack
        if ctx == "MAIN" and has_end and has_attack:
            high = True                                   # end-turn while an attack is available
        if ctx in _DAMAGE_CTX:
            high = True                                   # Dragapult damage-counter placement
        if ctx in _PROMOTION_CTX and n > 1:
            high = True                                   # promotion / gust / switch target with choice
        if ctx == "ATTACK":
            high = True
        if phantom_available:
            high = True
        if high:
            importance = HIGH_IMPACT
        else:
            tactical = (
                has_evolve or has_attach or is_multiselect
                or ctx in _ATTACH_CTX or ctx == "EVOLVE" or ctx in _SEARCH_CTX
                or ctx in ("TO_BENCH", "SETUP_BENCH_POKEMON", "SETUP_ACTIVE_POKEMON")
                or has_retreat or ctx == "ACTIVATE"
            )
            importance = TACTICAL if tactical else ROUTINE

    return {
        "importance_class": importance,
        "semantic_type": semantic,
        "forced": forced,
        "n_options": n,
        "min_count": lo,
        "max_count": hi,
        "is_multiselect": is_multiselect,
        "attack_available": has_attack,
        "end_turn_available": has_end,
        "phantom_dive_available": phantom_available,
    }


def importance_weight(importance_class: str, weights: Dict[str, float] = None) -> float:
    w = weights or {FORCED: 0.0, ROUTINE: 1.0, TACTICAL: 2.0, HIGH_IMPACT: 4.0}
    return w.get(importance_class, 1.0)
