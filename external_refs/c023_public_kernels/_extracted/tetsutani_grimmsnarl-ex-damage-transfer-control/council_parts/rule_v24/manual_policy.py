from __future__ import annotations
from collections import Counter
DECK = [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 104, 104, 112, 112, 112, 112, 646, 646, 646, 646, 647, 647, 647, 648, 648, 648, 860, 860, 1079, 1079, 1079, 1080, 1086, 1086, 1086, 1086, 1097, 1097, 1097, 1122, 1137, 1152, 1152, 1152, 1152, 1182, 1182, 1219, 1219, 1219, 1219, 1227, 1227, 1227, 1227, 1231, 1259, 1259, 1259, 1259]
DARK = 7
FROSLASS = 104
MUNK = 112
IMP = 646
MORG = 647
GRIM = 648
SNORUNT = 860
CANDY = 1079
STAMP = 1080
POFFIN = 1086
NIGHT = 1097
POKGEAR = 1122
SCRAPPER = 1137
POKEPAD = 1152
BOSS = 1182
PETREL = 1219
LILLIE = 1227
DAWN = 1231
GYM = 1259
DAMAGE_ENGINE_IDS = {90, 120, 140, 342, 343, 345, 380, 401, 414, 431, 742, 756, 1071}
DAMAGE_TARGET_BONUS = {345: 15000, 401: 2000, 741: 2000, 648: 5000}
_HISTORY = []
_TURN = -1
_TURN_SOURCE = Counter()
_TURN_TYPE = Counter()

def reset():
    global _HISTORY, _TURN
    _HISTORY = []
    _TURN = -1
    _TURN_SOURCE.clear()
    _TURN_TYPE.clear()

def cid(x):
    return int(x.get('id', 0) or 0) if isinstance(x, dict) else 0

def serial(x):
    return int(x.get('serial', -1) if isinstance(x, dict) else -1)

def zone(player, area):
    return {2: player.get('hand') or [], 3: player.get('discard') or [], 4: player.get('active') or [], 5: player.get('bench') or [], 6: player.get('prize') or []}.get(int(area or 0), [])

def state(obs):
    cur = obs.get('current') or {}
    your = int(cur.get('yourIndex', 0) or 0)
    ps = cur.get('players') or [{}, {}]
    me = ps[your] if 0 <= your < len(ps) else {}
    opp = ps[1 - your] if len(ps) > 1 else {}
    return (cur, me, opp, your)

def resolve_source(obs, opt):
    cur, me, opp, your = state(obs)
    ps = cur.get('players') or [{}, {}]
    p = int(opt.get('playerIndex', your) if opt.get('playerIndex') is not None else your)
    if not 0 <= p < len(ps):
        p = your
    area = opt.get('area')
    idx = opt.get('index')
    obj = None
    z = 0
    if area == 1:
        arr = (obs.get('select') or {}).get('deck') or []
        z = 1
        if isinstance(idx, int) and 0 <= idx < len(arr):
            obj = arr[idx]
    elif area in (2, 3, 4, 5, 6):
        arr = zone(ps[p], area)
        z = int(area)
        if isinstance(idx, int) and 0 <= idx < len(arr):
            obj = arr[idx]
    elif isinstance(idx, int):
        arr = me.get('hand') or []
        z = 2
        if 0 <= idx < len(arr):
            obj = arr[idx]
    return (obj, z, 0 if p == your else 1)

def resolve_target(obs, opt):
    cur, me, opp, your = state(obs)
    ps = cur.get('players') or [{}, {}]
    p = int(opt.get('playerIndex', your) if opt.get('playerIndex') is not None else your)
    if not 0 <= p < len(ps):
        p = your
    area = opt.get('inPlayArea')
    idx = opt.get('inPlayIndex')
    if area is None and int(opt.get('type', -1) or -1) == 10:
        area = opt.get('area')
        idx = opt.get('index')
    arr = zone(ps[p], area) if area in (4, 5) else []
    obj = arr[idx] if isinstance(idx, int) and 0 <= idx < len(arr) else None
    return (obj, int(area or 0), 0 if p == your else 1)

def sem(obs, opt):
    src, sz, srel = resolve_source(obs, opt)
    tgt, ta, trel = resolve_target(obs, opt)
    return {'type': int(opt.get('type', -1) if opt.get('type') is not None else -1), 'source_id': cid(src), 'source_serial': serial(src), 'source_zone': sz, 'source_rel': srel, 'target_id': cid(tgt), 'target_serial': serial(tgt), 'target_area': ta, 'target_rel': trel, 'attack_id': int(opt.get('attackId', 0) or 0), 'area': int(opt.get('area', 0) or 0), 'index': int(opt.get('index', -1) if opt.get('index') is not None else -1), 'inplay_area': int(opt.get('inPlayArea', 0) or 0), 'inplay_index': int(opt.get('inPlayIndex', -1) if opt.get('inPlayIndex') is not None else -1)}

def board(player):
    out = []
    for area, key in ((4, 'active'), (5, 'bench')):
        for idx, x in enumerate(player.get(key) or []):
            hp = int(x.get('hp', 0) or 0)
            mh = int(x.get('maxHp', 0) or 0)
            out.append({'obj': x, 'area': area, 'index': idx, 'id': cid(x), 'hp': hp, 'maxhp': mh, 'damage': max(0, mh - hp), 'energy': len(x.get('energyCards') or []), 'appear': bool(x.get('appearThisTurn')), 'serial': serial(x)})
    return out

def option_board(obs, s):
    cur, me, opp, your = state(obs)
    side = opp if s.get('target_rel') == 1 or s.get('source_rel') == 1 else me
    area = s.get('target_area') or s.get('area')
    ip = s.get('inplay_index')
    idx = ip if s.get('target_area') and isinstance(ip, int) and (ip >= 0) else s.get('index')
    arr = side.get('active') if area == 4 else side.get('bench') if area == 5 else []
    if isinstance(idx, int) and 0 <= idx < len(arr):
        x = arr[idx]
        hp = int(x.get('hp', 0) or 0)
        mh = int(x.get('maxHp', 0) or 0)
        return {'obj': x, 'area': area, 'index': idx, 'id': cid(x), 'hp': hp, 'maxhp': mh, 'damage': max(0, mh - hp), 'energy': len(x.get('energyCards') or []), 'appear': bool(x.get('appearThisTurn')), 'serial': serial(x)}
    return None

def legal(obs, a):
    s = obs.get('select') or {}
    n = len(s.get('option') or [])
    mn = int(s.get('minCount', 0) or 0)
    mx = int(s.get('maxCount', 0) or 0)
    return isinstance(a, list) and mn <= len(a) <= mx and (len(a) == len(set(a))) and all((isinstance(i, int) and 0 <= i < n for i in a))

def choose_n_ranked(obs, scores, k=None, order_index=True):
    sel = obs.get('select') or {}
    n = len(sel.get('option') or [])
    mn = int(sel.get('minCount', 0) or 0)
    mx = int(sel.get('maxCount', 0) or 0)
    if k is None:
        k = mx
    k = max(mn, min(mx, n, int(k)))
    rank = sorted(range(n), key=lambda i: (-scores[i], i))[:k]
    return sorted(rank) if order_index else rank

def count_ids(items):
    return Counter((cid(x) for x in items))

def has_powered_munk(me):
    return any((b['id'] == MUNK and b['energy'] >= 1 for b in board(me)))

def own_damage(me):
    return sum((b['damage'] for b in board(me)))

def role_value(card_id):
    return {MUNK: 110, GRIM: 100, FROSLASS: 75, MORG: 65, IMP: 55, SNORUNT: 45}.get(card_id, 30)

def target_score(b, damage, prefer_engine=True):
    if not b:
        return -10 ** 9
    lethal = 1 if b['hp'] <= damage else 0
    score = lethal * 100000 + (300 - b['hp']) * 40 + b['damage'] * 2
    if prefer_engine:
        score += role_value(b['id']) * 60
    if not lethal and b['hp'] <= damage + 30:
        score += 5000
    if b['id'] == MUNK:
        score += 9000
    if b['id'] in (646, 647, 648):
        score += 1500
    return score

def choose_setup_active(obs, sems):
    pri = {IMP: 300, SNORUNT: 200, MUNK: 100}
    return [max(range(len(sems)), key=lambda i: (pri.get(sems[i]['source_id'], 0), -i))]

def choose_setup_bench(obs, sems):
    sel = obs.get('select') or {}
    mn = int(sel.get('minCount', 0) or 0)
    mx = int(sel.get('maxCount', 0) or 0)
    ids = [x['source_id'] for x in sems]
    picks = []
    if SNORUNT in ids:
        picks = [ids.index(SNORUNT)]
    if not picks and mn > 0 and (IMP in ids):
        picks = [ids.index(IMP)]
    return picks[:mx]

def choose_poffin(obs, sems):
    cur, me, opp, your = state(obs)
    turn = int(cur.get('turn', 0) or 0)
    sel = obs.get('select') or {}
    bench_space = max(0, 5 - len(me.get('bench') or []))
    cap = min(2, bench_space, int(sel.get('maxCount', 0) or 0))
    chosen = []
    for i, s in enumerate(sems):
        if s['source_id'] == IMP and len(chosen) < cap:
            chosen.append(i)
    if turn <= 5:
        for i, s in enumerate(sems):
            if s['source_id'] == SNORUNT and i not in chosen and (len(chosen) < cap):
                chosen.append(i)
    mn = int(sel.get('minCount', 0) or 0)
    if len(chosen) < mn:
        for i in range(len(sems)):
            if i not in chosen:
                chosen.append(i)
            if len(chosen) >= mn:
                break
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    hand = count_ids(me.get('hand') or [])
    chosen_ids = tuple((sems[i]['source_id'] for i in chosen))
    no_frost_line = own[SNORUNT] + own[FROSLASS] + hand[SNORUNT] + hand[FROSLASS] == 0
    partial_board = turn <= 4 and 1 <= len(me.get('bench') or []) <= 3 and no_frost_line and (mn == 0)
    if partial_board and chosen_ids == (IMP, SNORUNT):
        chosen = [chosen[0]]
    elif partial_board and chosen_ids == (SNORUNT,):
        chosen = []
    return sorted(chosen)

def _choose_search_compatibility(obs, sems, effect):
    cur, me, opp, your = state(obs)
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    hand = count_ids(me.get('hand') or [])
    disc = count_ids(me.get('discard') or [])
    prize = len(me.get('prize') or [])
    turn = int(cur.get('turn', 0) or 0)

    def first_of(order):
        seen = set()
        for wanted in order:
            if wanted in seen:
                continue
            seen.add(wanted)
            for i, s in enumerate(sems):
                if s['source_id'] == wanted:
                    return [i]
        return []

    def override_pick(pick):
        if not pick:
            return pick
        chosen = sems[pick[0]]['source_id']
        available = {s['source_id'] for s in sems}

        def take(card_id):
            if card_id not in available:
                return pick
            return next(([i] for i, s in enumerate(sems) if s['source_id'] == card_id), pick)
        if effect == GYM:
            if chosen == GRIM and hand[GRIM] >= 1:
                return take(IMP)
            if chosen == IMP and own[IMP] >= 3:
                return take(MORG)
        elif effect == POKEPAD:
            if chosen == MORG and (len(me.get('hand') or []) >= 6 or hand[SNORUNT] >= 1):
                return take(MUNK)
            if chosen == MUNK and own[SNORUNT] >= 2:
                return take(FROSLASS)
            if chosen == IMP and own[SNORUNT] >= 1:
                return take(MORG)
        elif effect == NIGHT:
            if chosen == IMP and turn >= 11:
                return take(DARK)
            if chosen == SNORUNT and (turn >= 9 or own[MUNK] >= 2):
                return take(DARK)
            if chosen == SNORUNT and MUNK in available:
                return take(MUNK)
            if chosen == DARK and hand[DARK] >= 1:
                return take(MUNK)
            if chosen == DARK and turn <= 6:
                return take(IMP)
        elif effect == PETREL:
            if chosen == CANDY and hand[GRIM] == 0:
                for card_id in (GYM, POKEPAD, NIGHT):
                    if card_id in available:
                        return take(card_id)
            if chosen == NIGHT and hand[DARK] >= 2:
                return take(POKEPAD)
        elif effect == DAWN:
            if chosen == MORG and own[SNORUNT] >= 2:
                return take(FROSLASS)
        return pick
    if effect == POKGEAR:
        return [0] if sems else []
    if effect == GYM:
        if turn <= 2:
            order = [IMP, MORG, GRIM]
        elif own[GRIM] == 0:
            if own[MORG] > 0 and hand[GRIM] == 0:
                order = [GRIM, MORG, IMP]
            elif own[IMP] > 0 and hand[MORG] == 0:
                order = [MORG, GRIM, IMP]
            else:
                order = [IMP, MORG, GRIM]
        elif own[IMP] > 0 and hand[MORG] == 0:
            order = [MORG, IMP, GRIM]
        elif own[MORG] > 0 and hand[GRIM] == 0 and (own[IMP] == 0):
            order = [GRIM, IMP, MORG]
        else:
            order = [IMP, MORG, GRIM]
        pick = first_of(order)
        if pick:
            return override_pick(pick)
    if effect == NIGHT:
        unpowered = sum((1 for b in board(me) if b['id'] == MUNK and b['energy'] == 0))
        order = []
        if own[MUNK] == 0:
            order.append(MUNK)
        if unpowered > 0:
            order.append(DARK)
        if own[IMP] == 0 and turn <= 5:
            order.append(IMP)
        if own[MORG] > 0:
            order.append(GRIM)
        if own[IMP] > 0 and own[MORG] == 0:
            order.append(MORG)
        if own[SNORUNT] > 0 and own[FROSLASS] == 0:
            order.append(FROSLASS)
        if own[SNORUNT] + own[FROSLASS] == 0:
            order.append(SNORUNT)
        order += [MUNK, IMP, DARK, GRIM, MORG, SNORUNT, FROSLASS]
        pick = first_of(order)
        if pick:
            return override_pick(pick)
    if effect == PETREL:
        available = {s['source_id'] for s in sems}
        hand_size = len(me.get('hand') or [])
        useful_discard = disc[DARK] + sum((disc[x] for x in (MUNK, IMP, MORG, GRIM, SNORUNT, FROSLASS)))
        unpowered = sum((1 for b in board(me) if b['id'] == MUNK and b['energy'] == 0))
        missing_froslass = own[SNORUNT] > 0 and own[FROSLASS] == 0
        order = []
        if STAMP in available and hand[STAMP] == 0:
            order.append(STAMP)
        if own[GRIM] == 0:
            if own[IMP] > 0 and hand[CANDY] == 0:
                order.append(CANDY)
            if GYM in available and hand[GYM] == 0:
                order.append(GYM)
            if own[IMP] == 0 or own[MUNK] < 2 or missing_froslass:
                order.append(POKEPAD)
            if hand_size <= 5 and hand[LILLIE] == 0:
                order.append(LILLIE)
            if useful_discard >= 2:
                order.append(NIGHT)
            order += [POKEPAD, GYM, CANDY, NIGHT, LILLIE, POFFIN, SCRAPPER, BOSS]
        else:
            recover_now = disc[MUNK] > 0 and own[MUNK] < 2 or (disc[DARK] > 0 and unpowered > 0) or (disc[GRIM] > 0 and own[MORG] > 0) or (disc[MORG] > 0 and own[IMP] > 0)
            if recover_now or (turn >= 5 and useful_discard >= 2):
                order.append(NIGHT)
            if own[MUNK] < 2 or missing_froslass:
                order.append(POKEPAD)
            if GYM in available and hand[GYM] == 0:
                order.append(GYM)
            if own[IMP] > 0 and hand[CANDY] == 0:
                order.append(CANDY)
            if hand_size <= 5 and hand[LILLIE] == 0:
                order.append(LILLIE)
            order += [NIGHT, POKEPAD, GYM, CANDY, LILLIE, SCRAPPER, POFFIN, BOSS]
        pick = first_of(order)
        if pick:
            return override_pick(pick)
    scores = []
    for s in sems:
        x = s['source_id']
        score = 0
        if effect == GYM:
            if turn <= 2:
                desired = IMP
            elif own[MORG] > 0 and hand[GRIM] == 0:
                desired = GRIM
            elif own[IMP] > 0 and hand[MORG] == 0:
                desired = MORG
            elif own[IMP] == 0:
                desired = IMP
            elif own[GRIM] == 0 and hand[MORG] > 0:
                desired = GRIM
            else:
                desired = IMP if own[IMP] < 1 else MORG if own[MORG] < 1 else GRIM
            score = 10000 if x == desired else {IMP: 4200, MORG: 4000, GRIM: 3500}.get(x, 0)
        elif effect == POKEPAD:
            full_bench = len(me.get('bench') or []) >= 5
            if full_bench and turn >= 4 and (own[SNORUNT] > 0) and (x == FROSLASS):
                score = 12000
            elif full_bench and turn >= 4 and (own[IMP] > 0) and (x == MORG):
                score = 11500
            else:
                score = {MUNK: 10000, IMP: 9000, MORG: 8000, FROSLASS: 7000, SNORUNT: 6000}.get(x, 0)
        elif effect == NIGHT:
            unpowered = sum((1 for b in board(me) if b['id'] == MUNK and b['energy'] == 0))
            missing_chain = own[IMP] == 0 or (own[MORG] == 0 and own[GRIM] == 0)
            if x == DARK:
                score = 7600 if unpowered > 0 and (not cur.get('energyAttached')) else 4300
            elif x == IMP:
                score = 7500 if own[IMP] == 0 else 4700
            elif x == MUNK:
                score = 7300 if own[MUNK] < 2 else 4600
            elif x == GRIM:
                score = 7000 if own[MORG] > 0 or (own[IMP] > 0 and hand[CANDY]) else 4200
            elif x == MORG:
                score = 6800 if own[IMP] > 0 and own[MORG] == 0 else 4400
            elif x == SNORUNT:
                score = 5600 if own[SNORUNT] + own[FROSLASS] == 0 else 3600
            elif x == FROSLASS:
                score = 5500 if own[SNORUNT] > 0 and own[FROSLASS] == 0 else 3500
        elif effect == PETREL:
            if x == STAMP:
                score = 10000 if hand[STAMP] == 0 else 2600
            elif x == NIGHT:
                score = 7600 if turn >= 5 or disc[DARK] + sum((disc[p] for p in (IMP, MUNK, MORG, GRIM, SNORUNT, FROSLASS))) > 0 else 4500
            elif x == POKEPAD:
                score = 6900 if own[MUNK] < 2 or (own[SNORUNT] > 0 and own[FROSLASS] == 0) else 4300
            elif x == GYM:
                score = 6500 if own[GRIM] == 0 and (not cur.get('stadiumPlayed')) else 3500
            elif x == CANDY:
                score = 6200 if own[IMP] > 0 and own[GRIM] == 0 else 3200
            elif x == LILLIE:
                score = 5900 if len(me.get('hand') or []) <= 4 else 3000
            elif x == POFFIN:
                score = 4700 if turn <= 3 and len(me.get('bench') or []) <= 2 else 1800
            elif x == SCRAPPER:
                score = 4000 if any((p.get('toolCards') or [] for p in (opp.get('active') or []) + (opp.get('bench') or []))) else 1000
            elif x == BOSS:
                score = 3500
        elif effect == DAWN:
            if x == MUNK:
                score = 7000 + (1000 if own[MUNK] < 2 else 0)
            elif x == MORG:
                score = 6500 + (1200 if own[IMP] > 0 else 0)
            elif x == GRIM:
                score = 6400 + (1200 if own[MORG] > 0 or own[IMP] > 0 else 0)
            elif x == FROSLASS:
                score = 5900 + (1200 if own[SNORUNT] > 0 else 0)
            elif x == IMP:
                score = 5200 + (900 if own[IMP] == 0 else 0)
            elif x == SNORUNT:
                score = 4500 + (700 if own[SNORUNT] + own[FROSLASS] == 0 else 0)
        elif effect == POKGEAR:
            if x == LILLIE:
                score = 6000 + (1000 if len(me.get('hand') or []) <= 4 else 0)
            elif x == PETREL:
                score = 5800
            elif x == BOSS:
                score = 5000 if any((b['hp'] <= 180 for b in board(opp)[1:])) else 3500
            else:
                score = 500 if x else 0
        else:
            score = 1000 - role_value(x)
        scores.append(score)
    sel = obs.get('select') or {}
    mn = int(sel.get('minCount', 0) or 0)
    if not scores:
        return []
    best = max(range(len(scores)), key=lambda i: (scores[i], -i))
    if mn == 0 and scores[best] <= 0:
        return []
    return override_pick([best])

class SearchObjective:
    COMPLETE_FROSLASS_NOW = 'complete_froslass_now'
    COMPLETE_PRIMARY_NOW = 'complete_primary_now'
    COMPLETE_PRIMARY = 'complete_primary'
    BUILD_BACKUP_PRIMARY = 'build_backup_primary'
    BUILD_DAMAGE_NETWORK = 'build_damage_network'
    BUILD_FROSLASS_ENGINE = 'build_froslass_engine'
    RECOVER_ENERGY = 'recover_energy'
    RECOVER_POKEMON = 'recover_pokemon'
    RECYCLE_TRAINERS = 'recycle_trainers'
    SECURE_DISRUPTION = 'secure_disruption'
    REFRESH_HAND = 'refresh_hand'
    DIRECT_SUPPORTER = 'direct_supporter'
    COMPATIBILITY = 'compatibility'

def _search_ledger(obs, sems, effect):
    cur, me, opp, your = state(obs)
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    hand = count_ids(me.get('hand') or [])
    disc = count_ids(me.get('discard') or [])
    available = Counter((s['source_id'] for s in sems))
    own_b = board(me)
    unpowered_munks = sum((1 for b in own_b if b['id'] == MUNK and b['energy'] == 0))
    immediate_candy_primary = bool(effect == GYM and own[GRIM] == 0 and (hand[GRIM] == 0) and (own[IMP] >= 1) and (hand[CANDY] >= 1) and (available[GRIM] >= 1))
    immediate_froslass_completion = bool(effect == POKEPAD and own[SNORUNT] >= 1 and (own[FROSLASS] == 0) and (int(cur.get('turn', 0) or 0) >= 4) and (len(me.get('bench') or []) >= 4) and (available[FROSLASS] >= 1))
    return {'cur': cur, 'me': me, 'opp': opp, 'effect': effect, 'turn': int(cur.get('turn', 0) or 0), 'own': own, 'hand': hand, 'disc': disc, 'available': available, 'hand_n': len(me.get('hand') or []), 'bench_n': len(me.get('bench') or []), 'own_board': own_b, 'unpowered_munks': unpowered_munks, 'immediate_candy_primary': immediate_candy_primary, 'immediate_froslass_completion': immediate_froslass_completion, 'supporter_played': bool(cur.get('supporterPlayed')), 'energy_attached': bool(cur.get('energyAttached')), 'stadium_played': bool(cur.get('stadiumPlayed')), 'turn_used_gym': _TURN_SOURCE[GYM], 'turn_used_poffin': _TURN_SOURCE[POFFIN], 'turn_used_pokepad': _TURN_SOURCE[POKEPAD], 'turn_used_petrel': _TURN_SOURCE[PETREL], 'turn_used_night': _TURN_SOURCE[NIGHT]}

def _search_objectives(ledger):
    effect = ledger['effect']
    own = ledger['own']
    hand = ledger['hand']
    disc = ledger['disc']
    q = []
    if ledger['immediate_froslass_completion']:
        q.append(SearchObjective.COMPLETE_FROSLASS_NOW)
    if ledger['immediate_candy_primary']:
        q.append(SearchObjective.COMPLETE_PRIMARY_NOW)
    if effect == GYM:
        q += [SearchObjective.COMPLETE_PRIMARY, SearchObjective.BUILD_BACKUP_PRIMARY]
    elif effect == POKEPAD:
        if own[MUNK] < 2:
            q.append(SearchObjective.BUILD_DAMAGE_NETWORK)
        if own[SNORUNT] > 0 and own[FROSLASS] == 0:
            q.append(SearchObjective.BUILD_FROSLASS_ENGINE)
        q.append(SearchObjective.BUILD_BACKUP_PRIMARY)
    elif effect == NIGHT:
        if ledger['unpowered_munks'] > 0 and disc[DARK] > 0:
            q.append(SearchObjective.RECOVER_ENERGY)
        q.append(SearchObjective.RECOVER_POKEMON)
    elif effect == PETREL:
        if hand[STAMP] == 0:
            q.append(SearchObjective.SECURE_DISRUPTION)
        q += [SearchObjective.RECYCLE_TRAINERS, SearchObjective.REFRESH_HAND]
    elif effect == DAWN:
        q += [SearchObjective.COMPLETE_PRIMARY, SearchObjective.BUILD_DAMAGE_NETWORK, SearchObjective.BUILD_FROSLASS_ENGINE]
    elif effect == POKGEAR:
        q.append(SearchObjective.DIRECT_SUPPORTER)
    q.append(SearchObjective.COMPATIBILITY)
    return list(dict.fromkeys(q))

def _search_objective_for_card(effect, card_id, ledger):
    if effect == GYM:
        if card_id == GRIM and ledger['immediate_candy_primary']:
            return SearchObjective.COMPLETE_PRIMARY_NOW
        if card_id in (MORG, GRIM):
            return SearchObjective.COMPLETE_PRIMARY
        if card_id == IMP:
            return SearchObjective.BUILD_BACKUP_PRIMARY
    if effect in (POKEPAD, DAWN):
        if card_id == FROSLASS and ledger.get('immediate_froslass_completion'):
            return SearchObjective.COMPLETE_FROSLASS_NOW
        if card_id == MUNK:
            return SearchObjective.BUILD_DAMAGE_NETWORK
        if card_id in (SNORUNT, FROSLASS):
            return SearchObjective.BUILD_FROSLASS_ENGINE
        if card_id in (IMP, MORG, GRIM):
            return SearchObjective.BUILD_BACKUP_PRIMARY
    if effect == NIGHT:
        if card_id == DARK:
            return SearchObjective.RECOVER_ENERGY
        return SearchObjective.RECOVER_POKEMON
    if effect == PETREL:
        if card_id == STAMP:
            return SearchObjective.SECURE_DISRUPTION
        if card_id == LILLIE:
            return SearchObjective.REFRESH_HAND
        return SearchObjective.RECYCLE_TRAINERS
    if effect == POKGEAR:
        return SearchObjective.DIRECT_SUPPORTER
    return SearchObjective.COMPATIBILITY

def _build_search_queue(obs, sems, ledger, compatibility_pick):
    objectives = _search_objectives(ledger)
    rank = {o: i for i, o in enumerate(objectives)}
    compat = set(compatibility_pick or [])
    tickets = []
    for i, s in enumerate(sems):
        obj = _search_objective_for_card(ledger['effect'], s['source_id'], ledger)
        tickets.append({'objective': obj, 'objective_rank': rank.get(obj, len(rank)), 'card_id': s['source_id'], 'serial': s['source_serial'], 'index': i, 'compatibility_selected': i in compat})
    return (objectives, tickets)

def _select_search_ticket(queue, ledger, compatibility_pick):
    selected = None
    if compatibility_pick:
        idx = compatibility_pick[0]
        selected = next((t for t in queue if t['index'] == idx), None)
    if ledger['immediate_candy_primary']:
        direct = [t for t in queue if t['objective'] == SearchObjective.COMPLETE_PRIMARY_NOW and t['card_id'] == GRIM]
        if direct:
            selected = min(direct, key=lambda t: t['index'])
    compat_card = selected['card_id'] if selected is not None else 0
    if ledger.get('immediate_froslass_completion') and compat_card == MUNK:
        direct = [t for t in queue if t['objective'] == SearchObjective.COMPLETE_FROSLASS_NOW and t['card_id'] == FROSLASS]
        if direct:
            selected = min(direct, key=lambda t: t['index'])
    return selected

def _resolve_search_index(queue, ticket):
    if ticket is None:
        return None
    same = [t for t in queue if t['card_id'] == ticket['card_id'] and t['objective'] == ticket['objective']]
    return min(same, key=lambda t: t['index'])['index'] if same else ticket['index']

def build_search_plan(obs, sems, effect):
    ledger = _search_ledger(obs, sems, effect)
    compatibility = _choose_search_compatibility(obs, sems, effect)
    objectives, queue = _build_search_queue(obs, sems, ledger, compatibility)
    ticket = _select_search_ticket(queue, ledger, compatibility)
    index = _resolve_search_index(queue, ticket)
    if ticket is None:
        selected = list(compatibility)
    else:
        selected = [index] if index is not None else []
    return {'objectives': objectives, 'queue': queue, 'ledger': ledger, 'selected_objective': None if ticket is None else ticket['objective'], 'selected_card_id': None if ticket is None else ticket['card_id'], 'selected_indices': selected, 'compatibility_indices': list(compatibility)}

def explain_search_plan(obs):
    sel = (obs or {}).get('select') or {}
    sems = [sem(obs, o) for o in sel.get('option') or []]
    effect = cid(sel.get('effect'))
    if not sems:
        return {'objectives': [], 'selected_card_id': None, 'selected_indices': []}
    p = build_search_plan(obs, sems, effect)
    L = p['ledger']
    return {'effect': effect, 'turn': L['turn'], 'objectives': p['objectives'], 'selected_objective': p['selected_objective'], 'selected_card_id': p['selected_card_id'], 'selected_indices': p['selected_indices'], 'compatibility_indices': p['compatibility_indices'], 'resources': {'hand_n': L['hand_n'], 'bench_n': L['bench_n'], 'own_imp': L['own'][IMP], 'own_morg': L['own'][MORG], 'own_grim': L['own'][GRIM], 'hand_candy': L['hand'][CANDY], 'hand_grim': L['hand'][GRIM], 'immediate_candy_primary': L['immediate_candy_primary']}}

def choose_search(obs, sems, effect):
    return build_search_plan(obs, sems, effect)['selected_indices']

def choose_rare_candy(obs, sems):
    scores = []
    for s in sems:
        score = 10000 if s['source_id'] == GRIM and s['target_id'] == IMP else 0
        scores.append(score)
    return [max(range(len(scores)), key=lambda i: (scores[i], -i))]

def choose_punk_targets(obs, sems):
    cur, me, opp, your = state(obs)
    bmap = {(b['area'], b['index']): b for b in board(me)}
    scores = []
    for s in sems:
        b = option_board(obs, s)
        score = 0
        if b:
            missing = max(0, 2 - b['energy'])
            if b['id'] == GRIM:
                score = 10000 + missing * 3000 + (1000 if b['area'] == 4 else 0)
            elif b['id'] == IMP:
                score = 6500 + missing * 1800
            elif b['id'] == MORG:
                score = 6200 + missing * 2000
            else:
                score = 100
            if b['energy'] >= 2:
                score -= 8000
        scores.append(score)
    return [max(range(len(scores)), key=lambda i: (scores[i], -i))]

def choose_punk_energy_count(obs, sems):
    sel = obs.get('select') or {}
    mx = int(sel.get('maxCount', 0) or 0)
    mn = int(sel.get('minCount', 0) or 0)
    offered = len(sel.get('option') or [])
    cur, me, opp, your = state(obs)
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    if offered <= 1:
        k = offered
    elif offered == 2:
        k = 2
    elif offered <= 4:
        k = 2
    elif offered in (5, 6) and own[GRIM] >= 2:
        k = 2
    elif offered <= 7:
        k = 3
    elif offered == 8:
        k = 4
    else:
        k = 5
    k = max(mn, min(mx, offered, k))
    return list(range(k))

def choose_adrena_source(obs, sems):
    activator_serial = None
    for h in reversed(_HISTORY):
        if h.get('type') == 10 and h.get('source_id') == MUNK:
            activator_serial = h.get('source_serial')
            break
    boards = [option_board(obs, s) for s in sems]
    if activator_serial is not None:
        for i, b in enumerate(boards):
            if b and b.get('serial') == activator_serial and (b['damage'] >= 50):
                return [i]
    powered_munks = [(i, b) for i, b in enumerate(boards) if b and b['id'] == MUNK and (b['damage'] >= 40)]
    if powered_munks:
        return [max(powered_munks, key=lambda x: (x[1]['damage'], 1 if x[1]['area'] == 4 else 0, -x[0]))[0]]
    cur, me, opp, your = state(obs)
    active_180 = any((b and b['id'] == GRIM and (b['area'] == 4) and (b['damage'] == 180) for b in boards))
    early_munk30 = [(i, b) for i, b in enumerate(boards) if b and b['id'] == MUNK and (b['damage'] == 30)]
    if int(cur.get('turn', 0) or 0) <= 11 and active_180 and early_munk30:
        return [min(early_munk30, key=lambda x: x[0])[0]]
    active_grim = [(i, b) for i, b in enumerate(boards) if b and b['id'] == GRIM and (b['area'] == 4) and (b['damage'] >= 30)]
    if active_grim:
        return [active_grim[0][0]]
    scores = []
    for i, b in enumerate(boards):
        if not b:
            scores.append((-1, -1, -i))
            continue
        scores.append((1 if b['area'] == 4 else 0, b['damage'], -i))
    return [max(range(len(scores)), key=lambda i: scores[i])]

def choose_damage_target(obs, sems, damage, context):
    boards = [option_board(obs, s) for s in sems]
    valid = [b for b in boards if b]
    min_hp = min((b['hp'] for b in valid), default=10 ** 9)
    munk_window = 40 if context == 13 else 20
    scores = []
    for i, b in enumerate(boards):
        if not b:
            scores.append(-10 ** 12)
            continue
        lethal = b['hp'] <= damage
        score = (100000 if lethal else 0) - b['hp'] * 100 + role_value(b['id']) * 20
        if b['id'] in DAMAGE_ENGINE_IDS:
            score += 1000 if context == 13 else 2000
        if context == 13:
            score += DAMAGE_TARGET_BONUS.get(b['id'], 0)
        if b['id'] == MUNK and b['hp'] <= min_hp + munk_window:
            score += 5000 if context == 13 else 7000
        score += i if context == 15 else -i
        scores.append(score)
    winner = max(range(len(scores)), key=lambda i: scores[i])
    if context == 15:
        cur, me, opp, your = state(obs)
        if len(me.get('prize') or []) == 6 and len(opp.get('prize') or []) == 6:
            wb = boards[winner]
            if wb and wb['id'] == IMP:
                sn = [(i, b) for i, b in enumerate(boards) if b and b['id'] == SNORUNT and (b['hp'] <= wb['hp'])]
                mu = [(i, b) for i, b in enumerate(boards) if b and b['id'] == MUNK and (b['hp'] <= wb['hp'] + 40)]
                if sn:
                    winner = min(sn, key=lambda x: x[0])[0]
                elif mu:
                    winner = min(mu, key=lambda x: x[0])[0]
    if context == 13:
        wb = boards[winner]
        if wb and wb['id'] in (MUNK, 741):
            same = [(i, b) for i, b in enumerate(boards) if b and b['id'] == wb['id'] and (b['hp'] == wb['hp']) and (b['damage'] == wb['damage'])]
            if wb['id'] == MUNK and len(same) >= 3 or (wb['id'] == 741 and len(same) >= 2):
                winner = min(same, key=lambda x: (x[1]['serial'], x[0]))[0]
    return [winner]

def choose_count_max(obs, sems):
    opts = (obs.get('select') or {}).get('option') or []

    def val(i):
        o = opts[i]
        for k in ('number', 'count', 'index'):
            if isinstance(o.get(k), int):
                return int(o[k])
        return i
    return [max(range(len(opts)), key=lambda i: (val(i), -i))]

def choose_activate(obs, sems):
    cur, me, opp, your = state(obs)
    yes = next((i for i, s in enumerate(sems) if s['type'] == 1), None)
    no = next((i for i, s in enumerate(sems) if s['type'] == 2), None)
    useful = any((b['id'] in (GRIM, IMP, MORG) and b['energy'] < 2 for b in board(me)))
    if useful and yes is not None:
        return [yes]
    if no is not None:
        return [no]
    return [yes if yes is not None else 0]

def choose_switch_own(obs, sems, context, effect):
    cur, me, opp, your = state(obs)
    scores = []
    for i, s in enumerate(sems):
        b = option_board(obs, s)
        score = (-1, -1, -i)
        if b:
            if context == 3 and effect == BOSS:
                lethal = b['hp'] <= 180
                v = (100000 if lethal else 0) + role_value(b['id']) * 100
                if b['id'] == MUNK:
                    v += 15000
                if b['id'] in DAMAGE_ENGINE_IDS:
                    v += 3000
                if b['id'] == GRIM:
                    v += 20000
                if lethal:
                    v += b['hp'] * 50 + b['energy'] * 1000
                else:
                    v += (300 - b['hp']) * 40
                score = (v, b['hp'], -i)
            elif context == 3 and (s.get('source_rel') == 1 or s.get('target_rel') == 1):
                score = (target_score(b, 180, True), b['hp'], -i)
            else:
                if b['id'] == GRIM and b['energy'] >= 2:
                    pri = 100
                elif b['id'] == MORG:
                    pri = 90
                elif b['id'] == IMP:
                    pri = 80
                elif b['id'] == GRIM:
                    pri = 70
                elif b['id'] == MUNK:
                    pri = 30
                elif b['id'] == SNORUNT:
                    pri = 20
                elif b['id'] == FROSLASS:
                    pri = 10
                else:
                    pri = 0
                score = (pri, b['hp'], -i)
        scores.append(score)
    return [max(range(len(scores)), key=lambda i: scores[i])]

def choose_energy(obs, sems):
    scores = []
    for s in sems:
        b = option_board(obs, s)
        x = s['source_id'] or (b['id'] if b else 0)
        scores.append({GRIM: 10000, MUNK: 7000, MORG: 5500, FROSLASS: 4000, IMP: 3500, SNORUNT: 2500}.get(x, 1000))
    sel = obs.get('select') or {}
    k = int(sel.get('maxCount', 1) or 1)
    return choose_n_ranked(obs, scores, k)

def choose_discard(obs, sems):
    cur, me, opp, your = state(obs)
    sel = obs.get('select') or {}
    effect = cid(sel.get('effect'))
    if effect == 1197:
        keep_order = [LILLIE, MUNK, STAMP, PETREL, GRIM, NIGHT, BOSS, DARK, FROSLASS, SCRAPPER, SNORUNT, DAWN, CANDY, GYM, IMP, MORG, POKEPAD, POFFIN]
        keep = {x: (len(keep_order) - i) * 100 for i, x in enumerate(keep_order)}
        scores = [-keep.get(s['source_id'], 0) for s in sems]
    else:
        own = count_ids((me.get('active') or []) + (me.get('bench') or []))
        hand = count_ids(me.get('hand') or [])
        keep = {DARK: 7800, GRIM: 8500, MORG: 7200, MUNK: 7000, IMP: 6500, FROSLASS: 6200, SNORUNT: 5300, CANDY: 7600, STAMP: 9000, POFFIN: 3600, NIGHT: 8000, POKGEAR: 3300, SCRAPPER: 2500, POKEPAD: 6000, BOSS: 6200, PETREL: 6700, LILLIE: 5200, DAWN: 5800, GYM: 4200}
        scores = []
        for s in sems:
            x = s['source_id']
            kv = keep.get(x, 4000)
            if x == DARK and hand[DARK] > 2:
                kv -= 2500
            if x == POFFIN and len(me.get('bench') or []) >= 4:
                kv -= 2500
            if x == CANDY and own[IMP] == 0:
                kv -= 2500
            if x == SCRAPPER and (not any((p.get('toolCards') or [] for p in (opp.get('active') or []) + (opp.get('bench') or [])))):
                kv -= 1500
            scores.append(-kv)
    k = int(sel.get('maxCount', 0) or 0)
    picked = choose_n_ranked(obs, scores, k)
    if effect == 1197:
        own = count_ids((me.get('active') or []) + (me.get('bench') or []))
        turn = int(cur.get('turn', 0) or 0)

        def swap_keep(keep_card, drop_card):
            nonlocal picked
            picked_set = set(picked)
            keep_idx = next((i for i, s in enumerate(sems) if s['source_id'] == keep_card and i in picked_set), None)
            drop_idx = next((i for i, s in enumerate(sems) if s['source_id'] == drop_card and i not in picked_set), None)
            if keep_idx is not None and drop_idx is not None:
                picked = sorted(picked_set - {keep_idx} | {drop_idx})
        if own[MUNK] >= 1:
            swap_keep(GRIM, MUNK)
        if turn >= 3:
            swap_keep(FROSLASS, BOSS)
        if own[FROSLASS] == 0:
            swap_keep(FROSLASS, NIGHT)
        if own[SNORUNT] >= 1 and own[FROSLASS] == 0:
            swap_keep(FROSLASS, DARK)
        if turn <= 7:
            swap_keep(CANDY, DARK)
        if turn >= 10:
            swap_keep(DARK, PETREL)
        swap_keep(SCRAPPER, FROSLASS)
        swap_keep(NIGHT, DARK)
        swap_keep(BOSS, DARK)
        hand_counts = count_ids(me.get('hand') or [])
        if hand_counts[DAWN] == 0:
            swap_keep(SNORUNT, DARK)
        swap_keep(IMP, GYM)
        if own[SNORUNT] >= 2:
            swap_keep(CANDY, FROSLASS)
    return sorted(picked)

def choose_tool(obs, sems):
    cur, me, opp, your = state(obs)
    scores = []
    for s in sems:
        b = option_board(obs, s)
        score = 0
        if b:
            score = role_value(b['id']) * 100 + b['hp']
        scores.append(score)
    sel = obs.get('select') or {}
    k = min(int(sel.get('maxCount', 1) or 1), sum((1 for x in scores if x > 0)))
    k = max(int(sel.get('minCount', 0) or 0), k)
    return choose_n_ranked(obs, scores, k)

def main_score(obs, s):
    cur, me, opp, your = state(obs)
    turn = int(cur.get('turn', 0) or 0)
    tac = int(cur.get('turnActionCount', 0) or 0)
    hand = count_ids(me.get('hand') or [])
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    b = board(me)
    active = b[0] if b else None
    typ = s['type']
    src = s['source_id']
    aid = s['attack_id']
    score = 0
    if typ == 10 and src == MUNK:
        mb = option_board(obs, s)
        score = 15000 if own_damage(me) > 0 and has_powered_munk(me) else 900
        if mb:
            score += mb['damage'] * 80 + mb['index'] * 2
    elif typ == 9:
        tb = option_board(obs, s)
        if src == FROSLASS:
            score = 13600
        elif src == MORG:
            score = 13300
        elif src == GRIM:
            score = 13000 if own[GRIM] == 0 else 11500
        else:
            score = 9000
        if tb and src != GRIM:
            score += (500 if tb['area'] == 5 else 0) + tb['energy'] * 250 + tb['damage']
    elif typ == 7:
        if src == MUNK:
            score = 13100 + (700 if own[MUNK] < 2 else 0)
        elif src == IMP:
            score = 12800 + (700 if own[IMP] == 0 else 0)
        elif src == CANDY:
            score = 12600 if own[IMP] > 0 else 2500
        elif src == NIGHT:
            score = 12400 if len(me.get('discard') or []) else 2200
        elif src == POKEPAD:
            score = 12100
        elif src == GYM:
            score = 11800 if not cur.get('stadiumPlayed') else 2500
        elif src == POFFIN:
            score = (10400 if own[GRIM] > 0 else 11600) if len(me.get('bench') or []) < 5 else 2500
        elif src == LILLIE:
            score = (12000 if len(me.get('hand') or []) <= 4 else 10800) if not cur.get('supporterPlayed') else 0
        elif src == POKGEAR:
            score = 12350 if not cur.get('supporterPlayed') else 3000
        elif src == DAWN:
            score = 10700 if not cur.get('supporterPlayed') else 0
        elif src == PETREL:
            score = 10100 if not cur.get('supporterPlayed') else 0
        elif src == SNORUNT:
            score = 4800
        elif src == SCRAPPER:
            score = 9300
        elif src == STAMP:
            score = 8800
        elif src == BOSS:
            lethal = any((x['hp'] <= 180 for x in board(opp)[1:]))
            score = 5700 if lethal and active and (active['id'] == GRIM) and (active['energy'] >= 2) else 4500
        else:
            score = 6000
        if turn <= 2 and src in (MUNK, IMP, GYM, POFFIN, POKEPAD):
            score += 350
    elif typ == 10 and s['area'] == 7:
        if own[GRIM] == 0:
            score = 11900
        elif len(me.get('hand') or []) <= 7:
            score = 10600
        else:
            score = 11700
    elif typ == 8:
        target = option_board(obs, s)
        if target and target['id'] == MUNK and (target['energy'] == 0):
            score = 11400
        elif target and target['id'] == GRIM and (target['energy'] < 2):
            score = 4900
        elif target and target['id'] == IMP:
            score = 4200
        elif target and target['id'] == MORG:
            score = 4800
        elif target and target['id'] == SNORUNT:
            score = 3900
        else:
            score = 3500
    elif typ == 12:
        powered = any((x['id'] == GRIM and x['energy'] >= 2 for x in b[1:]))
        healthier_powered = bool(active and any((x['id'] == GRIM and x['energy'] >= 2 and (x['hp'] > active['hp']) for x in b[1:])))
        rotate_grim = bool(active and active['id'] == GRIM and (120 <= active['damage'] <= 250) and healthier_powered and (tac >= 15))
        score = 6400 if rotate_grim else 5000 if active and active['id'] != GRIM and powered else 700
    elif typ == 13:
        if aid == 937:
            score = 5200 + min(tac, 25) * 35
        elif aid == 934:
            score = 3900
        else:
            score = 3600
    elif typ == 14:
        score = 900
    return score

def _compatibility_queue_scores(obs, sems):
    scores = [main_score(obs, s) for s in sems]
    cur, me, opp, your = state(obs)
    own = count_ids((me.get('active') or []) + (me.get('bench') or []))
    hand_n = len(me.get('hand') or [])
    turn = int(cur.get('turn', 0) or 0)
    tac = int(cur.get('turnActionCount', 0) or 0)
    own_board = board(me)
    active = own_board[0] if own_board else None

    def indices(typ=None, src=None, aid=None, area=None):
        return [i for i, s in enumerate(sems) if (typ is None or s['type'] == typ) and (src is None or s['source_id'] == src) and (aid is None or s['attack_id'] == aid) and (area is None or s['area'] == area)]

    def force_before(left, right):
        if not left or not right:
            return
        li = max(left, key=lambda i: (scores[i], -i))
        ri = max(right, key=lambda i: (scores[i], -i))
        scores[li] = max(scores[li], scores[ri] + 1)
    force_before(indices(7, POFFIN), indices(7, LILLIE))
    force_before(indices(7, STAMP), indices(7, LILLIE))
    if len(me.get('bench') or []) <= 2:
        force_before(indices(7, POFFIN), indices(7, POKEPAD))
    if active and active.get('id') == IMP:
        force_before(indices(7, CANDY), indices(9, MORG))
    force_before(indices(7, POKGEAR), indices(7, NIGHT))
    force_before(indices(7, POKGEAR), indices(7, POKEPAD))
    if own[MUNK] >= 2 and own[IMP] == 0:
        force_before(indices(7, IMP), indices(7, MUNK))
    play_munk = indices(7, MUNK)
    if _HISTORY and _HISTORY[-1].get('source_id') == NIGHT or own[FROSLASS] >= 2 or count_ids(me.get('discard') or [])[GYM] >= 2:
        force_before(indices(7, NIGHT), play_munk)
    if count_ids(me.get('discard') or [])[POKEPAD] >= 2:
        force_before(indices(7, GYM), play_munk)
    if own[SNORUNT] >= 2 or own[FROSLASS] >= 2:
        force_before(indices(13, aid=937), indices(12))
    if count_ids(me.get('discard') or [])[FROSLASS] >= 2:
        force_before(indices(13, aid=937), indices(9, GRIM))
    unpowered_munk = [i for i, s in enumerate(sems) if s['type'] == 8 and (option_board(obs, s) or {}).get('id') == MUNK and ((option_board(obs, s) or {}).get('energy') == 0)]
    newly_appeared_munk = [i for i in unpowered_munk if (option_board(obs, sems[i]) or {}).get('appear')]
    if len(newly_appeared_munk) == 1:
        ni = newly_appeared_munk[0]
        if unpowered_munk:
            scores[ni] = max(scores[ni], max((scores[i] for i in unpowered_munk)) + 1)
    if turn <= 2 or own[MUNK] >= 2 or (own[GRIM] == 0 and hand_n >= 4):
        force_before(unpowered_munk, indices(7, LILLIE))
    grim_evolve = indices(9, GRIM)
    pad = indices(7, POKEPAD)
    if own[GRIM] == 0:
        force_before(grim_evolve, pad)
    else:
        force_before(pad, grim_evolve)
    if own[GRIM] >= 1 and turn >= 6 and (len(me.get('discard') or []) > 0):
        force_before(indices(7, NIGHT), grim_evolve)
    if hand_n <= 3 or tac >= 4:
        force_before(indices(13, aid=937), indices(7, BOSS))
    gym_ability = indices(10, area=7)
    if cur.get('stadiumPlayed') or (turn <= 2 and own[GRIM] == 0):
        force_before(gym_ability, pad)
    else:
        force_before(pad, gym_ability)
    if own[GRIM] >= 1:
        force_before(gym_ability, grim_evolve)
    else:
        force_before(grim_evolve, gym_ability)
    play_gym = indices(7, GYM)
    for src in (POKEPAD, POFFIN, LILLIE, PETREL, POKGEAR, NIGHT):
        force_before(play_gym, indices(7, src))
    force_before(play_gym, unpowered_munk)
    force_before(play_gym, grim_evolve)
    lillie = indices(7, LILLIE)
    petrel = indices(7, PETREL)
    if hand_n <= 5:
        force_before(lillie, gym_ability)
    elif hand_n >= 8:
        force_before(gym_ability, lillie)
        force_before(petrel, lillie)
    if turn >= 6 and own[GRIM] >= 1 and (own[MUNK] >= 1) and (not cur.get('stadiumPlayed')):
        force_before(unpowered_munk, gym_ability)
    if _HISTORY and _HISTORY[-1].get('source_id') == FROSLASS:
        force_before(indices(9, FROSLASS), indices(10, MUNK))
    if active and active.get('id') == GRIM and cur.get('energyAttached'):
        force_before(indices(7, PETREL), grim_evolve)
    if own[IMP] >= 2:
        force_before(indices(7, POKEPAD), indices(7, POFFIN))
    if own[MORG] >= 1:
        force_before(indices(7, MUNK), indices(7, IMP))
    if active and active.get('id') == IMP:
        attach_imp = [i for i, s in enumerate(sems) if s['type'] == 8 and (option_board(obs, s) or {}).get('id') == IMP]
        attach_morg = [i for i, s in enumerate(sems) if s['type'] == 8 and (option_board(obs, s) or {}).get('id') == MORG]
        force_before(attach_imp, attach_morg)
    if count_ids(me.get('discard') or [])[IMP] >= 1:
        force_before(indices(9, GRIM), indices(7, IMP))
    if cur.get('stadiumPlayed'):
        force_before(indices(7, SNORUNT), indices(13, aid=937))
    if own[GRIM] == 0:
        force_before(indices(7, MUNK), indices(9, MORG))
    if count_ids(me.get('discard') or [])[GYM] >= 1:
        force_before(indices(9, FROSLASS), indices(10, MUNK))
    if turn >= 3 and count_ids(me.get('discard') or [])[POFFIN] >= 1:
        force_before(indices(7, PETREL), indices(7, POFFIN))
    attack_best = max((scores[i] for i, s in enumerate(sems) if s['type'] == 13), default=None)
    if attack_best is not None:
        for i, s in enumerate(sems):
            if s['type'] == 14:
                scores[i] = min(scores[i], attack_best - 1)
    return scores

class TurnObjective:
    CLOSEOUT = 'closeout'
    ROTATE_ATTACKER = 'rotate_attacker'
    BUILD_PRIMARY = 'build_primary'
    MOVE_DAMAGE = 'move_damage'
    POWER_NETWORK = 'power_network'
    RECYCLE_RESOURCES = 'recycle_resources'
    BUILD_ENGINE = 'build_engine'
    DISRUPT = 'disrupt'
    PRESSURE = 'pressure'
    END = 'end'

def _turn_ledger(obs, sems):
    cur, me, opp, your = state(obs)
    own_cards = (me.get('active') or []) + (me.get('bench') or [])
    own = count_ids(own_cards)
    hand = count_ids(me.get('hand') or [])
    disc = count_ids(me.get('discard') or [])
    own_b = board(me)
    opp_b = board(opp)
    active = own_b[0] if own_b else None
    powered_munks = [b for b in own_b if b['id'] == MUNK and b['energy'] >= 1]
    unpowered_munks = [b for b in own_b if b['id'] == MUNK and b['energy'] == 0]
    powered_grims = [b for b in own_b if b['id'] == GRIM and b['energy'] >= 2]
    useful_discard = disc[DARK] + sum((disc[x] for x in (MUNK, IMP, MORG, GRIM, SNORUNT, FROSLASS)))
    return {'cur': cur, 'me': me, 'opp': opp, 'turn': int(cur.get('turn', 0) or 0), 'tac': int(cur.get('turnActionCount', 0) or 0), 'own': own, 'hand': hand, 'disc': disc, 'hand_n': len(me.get('hand') or []), 'bench_n': len(me.get('bench') or []), 'own_board': own_b, 'opp_board': opp_b, 'active': active, 'powered_munks': powered_munks, 'unpowered_munks': unpowered_munks, 'powered_grims': powered_grims, 'damage_total': sum((b['damage'] for b in own_b)), 'useful_discard': useful_discard, 'energy_attached': bool(cur.get('energyAttached')), 'supporter_played': bool(cur.get('supporterPlayed')), 'stadium_played': bool(cur.get('stadiumPlayed')), 'retreated': bool(cur.get('retreated'))}

def _action_kind(obs, s):
    typ = s['type']
    src = s['source_id']
    aid = s['attack_id']
    if typ == 10 and src == MUNK:
        return 'adrena'
    if typ == 10 and s['area'] == 7:
        return 'gym_search'
    if typ == 9:
        return {GRIM: 'evolve_grim', MORG: 'evolve_morg', FROSLASS: 'evolve_froslass'}.get(src, 'evolve_other')
    if typ == 7:
        return {MUNK: 'bench_munk', IMP: 'bench_imp', SNORUNT: 'bench_snorunt', CANDY: 'play_candy', STAMP: 'play_stamp', POFFIN: 'play_poffin', NIGHT: 'play_night', POKGEAR: 'play_pokegear', SCRAPPER: 'play_scrapper', POKEPAD: 'play_pokepad', BOSS: 'play_boss', PETREL: 'play_petrel', LILLIE: 'play_lillie', DAWN: 'play_dawn', GYM: 'play_gym'}.get(src, 'play_other')
    if typ == 8:
        b = option_board(obs, s)
        bid = b['id'] if b else 0
        return {MUNK: 'attach_munk', GRIM: 'attach_grim', IMP: 'attach_imp', MORG: 'attach_morg', SNORUNT: 'attach_snorunt', FROSLASS: 'attach_froslass'}.get(bid, 'attach_other')
    if typ == 12:
        return 'retreat'
    if typ == 13:
        return 'shadow_bullet' if aid == 937 else 'punk_up_attack' if aid == 934 else 'attack_other'
    if typ == 14:
        return 'end'
    return 'other'

def _indices_by_kind(obs, sems):
    out = {}
    for i, s in enumerate(sems):
        out.setdefault(_action_kind(obs, s), []).append(i)
    return out

def _resolve_action_instance(obs, sems, indices, kind, ledger):
    if not indices:
        return None
    if kind == 'adrena':
        rows = []
        for i in indices:
            b = option_board(obs, sems[i])
            if b:
                rows.append((i, b))
        if rows:
            fresh = [x for x in rows if x[1]['appear']]
            if len(fresh) == 1:
                return fresh[0][0]
            return max(rows, key=lambda x: (x[1]['damage'], x[1]['energy'], -x[1]['index']))[0]
    if kind.startswith('attach_') or kind.startswith('evolve_') or kind == 'retreat':
        return max(indices, key=lambda i: (main_score(obs, sems[i]), -i))
    return max(indices, key=lambda i: (main_score(obs, sems[i]), -i))

def _boss_has_closeout(ledger):
    active = ledger['active']
    if not active or active['id'] != GRIM or active['energy'] < 2:
        return False
    bench = [b for b in ledger['opp_board'] if b['area'] == 5]
    return any((b['hp'] <= 180 and (b['id'] == MUNK or b['id'] == GRIM or b['id'] in DAMAGE_ENGINE_IDS) for b in bench))

def _build_turn_objectives(ledger, kinds):
    q = []
    own = ledger['own']
    active = ledger['active']
    if 'play_boss' in kinds and _boss_has_closeout(ledger):
        q.append(TurnObjective.CLOSEOUT)
    if 'retreat' in kinds and active and (active['id'] == GRIM) and (active['damage'] >= 200) and any((b['id'] == GRIM and b['energy'] >= 2 and (b['hp'] > active['hp']) for b in ledger['own_board'][1:])):
        q.append(TurnObjective.ROTATE_ATTACKER)
    if own[GRIM] == 0:
        q.append(TurnObjective.BUILD_PRIMARY)
    if ledger['damage_total'] > 0 and ledger['powered_munks'] and ('adrena' in kinds):
        q.append(TurnObjective.MOVE_DAMAGE)
    if ledger['unpowered_munks'] and (not ledger['energy_attached']) and ('attach_munk' in kinds):
        q.append(TurnObjective.POWER_NETWORK)
    if own[FROSLASS] == 0 or own[SNORUNT] == 0:
        q.append(TurnObjective.BUILD_ENGINE)
    if (ledger['useful_discard'] >= 2 or ledger['hand_n'] <= 5) and (not ledger['supporter_played']):
        q.append(TurnObjective.RECYCLE_RESOURCES)
    if 'play_stamp' in kinds:
        q.append(TurnObjective.DISRUPT)
    if 'shadow_bullet' in kinds or 'punk_up_attack' in kinds:
        q.append(TurnObjective.PRESSURE)
    q.append(TurnObjective.END)
    return list(dict.fromkeys(q))

def _objective_tasks(objective, ledger, kinds):
    own = ledger['own']
    hand = ledger['hand']
    turn = ledger['turn']
    active = ledger['active']
    if objective == TurnObjective.CLOSEOUT:
        return ['play_boss']
    if objective == TurnObjective.ROTATE_ATTACKER:
        return ['retreat']
    if objective == TurnObjective.BUILD_PRIMARY:
        tasks = []
        if active and active['id'] == IMP:
            tasks += ['play_candy', 'evolve_grim']
        tasks += ['evolve_grim', 'play_gym', 'gym_search', 'play_pokegear', 'play_pokepad', 'play_poffin', 'evolve_morg', 'bench_imp']
        return tasks
    if objective == TurnObjective.MOVE_DAMAGE:
        urgent = bool(active and active['damage'] >= active['hp'] - 30)
        return ['adrena'] if urgent else ['evolve_froslass', 'evolve_grim', 'adrena']
    if objective == TurnObjective.POWER_NETWORK:
        if own[GRIM] >= 1:
            return ['attach_munk']
        if turn <= 2:
            return ['play_poffin', 'play_pokepad', 'attach_munk']
        return ['attach_munk']
    if objective == TurnObjective.RECYCLE_RESOURCES:
        tasks = []
        if 'play_pokegear' in kinds:
            tasks.append('play_pokegear')
        if 'play_petrel' in kinds and (not ledger['supporter_played']):
            tasks.append('play_petrel')
        if 'play_night' in kinds:
            tasks.append('play_night')
        if 'play_lillie' in kinds and (not ledger['supporter_played']):
            tasks.append('play_lillie')
        return tasks
    if objective == TurnObjective.BUILD_ENGINE:
        return ['evolve_froslass', 'bench_snorunt', 'play_poffin', 'play_pokepad']
    if objective == TurnObjective.DISRUPT:
        return ['play_stamp', 'play_scrapper']
    if objective == TurnObjective.PRESSURE:
        if active and active['id'] == GRIM and (active['energy'] >= 2):
            return ['shadow_bullet', 'punk_up_attack']
        return ['punk_up_attack', 'shadow_bullet']
    return ['end']

def _objective_for_task(task, ledger):
    if task == 'play_boss' and _boss_has_closeout(ledger):
        return TurnObjective.CLOSEOUT
    if task == 'retreat':
        return TurnObjective.ROTATE_ATTACKER
    if task in ('evolve_grim', 'evolve_morg', 'play_candy', 'bench_imp', 'play_gym', 'gym_search'):
        return TurnObjective.BUILD_PRIMARY
    if task == 'adrena':
        return TurnObjective.MOVE_DAMAGE
    if task.startswith('attach_'):
        return TurnObjective.POWER_NETWORK
    if task in ('evolve_froslass', 'bench_snorunt', 'play_poffin', 'play_pokepad', 'bench_munk'):
        return TurnObjective.BUILD_ENGINE
    if task in ('play_petrel', 'play_night', 'play_lillie', 'play_pokegear', 'play_dawn'):
        return TurnObjective.RECYCLE_RESOURCES
    if task in ('play_stamp', 'play_scrapper', 'play_boss'):
        return TurnObjective.DISRUPT
    if task in ('shadow_bullet', 'punk_up_attack', 'attack_other'):
        return TurnObjective.PRESSURE
    return TurnObjective.END if task == 'end' else TurnObjective.BUILD_ENGINE

def _build_processing_queue(obs, sems, ledger, kinds, compatibility_scores):
    declared = _build_turn_objectives(ledger, kinds)
    rank = {obj: i for i, obj in enumerate(declared)}
    tickets = []
    for task, indices in kinds.items():
        objective = _objective_for_task(task, ledger)
        objective_rank = rank.get(objective, len(rank))
        for idx in indices:
            tickets.append({'objective': objective, 'objective_rank': objective_rank, 'task': task, 'index': idx, 'compatibility_priority': compatibility_scores[idx]})
    return tickets

def _select_queue_ticket(queue, ledger):
    if not queue:
        return None
    baseline = max(queue, key=lambda t: (t['compatibility_priority'], -t['index']))
    by_task = {}
    for ticket in queue:
        old = by_task.get(ticket['task'])
        if old is None or (ticket['compatibility_priority'], -ticket['index']) > (old['compatibility_priority'], -old['index']):
            by_task[ticket['task']] = ticket

    def replace(undesired, desired, condition):
        nonlocal baseline
        if condition and baseline['task'] == undesired and (desired in by_task):
            baseline = by_task[desired]
    replace('evolve_grim', 'play_candy', ledger['turn'] <= 5)
    replace('play_lillie', 'attach_munk', ledger['turn'] <= 2)
    replace('play_stamp', 'bench_snorunt', ledger['turn'] <= 8)
    replace('bench_munk', 'evolve_grim', ledger['disc'][IMP] >= 2)
    replace('evolve_morg', 'bench_munk', ledger['hand_n'] >= 7)
    replace('bench_imp', 'play_gym', bool(ledger['active'] and ledger['active']['id'] == GRIM and (ledger['active']['energy'] >= 2)))
    replace('play_poffin', 'play_pokepad', ledger['disc'][POFFIN] >= 1)
    return baseline

def _resolve_ticket_index(obs, sems, ticket, kinds, ledger, compatibility_scores):
    if ticket is None:
        return None
    candidates = kinds.get(ticket['task']) or [ticket['index']]
    return max(candidates, key=lambda i: (compatibility_scores[i], -i))

def build_turn_plan(obs, sems):
    ledger = _turn_ledger(obs, sems)
    kinds = _indices_by_kind(obs, sems)
    objectives = _build_turn_objectives(ledger, kinds)
    scores = _compatibility_queue_scores(obs, sems)
    queue = _build_processing_queue(obs, sems, ledger, kinds, scores)
    ticket = _select_queue_ticket(queue, ledger)
    index = _resolve_ticket_index(obs, sems, ticket, kinds, ledger, scores)
    return {'objectives': objectives, 'queue': queue, 'ledger': ledger, 'selected_objective': None if ticket is None else ticket['objective'], 'selected_task': None if ticket is None else ticket['task'], 'selected_index': index}

def explain_turn_plan(obs):
    sel = (obs or {}).get('select') or {}
    sems = [sem(obs, o) for o in sel.get('option') or []]
    if not sems:
        return {'objectives': [], 'selected_task': None, 'selected_index': None}
    plan = build_turn_plan(obs, sems)
    ledger = plan['ledger']
    return {'turn': ledger['turn'], 'turn_action_count': ledger['tac'], 'objectives': plan['objectives'], 'selected_objective': plan['selected_objective'], 'selected_task': plan['selected_task'], 'selected_index': plan['selected_index'], 'resources': {'hand_n': ledger['hand_n'], 'deck_n': ledger['deck_n'], 'own_prize': ledger['own_prize'], 'opp_prize': ledger['opp_prize'], 'powered_munks': len(ledger['powered_munks']), 'unpowered_munks': len(ledger['unpowered_munks']), 'powered_grims': len(ledger['powered_grims']), 'damage_total': ledger['damage_total'], 'useful_discard': ledger['useful_discard']}}

def choose_main(obs, sems):
    plan = build_turn_plan(obs, sems)
    idx = plan['selected_index']
    return [] if idx is None else [idx]

def _dispatch_hierarchical_decision(obs, sems, ctx, effect):
    sel = obs.get('select') or {}
    opts = sel.get('option') or []
    if ctx == 41:
        return [next((i for i, s in enumerate(sems) if s['type'] == 1), 0)]
    if ctx == 42:
        return [next((i for i, s in enumerate(sems) if s['type'] == 2), 0)]
    if ctx == 1:
        return choose_setup_active(obs, sems)
    if ctx == 2:
        return choose_setup_bench(obs, sems)
    if ctx == 5:
        return choose_poffin(obs, sems)
    if ctx == 7:
        return choose_search(obs, sems, effect)
    if ctx == 37:
        return choose_rare_candy(obs, sems)
    if ctx == 21:
        return choose_punk_targets(obs, sems)
    if ctx == 22:
        return choose_punk_energy_count(obs, sems)
    if ctx == 16:
        return choose_adrena_source(obs, sems)
    if ctx in (13, 15):
        return choose_damage_target(obs, sems, 30, ctx)
    if ctx == 40:
        return choose_count_max(obs, sems)
    if ctx == 43:
        return choose_activate(obs, sems)
    if ctx in (3, 4):
        return choose_switch_own(obs, sems, ctx, effect)
    if ctx == 30:
        return choose_energy(obs, sems)
    if ctx == 34:
        return list(range(max(int(sel.get('minCount', 0) or 0), min(int(sel.get('maxCount', 0) or 0), len(opts)))))
    if ctx == 8:
        return choose_discard(obs, sems)
    if ctx == 27:
        return choose_tool(obs, sems)
    if ctx in (38, 39):
        return choose_count_max(obs, sems)
    if ctx == 0:
        return choose_main(obs, sems)
    mn = int(sel.get('minCount', 0) or 0)
    mx = int(sel.get('maxCount', 0) or 0)
    return list(range(max(mn, min(mx, len(opts)))))

def choose(obs):
    global _TURN
    if not obs or obs.get('select') is None:
        reset()
        return list(DECK)
    cur = obs.get('current') or {}
    turn = int(cur.get('turn', 0) or 0)
    if turn != _TURN:
        _TURN = turn
        _TURN_SOURCE.clear()
        _TURN_TYPE.clear()
    sel = obs.get('select') or {}
    ctx = int(sel.get('context', -1) if sel.get('context') is not None else -1)
    effect = cid(sel.get('effect'))
    opts = sel.get('option') or []
    sems = [sem(obs, o) for o in opts]
    if not opts:
        return []
    a = _dispatch_hierarchical_decision(obs, sems, ctx, effect)
    if not legal(obs, a):
        mn = int(sel.get('minCount', 0) or 0)
        mx = int(sel.get('maxCount', 0) or 0)
        a = list(range(max(mn, min(mx, len(opts)))))
    for i in a:
        s = sems[i]
        _HISTORY.append(s)
        _TURN_SOURCE[s['source_id']] += 1
        _TURN_TYPE[s['type']] += 1
    del _HISTORY[:-20]
    return list(a)
