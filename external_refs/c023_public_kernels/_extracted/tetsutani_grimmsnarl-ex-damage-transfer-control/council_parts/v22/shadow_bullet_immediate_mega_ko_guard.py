from __future__ import annotations
from .manual_observation import get_card_id, semantic
GRIMMSNARL_EX_ID = 648
MEGA_KANGASKHAN_EX_ID = 756
SHADOW_BULLET_ATTACK_ID = 937
SHADOW_BULLET_DAMAGE = 180

def _hp(card: dict, default: int=999) -> int:
    try:
        return int((card or {}).get('hp', default) or default)
    except Exception:
        return default

def choose(obs: dict):
    sel = obs.get('select') or {}
    opts = sel.get('option') or []
    if int(sel.get('context', -1) if sel.get('context') is not None else -1) != 0:
        return (None, None)
    if int(sel.get('minCount', 0) or 0) != 1 or int(sel.get('maxCount', 0) or 0) != 1:
        return (None, None)
    cur = obs.get('current') or {}
    players = cur.get('players') or []
    try:
        your = int(cur.get('yourIndex', 0) or 0)
    except Exception:
        return (None, None)
    if len(players) != 2 or your not in (0, 1):
        return (None, None)
    me, opp = (players[your], players[1 - your])
    active = me.get('active') or []
    opp_active = opp.get('active') or []
    if len(active) != 1 or get_card_id(active[0]) != GRIMMSNARL_EX_ID:
        return (None, None)
    if not 0 < _hp(active[0]) <= SHADOW_BULLET_DAMAGE:
        return (None, None)
    if len(opp_active) != 1 or get_card_id(opp_active[0]) != MEGA_KANGASKHAN_EX_ID:
        return (None, None)
    if not 0 < _hp(opp_active[0]) <= SHADOW_BULLET_DAMAGE:
        return (None, None)
    if len(me.get('prize') or []) < 3 or len(opp.get('prize') or []) > 3:
        return (None, None)
    sems = [semantic(obs, option) for option in opts]
    attacks = [i for i, option in enumerate(opts) if int((option or {}).get('type', -1)) == 13 and int((option or {}).get('attackId', -1)) == SHADOW_BULLET_ATTACK_ID]
    if len(attacks) != 1:
        return (None, sems)
    if not any((i != attacks[0] and int((o or {}).get('type', -1)) in (7, 8, 9, 10) for i, o in enumerate(opts))):
        return (None, sems)
    return ([attacks[0]], sems)
