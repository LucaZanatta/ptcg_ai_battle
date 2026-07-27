"""c020 — exact card/attack metadata lookup shared by the evaluator and the encoder.

`MANDATORY_CHANGES A6` is explicit: "Do not infer attack readiness from total energy count
alone." That instruction is the whole reason this module exists. The starter kit exposes
`all_card_data()` and `all_attack()`, which carry typed attack costs, weaknesses, retreat costs
and rule-box status; c019's evaluator ignored all of it and counted energy cards, which is why a
Pokemon holding three Water energy looked "ready" for an attack costing two Fighting.

Everything here is derived from the official tables at import and cached, so the evaluator can be
called inside a search loop without repeated FFI work.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_CARDS: Dict[int, Any] = {}
_ATTACKS: Dict[int, Any] = {}
_LOADED = False

# EnergyType.COLORLESS is payable by ANY energy; every other type demands its own.
COLORLESS = 0


def _load():
    global _LOADED
    if _LOADED:
        return
    from cg import api as A
    try:
        for c in (A.all_card_data() or []):
            _CARDS[int(c.cardId)] = c
    except Exception:  # noqa: BLE001
        pass
    try:
        for a in (A.all_attack() or []):
            _ATTACKS[int(a.attackId)] = a
    except Exception:  # noqa: BLE001
        pass
    try:
        globals()["COLORLESS"] = int(A.EnergyType.COLORLESS)
    except Exception:  # noqa: BLE001
        pass
    _LOADED = True


def card(card_id) -> Optional[Any]:
    _load()
    try:
        return _CARDS.get(int(card_id))
    except (TypeError, ValueError):
        return None


def attack(attack_id) -> Optional[Any]:
    _load()
    try:
        return _ATTACKS.get(int(attack_id))
    except (TypeError, ValueError):
        return None


def card_of(pokemon) -> Optional[Any]:
    """Card metadata for a board Pokemon instance."""
    return card(getattr(pokemon, "id", None))


def attacks_of(pokemon) -> List[Any]:
    """Attack metadata for whatever this Pokemon can actually use."""
    cd = card_of(pokemon)
    if cd is None:
        return []
    out = []
    for aid in (getattr(cd, "attacks", None) or []):
        a = attack(aid)
        if a is not None:
            out.append(a)
    return out


def attached_energy(pokemon) -> Dict[int, int]:
    """Attached energy COUNTED BY TYPE. c019 only ever had the total."""
    out: Dict[int, int] = {}
    for e in (getattr(pokemon, "energies", None) or []):
        try:
            t = int(e)
        except (TypeError, ValueError):
            continue
        out[t] = out.get(t, 0) + 1
    return out


def cost_of(atk) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for e in (getattr(atk, "energies", None) or []):
        try:
            t = int(e)
        except (TypeError, ValueError):
            continue
        out[t] = out.get(t, 0) + 1
    return out


def can_pay(attached: Dict[int, int], cost: Dict[int, int]) -> bool:
    """Typed-energy legality.

    Specific requirements must be met by their own type; COLORLESS is then paid by whatever is
    left over. This is the check c019 lacked entirely.
    """
    pool = dict(attached)
    generic = 0
    for t, need in cost.items():
        if t == COLORLESS:
            generic += need
            continue
        have = pool.get(t, 0)
        if have < need:
            return False
        pool[t] = have - need
    return sum(pool.values()) >= generic


def legal_attacks(pokemon) -> List[Tuple[Any, Dict[int, int]]]:
    """Attacks this Pokemon can pay for RIGHT NOW, with their costs."""
    att = attached_energy(pokemon)
    out = []
    for a in attacks_of(pokemon):
        c = cost_of(a)
        if can_pay(att, c):
            out.append((a, c))
    return out


def best_damage(pokemon) -> int:
    """Highest damage among attacks that are actually payable now."""
    best = 0
    for a, _c in legal_attacks(pokemon):
        best = max(best, int(getattr(a, "damage", 0) or 0))
    return best


def max_damage_potential(pokemon) -> int:
    """Highest damage among ALL its attacks, payable or not — used for readiness gaps."""
    best = 0
    for a in attacks_of(pokemon):
        best = max(best, int(getattr(a, "damage", 0) or 0))
    return best


def energy_shortfall(pokemon) -> int:
    """Smallest number of additional energy needed to enable ANY attack.

    Zero means an attack is already legal. Used for "attacker readiness" and to tell a genuinely
    stranded energy pile from one that is one attachment away from working.
    """
    att = attached_energy(pokemon)
    best = 99
    for a in attacks_of(pokemon):
        c = cost_of(a)
        if can_pay(att, c):
            return 0
        need = 0
        pool = dict(att)
        generic = 0
        for t, k in c.items():
            if t == COLORLESS:
                generic += k
                continue
            have = pool.get(t, 0)
            if have < k:
                need += k - have
                pool[t] = 0
            else:
                pool[t] = have - k
        left = sum(pool.values())
        if left < generic:
            need += generic - left
        best = min(best, need)
    return best if best < 99 else 99


def prize_value(pokemon) -> int:
    """Prizes the OPPONENT takes for knocking this out. Rule-box Pokemon are worth more."""
    cd = card_of(pokemon)
    if cd is None:
        return 1
    if bool(getattr(cd, "megaEx", False)) or bool(getattr(cd, "tera", False)):
        return 3
    if bool(getattr(cd, "ex", False)):
        return 2
    return 1


def retreat_cost(pokemon) -> int:
    cd = card_of(pokemon)
    return int(getattr(cd, "retreatCost", 0) or 0) if cd else 0


def hp_now(pokemon) -> Tuple[int, int]:
    hp = int(getattr(pokemon, "hp", 0) or 0)
    mx = int(getattr(pokemon, "maxHp", 0) or 0) or hp
    return hp, mx


def weakness_multiplier(attacker, defender) -> float:
    """2x when the attacker's type matches the defender's weakness. Drives lethal detection."""
    acd, dcd = card_of(attacker), card_of(defender)
    if acd is None or dcd is None:
        return 1.0
    try:
        if int(getattr(dcd, "weakness", -1)) == int(getattr(acd, "energyType", -2)):
            return 2.0
    except (TypeError, ValueError):
        pass
    return 1.0


def effective_damage(attacker, defender, dmg: int) -> int:
    """Damage after weakness/resistance — what actually decides a knockout."""
    if dmg <= 0:
        return 0
    out = dmg * weakness_multiplier(attacker, defender)
    dcd, acd = card_of(defender), card_of(attacker)
    if dcd is not None and acd is not None:
        try:
            if int(getattr(dcd, "resistance", -1)) == int(getattr(acd, "energyType", -2)):
                out -= 30
        except (TypeError, ValueError):
            pass
    return int(max(0, out))


def can_ko(attacker, defender) -> Tuple[bool, int]:
    """Can `attacker` knock out `defender` this turn with a payable attack?"""
    hp, _mx = hp_now(defender)
    best = 0
    for a, _c in legal_attacks(attacker):
        best = max(best, effective_damage(attacker, defender,
                                          int(getattr(a, "damage", 0) or 0)))
    return (best >= hp > 0), best


def metadata_available() -> Dict[str, Any]:
    _load()
    return {"cards": len(_CARDS), "attacks": len(_ATTACKS),
            "colorless_id": COLORLESS,
            "usable": bool(_CARDS and _ATTACKS)}
