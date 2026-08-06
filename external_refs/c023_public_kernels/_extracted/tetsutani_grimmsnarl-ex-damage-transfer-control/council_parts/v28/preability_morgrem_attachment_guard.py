from __future__ import annotations
from .manual_observation import get_card_id, semantic
DARK_ENERGY_ID = 7
MUNKIDORI_ID = 112
MORGREM_ID = 647
GRIMMSNARL_EX_ID = 648

def _i(v, default=0):
    try:
        return int(v if v is not None else default)
    except Exception:
        return default

def _energy_count(card: dict) -> int:
    cards = (card or {}).get('energyCards') or []
    if cards:
        return len(cards)
    return len((card or {}).get('energies') or [])

def choose(obs: dict):
    sel = obs.get('select') or {}
    opts = sel.get('option') or []
    if _i(sel.get('context'), -1) != 0:
        return (None, None)
    if _i(sel.get('minCount'), 0) != 1 or _i(sel.get('maxCount'), 0) != 1:
        return (None, None)
    cur = obs.get('current') or {}
    if bool(cur.get('energyAttached')):
        return (None, None)
    if _i(cur.get('turn'), 0) < 10:
        return (None, None)
    players = cur.get('players') or []
    your = _i(cur.get('yourIndex'), -1)
    if len(players) != 2 or your not in (0, 1):
        return (None, None)
    me, opp = (players[your], players[1 - your])
    if len(me.get('prize') or []) < 5 or len(opp.get('prize') or []) > 2:
        return (None, None)
    active = me.get('active') or []
    if len(active) != 1:
        return (None, None)
    a = active[0]
    if get_card_id(a) != MORGREM_ID or _energy_count(a) != 0:
        return (None, None)
    hp, max_hp = (_i(a.get('hp'), 0), _i(a.get('maxHp'), 0))
    if hp <= 0 or max_hp <= 0 or hp > 40 or (hp >= max_hp):
        return (None, None)
    hand_ids = [get_card_id(x) for x in me.get('hand') or []]
    if GRIMMSNARL_EX_ID not in hand_ids or DARK_ENERGY_ID not in hand_ids:
        return (None, None)
    oa = opp.get('active') or []
    if len(oa) != 1 or _energy_count(oa[0]) < 2:
        return (None, None)
    if not any((get_card_id(c) == GRIMMSNARL_EX_ID and 0 < _i(c.get('hp'), 0) <= 40 and (_energy_count(c) >= 2) for c in opp.get('bench') or [])):
        return (None, None)
    sems = [semantic(obs, option) for option in opts]
    if not any((_i(s.get('type'), -1) == 10 for s in sems)):
        return (None, sems)
    if not any((_i(s.get('type'), -1) == 9 and _i(s.get('source_id'), 0) == GRIMMSNARL_EX_ID and (_i(s.get('target_id'), 0) == MORGREM_ID) and (_i(s.get('target_area'), 0) == 4) for s in sems)):
        return (None, sems)
    candidates = []
    for i, s in enumerate(sems):
        if _i(s.get('type'), -1) == 8 and _i(s.get('source_id'), 0) == DARK_ENERGY_ID and (_i(s.get('target_id'), 0) == MORGREM_ID) and (_i(s.get('target_area'), 0) == 4) and (_i(s.get('inplay_index'), -1) == 0):
            candidates.append(i)
    if not candidates:
        return (None, sems)
    return ([min(candidates)], sems)
