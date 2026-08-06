from __future__ import annotations
from .manual_observation import get_card_id, semantic
GRIMMSNARL_EX_ID = 648
DARK_ENERGY_ID = 7

def _energy_count(card: dict) -> int:
    cards = (card or {}).get('energyCards') or []
    if cards:
        return sum((1 for e in cards if get_card_id(e) == DARK_ENERGY_ID))
    return sum((1 for e in (card or {}).get('energies') or [] if int(e or 0) == DARK_ENERGY_ID))

def _hp(card: dict) -> int:
    try:
        return int((card or {}).get('hp', 0) or 0)
    except Exception:
        return 0

def _max_hp(card: dict) -> int:
    try:
        return int((card or {}).get('maxHp', 0) or 0)
    except Exception:
        return 0

def choose(obs: dict):
    sel = obs.get('select') or {}
    opts = sel.get('option') or []
    context = int(sel.get('context', -1) if sel.get('context') is not None else -1)
    if context != 21:
        return (None, None)
    if int(sel.get('minCount', 0) or 0) != 1 or int(sel.get('maxCount', 0) or 0) != 1:
        return (None, None)
    if get_card_id(sel.get('effect')) != GRIMMSNARL_EX_ID:
        return (None, None)
    cur = obs.get('current') or {}
    players = cur.get('players') or []
    try:
        your = int(cur.get('yourIndex', 0) or 0)
    except Exception:
        return (None, None)
    if len(players) != 2 or your not in (0, 1):
        return (None, None)
    me = players[your]
    active = me.get('active') or []
    bench = me.get('bench') or []
    if len(active) != 1 or get_card_id(active[0]) != GRIMMSNARL_EX_ID:
        return (None, None)
    if _energy_count(active[0]) < 2:
        return (None, None)
    if _hp(active[0]) >= _max_hp(active[0]):
        return (None, None)
    sems = [semantic(obs, option) for option in opts]
    backup = []
    overfilled = []
    for option_index, option in enumerate(opts):
        if int(option.get('type', -1) if option.get('type') is not None else -1) != 3:
            continue
        if int(option.get('playerIndex', -1) if option.get('playerIndex') is not None else -1) != your:
            continue
        area = int(option.get('area', 0) or 0)
        idx = int(option.get('index', -1) if option.get('index') is not None else -1)
        if area == 4:
            card = active[0] if idx == 0 else None
        elif area == 5:
            card = bench[idx] if 0 <= idx < len(bench) else None
        else:
            card = None
        if not card:
            continue
        ec = _energy_count(card)
        cid = get_card_id(card)
        if area == 5 and cid == GRIMMSNARL_EX_ID and (ec < 2) and (_hp(card) == _max_hp(card)):
            backup.append((-_hp(card), ec, -_max_hp(card), idx, option_index))
        if area == 5 and ec >= 2:
            overfilled.append(option_index)
    if not backup or not overfilled:
        return (None, sems)
    backup.sort()
    return ([backup[0][4]], sems)
