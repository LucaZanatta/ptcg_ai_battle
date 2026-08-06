from __future__ import annotations
from collections import Counter
DARK = 7
FROSLASS = 104
MUNK = 112
IMP = 646
MORG = 647
GRIM = 648
SNOR = 860
CANDY = 1079
STAMP = 1080
POFFIN = 1086
NIGHT = 1097
GEAR = 1122
SCRAPPER = 1137
PAD = 1152
BOSS = 1182
PETREL = 1219
LILLIE = 1227
DAWN = 1231
GYM = 1259
SHADOW = 937
EX_IDS = set()

def ids(cards):
    return [int((c or {}).get('id', 0) or 0) for c in cards or [] if isinstance(c, dict)]

def count_board(st, cid):
    return ids(st['me'].get('active')).count(cid) + ids(st['me'].get('bench')).count(cid)

def count_hand(st, cid):
    return (st['me'].get('hand_ids') or []).count(cid)

def board_ids(st, who='me'):
    return ids(st[who].get('active')) + ids(st[who].get('bench'))

def bench_slots(st):
    return max(0, 5 - len(st['me'].get('bench') or []))

def card_obj(st, s):
    side = 'me' if int(s.get('source_rel', 0)) == 0 else 'op'
    p = st[side]
    z = int(s.get('source_zone', 0))
    i = int(s.get('index', -1))
    arr = p.get('active') if z == 4 else p.get('bench') if z == 5 else None
    if arr is not None and 0 <= i < len(arr):
        return arr[i] or {}
    for c in arr or []:
        if isinstance(c, dict) and int(c.get('id', 0) or 0) == int(s.get('source_id', 0) or 0):
            return c
    return {}

def remaining_hp(st, s):
    c = card_obj(st, s)
    return int(c.get('hp', 0) or 0)

def damage(st, s):
    c = card_obj(st, s)
    return max(0, int(c.get('maxHp', 0) or 0) - int(c.get('hp', 0) or 0))

def target_obj(st, s):
    side = 'me' if int(s.get('target_rel', 0)) == 0 else 'op'
    p = st[side]
    z = int(s.get('target_area', s.get('inplay_area', 0)) or 0)
    i = int(s.get('inplay_index', -1))
    arr = p.get('active') if z == 4 else p.get('bench') if z == 5 else None
    if arr is not None and 0 <= i < len(arr):
        return arr[i] or {}
    for c in arr or []:
        if isinstance(c, dict) and int(c.get('id', 0) or 0) == int(s.get('target_id', 0) or 0):
            return c
    return {}

def energy_n(st, s):
    return int(card_obj(st, s).get('en', 0) or 0)

def target_energy_n(st, s):
    return int(target_obj(st, s).get('en', 0) or 0)

def prize_value(cid, hp=0):
    if hp >= 340:
        return 3
    if hp >= 180:
        return 2
    return 1

def choose_matching(options, pred, default=None):
    for i, s in enumerate(options):
        if pred(s):
            return i
    return default

def choose_setup_active(options):
    pri = {IMP: 0, SNOR: 1, MUNK: 2}
    return min(range(len(options)), key=lambda i: (pri.get(options[i].get('source_id'), 99), i))

def choose_setup_bench(st, options):
    picks = [i for i, s in enumerate(options) if s.get('source_id') == SNOR]
    return picks[:st['max']]

def own_switch_score(st, s):
    cid = s.get('source_id')
    en = energy_n(st, s)
    hp = remaining_hp(st, s)
    base = {MORG: 100, IMP: 95, GRIM: 75, MUNK: 60, SNOR: 50, FROSLASS: 40}.get(cid, 45)
    if cid == GRIM and en >= 2:
        base -= 45
    if en:
        base -= 8 * en
    if hp and hp <= 30:
        base += 15
    return base

def threat_score(st, s, damage_amount=0, bench_damage=False, munk_bonus=260, basic_bonus=70):
    cid = int(s.get('source_id', 0) or 0)
    hp = remaining_hp(st, s)
    maxhp = int(card_obj(st, s).get('maxHp', 0) or hp)
    pv = prize_value(cid, maxhp)
    score = pv * 120
    if hp > 0:
        if damage_amount and hp <= damage_amount:
            score += 1000 + pv * 300
        score += max(0, 240 - hp)
        if hp in (40, 50, 60, 70, 80, 90, 100, 110, 120):
            score += 30
    if cid == MUNK:
        score += munk_bonus
    elif cid in (IMP, SNOR, 741, 400, 343, 742):
        score += basic_bonus
    if int(s.get('source_zone', 0)) == 5:
        score += 25
    if bench_damage and int(s.get('source_zone', 0)) != 5:
        score -= 1000
    return score

def choose_to_hand(st, options, history):
    effect = int(st.get('effect', 0) or 0)
    avail = [int(s.get('source_id', 0) or 0) for s in options]
    if all((x == 0 for x in avail)):
        return list(range(st['min'])) if st['min'] else [0] if options else []
    cards = (st['me'].get('active') or []) + (st['me'].get('bench') or [])
    board = Counter((int(c.get('id', 0) or 0) for c in cards if isinstance(c, dict)))
    hand = Counter(st['me'].get('hand_ids') or [])
    discard = Counter(st['me'].get('discard_ids') or [])
    if effect == GYM:
        ready_imp = sum((1 for c in cards if c.get('id') == IMP and (not c.get('appear'))))
        ready_morg = sum((1 for c in cards if c.get('id') == MORG and (not c.get('appear'))))
        active_id = int(((st['me'].get('active') or [{}])[0] or {}).get('id', 0) or 0)
        if int(st.get('turn', 0) or 0) <= 3 and active_id == IMP and (ready_imp == 1) and (board[IMP] == 1) and (bench_slots(st) >= 2) and (hand[CANDY] == 0) and (IMP in avail):
            order = [IMP, MORG, GRIM]
        elif active_id == IMP and hand[CANDY] > 0 and (hand[GRIM] == 0):
            order = [GRIM, MORG, IMP]
        elif ready_imp > 0 and board[GRIM] > 0 and (hand[CANDY] == 0):
            order = [MORG, IMP, GRIM]
        elif ready_imp == 0 and hand[GRIM] == 0 and (IMP not in avail):
            order = [GRIM, MORG, IMP]
        elif ready_morg > hand[GRIM]:
            order = [GRIM, MORG, IMP]
        elif ready_imp > hand[MORG]:
            order = [MORG, IMP, GRIM]
        else:
            order = [IMP, MORG, GRIM]
    elif effect == PAD:
        represented_munk = board[MUNK] + hand[MUNK]
        need_froslass = board[SNOR] > 0 and board[FROSLASS] + hand[FROSLASS] == 0
        order = []
        line_n = board[IMP] + board[MORG] + board[GRIM]
        if int(st.get('turn', 0) or 0) <= 2 and represented_munk >= 1 and (line_n <= 1) and (hand[IMP] == 0) and (IMP in avail) and (bench_slots(st) >= 1):
            order.append(IMP)
        if int(st.get('turn', 0) or 0) >= 7 and board[SNOR] > 0:
            order.append(FROSLASS)
        if need_froslass and len(st['me'].get('bench') or []) >= 4:
            order.append(FROSLASS)
        if represented_munk < 3:
            order.append(MUNK)
        if need_froslass:
            order.append(FROSLASS)
        if represented_munk < 4:
            order.append(MUNK)
        ready_imp = sum((1 for c in cards if c.get('id') == IMP and (not c.get('appear')))) > hand[MORG]
        if ready_imp:
            order.append(MORG)
        order += [IMP, MORG, MUNK, FROSLASS, SNOR]
    elif effect == NIGHT:
        need_energy = hand[DARK] == 0 and any((c.get('id') == MUNK and int(c.get('en', 0) or 0) == 0 for c in cards))
        need_grim = sum((1 for c in cards if c.get('id') == MORG and (not c.get('appear')))) > hand[GRIM]
        need_morg = sum((1 for c in cards if c.get('id') == IMP and (not c.get('appear')))) > hand[MORG]
        need_froslass = board[SNOR] > 0 and board[FROSLASS] + hand[FROSLASS] == 0
        order = []
        if need_energy:
            order.append(DARK)
        if need_grim:
            order.append(GRIM)
        if need_morg:
            order.append(MORG)
        if need_froslass:
            order.append(FROSLASS)
        order += [MUNK, IMP, MORG, GRIM, FROSLASS, SNOR, DARK]
        base_first = next((cid for cid in order if cid in avail), 0)
        if base_first == IMP and bench_slots(st) == 0 and (DARK in avail):
            order = [DARK] + order
        elif base_first == IMP and int(st['me'].get('prize_n', 0) or 0) <= 2 and (DARK in avail):
            order = [DARK] + order
        elif base_first == MUNK and int(st['me'].get('prize_n', 0) or 0) <= 4 and (hand[DARK] == 0) and (DARK in avail):
            order = [DARK] + order
        elif base_first == FROSLASS and DARK in avail:
            order = [DARK] + order
    elif effect == PETREL:
        recoverable = sum((discard[c] for c in (DARK, IMP, MORG, GRIM, MUNK, SNOR, FROSLASS)))
        active_id = int((st['me'].get('active') or [{}])[0].get('id', 0) or 0)
        score = {STAMP: 400, NIGHT: 210, PAD: 180, GYM: 170, CANDY: 140, LILLIE: 100, POFFIN: 60, SCRAPPER: 50, BOSS: 40, GEAR: 20, DAWN: 20}
        score[NIGHT] += 10 * min(5, recoverable)
        if int(st.get('turn', 0) or 0) >= 9:
            score[NIGHT] += 100
        if st.get('stadium') != GYM:
            score[GYM] += 200
        if active_id == IMP and board[IMP] > 0 and (hand[GRIM] > 0) and (hand[CANDY] == 0):
            score[CANDY] += 150
        if board[MUNK] + hand[MUNK] >= 4:
            score[PAD] -= 100
        for cid in (STAMP, NIGHT, PAD, GYM, CANDY, LILLIE):
            if hand[cid] > 0:
                score[cid] -= 260
        if bench_slots(st) > 0 and board[MUNK] + hand[MUNK] < 4:
            score[PAD] += 180
        ranked = sorted(score, key=lambda c: (score[c], -c), reverse=True)
        order = ranked
    elif effect == DAWN:
        aset = set(avail)
        if aset <= {GRIM}:
            order = [GRIM]
        elif aset <= {MORG, FROSLASS}:
            need_froslass = board[SNOR] > 0 and board[FROSLASS] + hand[FROSLASS] == 0
            order = [FROSLASS, MORG] if need_froslass else [MORG, FROSLASS]
        elif aset <= {MUNK, IMP, SNOR}:
            line_n = board[IMP] + board[MORG] + board[GRIM]
            order = [IMP, MUNK, SNOR] if line_n < 2 else [MUNK, IMP, SNOR]
        else:
            order = [GRIM, MORG, FROSLASS, MUNK, IMP, SNOR]
    elif effect == GEAR:
        return [0] if options else []
    else:
        order = [GRIM, MORG, MUNK, IMP, FROSLASS, DARK, STAMP, NIGHT, PAD, GYM, CANDY, LILLIE, POFFIN, SCRAPPER, BOSS, DAWN, SNOR]
    for cid in order:
        for i, s in enumerate(options):
            if int(s.get('source_id', 0) or 0) == cid:
                return [i]
    if st['min'] == 0:
        return []
    return list(range(min(st['min'], len(options))))

def desired_energy(st, c):
    cid = int((c or {}).get('id', 0) or 0)
    zone_active = c in (st['me'].get('active') or [])
    if cid == GRIM:
        return 2
    if cid in (MORG, IMP):
        return 2
    return 0

def energy_deficit_total(st):
    total = 0
    for c in (st['me'].get('active') or []) + (st['me'].get('bench') or []):
        if not isinstance(c, dict):
            continue
        total += max(0, desired_energy(st, c) - int(c.get('en', 0) or 0))
    return total

def choose_attach_target(st, options):
    scored = []
    for i, s in enumerate(options):
        c = card_obj(st, s)
        cid = int(s.get('source_id', 0) or 0)
        en = int(c.get('en', 0) or 0)
        need = max(0, desired_energy(st, c) - en)
        active = int(s.get('source_zone', 0)) == 4
        base = {GRIM: 90, MORG: 55, IMP: 50, MUNK: 45}.get(cid, 0)
        if active:
            base += 35
        if cid == MUNK and en == 0:
            base += 30
        if need <= 0:
            base -= 100
        scored.append((need > 0, base - 10 * en, -i, i))
    return max(scored)[-1]

def discard_keep_value(st, s):
    cid = int(s.get('source_id', 0) or 0)
    board = Counter(board_ids(st))
    hand = Counter(st['me'].get('hand_ids') or [])
    val = {DARK: 45, MUNK: 90, IMP: 75, MORG: 80, GRIM: 95, SNOR: 30, FROSLASS: 35, CANDY: 65, STAMP: 95, POFFIN: 35, NIGHT: 65, GEAR: 30, SCRAPPER: 20, PAD: 50, BOSS: 60, PETREL: 55, LILLIE: 70, DAWN: 50, GYM: 45}.get(cid, 40)
    if cid == POFFIN and (bench_slots(st) == 0 or board[IMP] >= 2):
        val -= 30
    if cid == GYM and st.get('stadium') == GYM:
        val -= 25
    if cid == DARK and hand[DARK] > 2:
        val -= 18
    if cid in (MORG, GRIM) and board[IMP] + board[MORG] == 0:
        val -= 25
    if hand[cid] > 1:
        val -= 8 * (hand[cid] - 1)
    return val

def main_score(st, s, history):
    t = int(s.get('type', -1))
    src = int(s.get('source_id', 0) or 0)
    tgt = int(s.get('target_id', 0) or 0)
    area = int(s.get('target_area', 0) or 0)
    turn = int(st.get('turn', 0))
    tac = int(st.get('tac', 0))
    me = st['me']
    board = Counter(board_ids(st))
    hand = Counter(me.get('hand_ids') or [])
    active = (me.get('active') or [{}])[0] or {}
    active_id = int(active.get('id', 0) or 0)
    active_en = int(active.get('en', 0) or 0)
    if t == 10 and src == MUNK:
        return 10000
    if t == 10 and src == 0 and (int(s.get('area', 0)) == 7):
        return 8500 if st.get('flags', {}).get('stadium') and st.get('stadium') == GYM else 8425
    if t == 7:
        if src == MUNK:
            return 9300 - 250 * max(0, board[MUNK] - 2)
        if src == IMP:
            line_n = board[IMP] + board[MORG] + board[GRIM]
            if me.get('prize_n') == 6 and line_n <= 1:
                return 8950
            return 8850 - 180 * max(0, line_n - 2)
        if src == NIGHT:
            return 8900 if me.get('prize_n') == 6 and board[FROSLASS] > 0 else 8550
        if src == PAD:
            return 8450
        if src == POFFIN:
            return 8250 if bench_slots(st) >= 1 else 3000
        if src == CANDY:
            if board[IMP] > 0 and hand[GRIM] > 0:
                return 8920 if me.get('prize_n') == 6 else 8750
            return 7800
        if src == STAMP:
            return 8150
        if src == GEAR:
            return 8350
        if src == GYM:
            return 8850 if st.get('stadium') != GYM else 2000
        if src == LILLIE:
            return 7700 + (350 if me.get('hand_n', 0) <= 6 else 0) + (150 if me.get('prize_n') == 6 else 0) + (500 if me.get('hand_n', 0) <= 2 else 0)
        if src == PETREL:
            return 7750
        if src == DAWN:
            return 7700
        if src == BOSS:
            op_active = (st['op'].get('active') or [{}])[0] or {}
            active_hp = int(op_active.get('hp', 0) or 0)
            return 6900 if 0 < active_hp <= 180 and active_id == GRIM and (active_en >= 2) else 7400
        if src == FROSLASS:
            return 6500
        if src == SNOR:
            return 5900 if board[SNOR] == 0 else 4300
        if src == SCRAPPER:
            return 7600
        return 6000
    if t == 9:
        active_target = area == 4
        if src == GRIM:
            return 9500 if active_target else 8380
        if src == MORG:
            return 9150 if not active_target else 8700
        if src == FROSLASS:
            return 8900
        return 8200
    if t == 8 and src == DARK:
        cid = tgt
        obj = None
        if cid == MUNK:
            en = target_energy_n(st, s)
            zero_munk = sum((1 for c in (me.get('active') or []) + (me.get('bench') or []) if c.get('id') == MUNK and int(c.get('en', 0) or 0) == 0))
            if en == 0 and active_id == GRIM and (zero_munk > 0):
                return 8440 + (50 if zero_munk >= 2 else 0)
            return 8330 + (50 if zero_munk >= 2 else 0) if en == 0 else 6200
        if cid == GRIM:
            en = target_energy_n(st, s)
            if area == 5 and active_id == GRIM and (active_en >= 2):
                return 6900
            return 8050 if en < 2 else 5200
        if cid in (MORG, IMP):
            return 6900
        return 5000
    if t == 12:
        ready = any((c.get('id') == GRIM and int(c.get('en', 0) or 0) >= 2 for c in me.get('bench') or []))
        if ready:
            if active_id == GRIM and int(active.get('hp', 0) or 0) <= 200:
                return 6900 if me.get('prize_n', 0) <= 3 else 7100
            return 6800
        return -100
    if t == 13:
        if int(s.get('attack_id', 0) or 0) == SHADOW:
            return 7000
        return 5200
    if t == 14:
        return 0
    return 4000

def _choose_v8_base(st, options, history):
    ctx = int(st['context'])
    mn = int(st['min'])
    mx = int(st['max'])
    n = len(options)
    if n == 0:
        return []
    if ctx == 0:
        scores = [main_score(st, s, history) for s in options]
        winner = max(range(n), key=lambda i: (scores[i], -i))
        wo = options[winner]
        if int(wo.get('type', -1)) == 9:
            semantic = (int(wo.get('source_id', 0) or 0), int(wo.get('target_id', 0) or 0), int(wo.get('target_area', 0) or 0), scores[winner])
            tied = [i for i, o in enumerate(options) if int(o.get('type', -1)) == 9 and (int(o.get('source_id', 0) or 0), int(o.get('target_id', 0) or 0), int(o.get('target_area', 0) or 0), scores[i]) == semantic]
            if len(tied) > 1:
                winner = max(tied, key=lambda i: (target_energy_n(st, options[i]), -i))
        bench_munk_attach = choose_matching(options, lambda s: int(s.get('type', -1)) == 8 and int(s.get('source_id', 0) or 0) == DARK and (int(s.get('target_id', 0) or 0) == MUNK) and (int(s.get('target_area', 0) or 0) == 5) and (target_energy_n(st, s) == 0))
        win_type = int(options[winner].get('type', -1))
        win_src = int(options[winner].get('source_id', 0) or 0)
        win_area = int(options[winner].get('target_area', 0) or 0)
        active = (st['me'].get('active') or [{}])[0] or {}
        if bench_munk_attach is not None:
            if win_type == 8 and win_src == DARK and (int(options[winner].get('target_id', 0) or 0) == MUNK) and (int(options[winner].get('target_area', 0) or 0) == 4) and (st['me'].get('prize_n', 0) == 6):
                return [bench_munk_attach]
            if win_type == 7 and win_src == LILLIE:
                return [bench_munk_attach]
            if win_type == 9 and win_src == MORG and (win_area == 4):
                return [bench_munk_attach]
            if win_type == 7 and win_src == PAD and (int(active.get('id', 0) or 0) == GRIM) and (st.get('stadium') == GYM):
                return [bench_munk_attach]
        is_gym_ability = win_type == 10 and int(options[winner].get('source_id', 0) or 0) == 0 and (int(options[winner].get('area', 0) or 0) == 7)
        line_n = count_board(st, IMP) + count_board(st, MORG) + count_board(st, GRIM)
        immediate_gym = st['me'].get('hand_n', 0) >= 6 and line_n <= 2
        hand_ids = Counter(st['me'].get('hand_ids') or [])
        if win_type == 7 and win_src == PAD and (count_board(st, FROSLASS) == 0) and (hand_ids[CANDY] >= 1):
            gear = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == GEAR)
            if gear is not None:
                return [gear]
        if is_gym_ability and history and (int(history[-1].get('type', -1) or -1) == 9) and (line_n >= 2) and (sum((1 for c in (st['me'].get('active') or []) + (st['me'].get('bench') or []) if c.get('id') == MUNK and int(c.get('en', 0) or 0) == 0)) <= 1):
            dawn = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == DAWN)
            if dawn is not None:
                return [dawn]
        if win_type == 7 and win_src == MUNK and (int(st.get('turn', 0) or 0) <= 1) and (line_n == 0):
            imp = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == IMP)
            if imp is not None:
                return [imp]
        if win_type == 7 and win_src == PAD and (int(st.get('turn', 0) or 0) <= 1) and (bench_slots(st) == 5):
            poffin = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == POFFIN)
            if poffin is not None:
                return [poffin]
        if win_type == 7 and win_src == PAD and (int(st.get('turn', 0) or 0) <= 2) and (int(st['me'].get('prize_n', 0) or 0) == 6) and (line_n == 0):
            poffin = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == POFFIN)
            if poffin is not None:
                return [poffin]
        if is_gym_ability and int(st.get('turn', 0) or 0) <= 9 and (line_n >= 3) and (count_board(st, GRIM) <= 1) and (int(active.get('id', 0) or 0) == GRIM) and (int(st['me'].get('hand_n', 0) or 0) <= 7):
            dawn = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == DAWN)
            if dawn is not None:
                return [dawn]
        if is_gym_ability and st['me'].get('hand_n', 0) <= 7 and (not immediate_gym):
            lillie = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == LILLIE)
            if lillie is not None:
                if bench_munk_attach is not None:
                    return [bench_munk_attach]
                return [lillie]
        if is_gym_ability:
            gear = choose_matching(options, lambda s: int(s.get('type', -1)) == 7 and int(s.get('source_id', 0) or 0) == GEAR)
            if gear is not None:
                return [gear]
        return [winner]
    if ctx == 1:
        return [choose_setup_active(options)]
    if ctx == 2:
        return choose_setup_bench(st, options)
    if ctx == 3:
        rel = int(options[0].get('source_rel', 0)) if options else 0
        if rel == 1:
            return [max(range(n), key=lambda i: (threat_score(st, options[i], 180), -i))]
        last = int((history[-1] if history else {}).get('source_id', 0) or 0)
        if last == MORG:
            pri = {IMP: 100, GRIM: 90, MUNK: 70, MORG: 60, SNOR: 50, FROSLASS: 40}
            return [max(range(n), key=lambda i: (pri.get(int(options[i].get('source_id', 0) or 0), 0), -i))]
        return [max(range(n), key=lambda i: ((1000 if int(options[i].get('source_id', 0) or 0) == GRIM else 0) + 10 * energy_n(st, options[i]) + remaining_hp(st, options[i]), -i))]
    if ctx == 4:
        ready = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == GRIM and energy_n(st, s) >= 2]
        if ready:
            return [max(ready, key=lambda i: (remaining_hp(st, options[i]), -i))]
        near_ready = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == GRIM and energy_n(st, s) >= 1]
        if near_ready:
            return [max(near_ready, key=lambda i: (remaining_hp(st, options[i]), -i))]
        pri = {MORG: 100, IMP: 90, GRIM: 80, MUNK: 70, SNOR: 60, FROSLASS: 50}
        return [max(range(n), key=lambda i: (pri.get(int(options[i].get('source_id', 0) or 0), 0), -i))]
    if ctx == 5:
        marnie = count_board(st, IMP) + count_board(st, MORG) + count_board(st, GRIM)
        slots = bench_slots(st)
        imp = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == IMP]
        picks = imp[:min(mx, slots, max(0, 4 - marnie))]
        if not picks and slots > 0 and (count_board(st, FROSLASS) > 0) and (int(st.get('turn', 0) or 0) <= 8):
            snor = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == SNOR]
            if snor:
                picks = snor[:1]
        if len(picks) < mn:
            rest = [i for i in range(n) if i not in picks]
            picks += rest[:mn - len(picks)]
        return picks
    if ctx == 7:
        return choose_to_hand(st, options, history)
    if ctx == 8:
        discard_order = [POFFIN, MORG, PAD, GYM, SCRAPPER, DARK, NIGHT, SNOR, IMP, FROSLASS, MUNK, BOSS, CANDY, GRIM, PETREL, DAWN, STAMP, LILLIE]
        rank = {cid: i for i, cid in enumerate(discard_order)}
        picked = sorted(range(n), key=lambda i: (rank.get(int(options[i].get('source_id', 0) or 0), 99), i))[:mn]
        return sorted(picked)
    if ctx == 13:
        amount = max(1, int(st.get('remain_damage', 0) or 3)) * 10
        winner = max(range(n), key=lambda i: (threat_score(st, options[i], amount, False, 150, 100), -i))
        wc = card_obj(st, options[winner])
        whp = int(wc.get('hp', 0) or 0)
        wmax = int(wc.get('maxHp', 0) or whp)
        if prize_value(int(options[winner].get('source_id', 0) or 0), wmax) >= 2 and whp > amount:
            winner = min(range(n), key=lambda i: (remaining_hp(st, options[i]), i))
        wc = card_obj(st, options[winner])
        whp = int(wc.get('hp', 0) or 0)
        if int(options[winner].get('source_id', 0) or 0) == MUNK and whp >= 90:
            fragile = []
            for i, o in enumerate(options):
                c = card_obj(st, o)
                hp = int(c.get('hp', 0) or 0)
                mx = int(c.get('maxHp', 0) or hp)
                if int(o.get('source_id', 0) or 0) != MUNK and prize_value(int(o.get('source_id', 0) or 0), mx) == 1 and (0 < hp <= 50):
                    fragile.append(i)
            if fragile:
                winner = min(fragile, key=lambda i: (remaining_hp(st, options[i]), i))
        return [winner]
    if ctx == 14:
        return [max(range(n), key=lambda i: (threat_score(st, options[i], 30), -i))]
    if ctx == 15:
        winner = max(range(n), key=lambda i: (threat_score(st, options[i], 30, True, 100, 70), -i))
        wc = card_obj(st, options[winner])
        whp = int(wc.get('hp', 0) or 0)
        wmax = int(wc.get('maxHp', 0) or whp)
        if prize_value(int(options[winner].get('source_id', 0) or 0), wmax) >= 2 and whp > 30:
            winner = min(range(n), key=lambda i: (remaining_hp(st, options[i]), i))
        return [winner]
    if ctx == 16:
        active_grim = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == GRIM and int(s.get('source_zone', 0) or 0) == 4]
        bench_munk = [i for i, s in enumerate(options) if int(s.get('source_id', 0) or 0) == MUNK and int(s.get('source_zone', 0) or 0) == 5]
        if active_grim and bench_munk:
            ai = active_grim[0]
            active_obj = card_obj(st, options[ai])
            active_damage = max(0, int(active_obj.get('maxHp', 0) or 0) - int(active_obj.get('hp', 0) or 0))
            most_damaged_munk = max(bench_munk, key=lambda i: (damage(st, options[i]), -i))
            max_munk_damage = damage(st, options[most_damaged_munk])
            if max_munk_damage >= 50:
                return [most_damaged_munk]
            if int(active_obj.get('hp', 0) or 0) >= 200 and active_damage - max_munk_damage >= 60:
                return [ai]
            if active_damage >= 30 and int(active_obj.get('hp', 0) or 0) >= 170 and (max_munk_damage <= 30):
                return [ai]
            min_munk_hp = min((remaining_hp(st, options[i]) for i in bench_munk))
            if active_damage >= 10 and min_munk_hp >= 90:
                return [ai]

        def sc(i):
            s = options[i]
            cid = int(s.get('source_id', 0) or 0)
            active = int(s.get('source_zone', 0)) == 4
            return (100 * active + 50 * (cid == MUNK) - remaining_hp(st, s), -i)
        return [max(range(n), key=sc)]
    if ctx in (17, 18, 19, 20):
        return [max(range(n), key=lambda i: (own_switch_score(st, options[i]), -i))]
    if ctx == 21:
        return [choose_attach_target(st, options)]
    if ctx == 22:
        count_table = {1: 1, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 4, 9: 5, 10: 5}
        k = count_table.get(n, min(5, n))
        if n in (5, 6):
            last_grim_evo = next((h for h in reversed(history) if int(h.get('type', -1)) == 9 and int(h.get('source_id', 0) or 0) == GRIM), None)
            if last_grim_evo is not None:
                evo_area = int(last_grim_evo.get('target_area', 0) or 0)
                if evo_area == 5:
                    k = 2
                elif evo_area == 4:
                    active = (st['me'].get('active') or [{}])[0] or {}
                    active_en = int(active.get('en', 0) or 0)
                    total_grim_en = sum((int(c.get('en', 0) or 0) for c in (st['me'].get('active') or []) + (st['me'].get('bench') or []) if int((c or {}).get('id', 0) or 0) == GRIM))
                    if active_en >= 2 or (n == 6 and active_en == 1 and (total_grim_en == 1)):
                        k = 2
                target_index = int(last_grim_evo.get('inplay_index', -1))
                target_cards = st['me'].get('bench') or [] if evo_area == 5 else st['me'].get('active') or [] if evo_area == 4 else []
                target_card = target_cards[target_index] if 0 <= target_index < len(target_cards) else {}
                target_energy = int((target_card or {}).get('en', 0) or 0)
                if n == 6 and evo_area == 5 and (target_energy == 0):
                    k = 3
                if n == 5 and evo_area == 5 and (target_energy == 0) and (int(st.get('turn', 0) or 0) <= 4):
                    k = 3
        k = max(mn, min(mx, n, k))
        return list(range(k))
    if ctx in (26, 27, 28, 29, 30, 31, 32, 33):
        k = mn
        return sorted(range(n), key=lambda i: (own_switch_score(st, options[i]), i))[:k]
    if ctx == 34:
        return list(range(min(mx, n)))
    if ctx in (35, 36):
        return [0]
    if ctx == 37:
        return [max(range(n), key=lambda i: (100 if int(options[i].get('target_area', 0)) == 4 else 0, -i))]
    if ctx in (38, 39, 40):
        return [n - 1]
    if ctx == 41:
        return [choose_matching(options, lambda s: int(s.get('type', -1)) == 1, 0)]
    if ctx == 42:
        return [choose_matching(options, lambda s: int(s.get('type', -1)) == 2, 0)]
    if ctx in (43, 44, 45, 46):
        return [choose_matching(options, lambda s: int(s.get('type', -1)) == 1, 0)]
    k = max(mn, min(mx, n))
    return list(range(k))

def _choose_v9_base(st, options, history):
    base = _choose_v8_base(st, options, history)
    ctx = int(st.get('context', -1))
    if not base or not options:
        return base
    if ctx == 7 and int(st.get('effect', 0) or 0) == GYM:
        me = st.get('me') or {}
        cards = (me.get('active') or []) + (me.get('bench') or [])
        board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
        hand = Counter(me.get('hand_ids') or [])
        current = int(options[base[0]].get('source_id', 0) or 0)
        turn = int(st.get('turn', 0) or 0)
        slots = max(0, 5 - len(me.get('bench') or []))
        line_n = board[IMP] + board[MORG] + board[GRIM]
        if current == GRIM and turn <= 1 and (slots == 5):
            imp = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == IMP)
            if imp is not None:
                return [imp]
        if current == GRIM and hand[GRIM] >= 1:
            morg = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == MORG)
            if morg is not None:
                return [morg]
        if current == MORG and turn == 2 and (line_n == 1):
            imp = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == IMP)
            if imp is not None:
                return [imp]
        return base
    if ctx != 0:
        return base
    me = st.get('me') or {}
    active = (me.get('active') or [{}])[0] or {}
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    hand = Counter(me.get('hand_ids') or [])
    chosen = options[base[0]]
    ctype = int(chosen.get('type', -1))
    csrc = int(chosen.get('source_id', 0) or 0)
    carea = int(chosen.get('area', 0) or 0)
    if ctype == 12 and int(active.get('id', 0) or 0) == GRIM and (0 < int(active.get('hp', 0) or 0) <= 100) and (board[SNOR] >= 1):
        attack = choose_matching(options, lambda o: int(o.get('type', -1)) == 13 and int(o.get('attack_id', 0) or 0) == SHADOW)
        if attack is not None:
            return [attack]
    if ctype == 7 and csrc == PAD:
        turn = int(st.get('turn', 0) or 0)
        prizes = int(me.get('prize_n', 0) or 0)
        slots = max(0, 5 - len(me.get('bench') or []))
        active_energy = int(active.get('en', 0) or 0)
        gear_first = turn >= 7 and prizes >= 3 and (hand[CANDY] == 0) or (turn >= 6 and slots >= 1) or (active_energy == 0 and board[MUNK] >= 2)
        if gear_first:
            gear = choose_matching(options, lambda o: int(o.get('type', -1)) == 7 and int(o.get('source_id', 0) or 0) == GEAR)
            if gear is not None:
                return [gear]
    is_gym = ctype == 10 and csrc == 0 and (carea == 7)
    if is_gym and (hand[DARK] == 1 and board[MORG] >= 2 or board[IMP] >= 3):
        dawn = choose_matching(options, lambda o: int(o.get('type', -1)) == 7 and int(o.get('source_id', 0) or 0) == DAWN)
        if dawn is not None:
            return [dawn]
    return base

def _choose_v10_base(st, options, history):
    base = _choose_v9_base(st, options, history)
    if not base or not options:
        return base
    ctx = int(st.get('context', -1))
    if ctx == 21:
        current = options[base[0]]
        if energy_n(st, current) >= 2:
            imp = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == IMP and int(o.get('source_zone', 0) or 0) == 5)
            if imp is not None:
                return [imp]
        return base
    if ctx == 4 and remaining_hp(st, options[base[0]]) <= 130:
        morg = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == MORG)
        if morg is not None:
            return [morg]
    if ctx == 16:
        endangered = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == MUNK and int(o.get('source_zone', 0) or 0) == 5 and (remaining_hp(st, o) == 40)]
        if endangered:
            return [endangered[0]]
        cur = options[base[0]]
        if int(cur.get('source_id', 0) or 0) == GRIM and int(cur.get('source_zone', 0) or 0) == 5 and (remaining_hp(st, cur) >= 170):
            active_grim = choose_matching(options, lambda o: int(o.get('source_id', 0) or 0) == GRIM and int(o.get('source_zone', 0) or 0) == 4)
            if active_grim is not None:
                return [active_grim]
        return base
    if ctx in (13, 15):
        cur = options[base[0]]
        if int(cur.get('source_id', 0) or 0) == MUNK:
            c = card_obj(st, cur)
            sig = (int(cur.get('source_id', 0) or 0), int(cur.get('source_zone', 0) or 0), int(c.get('hp', 0) or 0), int(c.get('maxHp', 0) or 0), int(c.get('en', 0) or 0))
            same = []
            for i, o in enumerate(options):
                co = card_obj(st, o)
                osig = (int(o.get('source_id', 0) or 0), int(o.get('source_zone', 0) or 0), int(co.get('hp', 0) or 0), int(co.get('maxHp', 0) or 0), int(co.get('en', 0) or 0))
                if osig == sig:
                    same.append(i)
            use_last = len(same) >= 3
            if use_last:
                return [same[-1]]
    return base

def _sig6(o):
    return (int(o.get('type', -1)), int(o.get('source_id', 0) or 0), int(o.get('source_zone', 0) or 0), int(o.get('target_id', 0) or 0), int(o.get('target_area', 0) or 0), int(o.get('attack_id', 0) or 0))

def _find_sig6(options, sig):
    for i, o in enumerate(options):
        if _sig6(o) == sig:
            return i
    return None

def choose(st, options, history):
    base = _choose_v10_base(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    cur = _sig6(options[base[0]])
    if ctx == 0:
        if cur == (8, DARK, 2, MUNK, 4, 0):
            j = _find_sig6(options, (7, POFFIN, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (8, DARK, 2, IMP, 5, 0):
            j = _find_sig6(options, (8, DARK, 2, SNOR, 4, 0))
            if j is not None:
                return [j]
        if cur == (9, MORG, 2, IMP, 4, 0):
            for sig in ((7, PAD, 2, 0, 0, 0), (7, NIGHT, 2, 0, 0, 0), (7, GEAR, 2, 0, 0, 0)):
                j = _find_sig6(options, sig)
                if j is not None:
                    return [j]
        if cur == (7, LILLIE, 2, 0, 0, 0):
            for sig in ((7, STAMP, 2, 0, 0, 0), (7, GEAR, 2, 0, 0, 0), (7, PAD, 2, 0, 0, 0)):
                j = _find_sig6(options, sig)
                if j is not None:
                    return [j]
        if cur == (7, CANDY, 2, 0, 0, 0):
            j = _find_sig6(options, (9, FROSLASS, 2, SNOR, 5, 0))
            if j is not None:
                return [j]
        if cur in ((9, GRIM, 2, MORG, 4, 0), (9, FROSLASS, 2, SNOR, 4, 0)):
            j = _find_sig6(options, (9, FROSLASS, 2, SNOR, 5, 0))
            if j is not None:
                return [j]
        if cur == (7, BOSS, 2, 0, 0, 0):
            j = _find_sig6(options, (13, 0, 0, 0, 0, 934))
            if j is not None:
                return [j]
        if cur == (8, DARK, 2, MUNK, 4, 0):
            j = _find_sig6(options, (7, DAWN, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (8, DARK, 2, MUNK, 5, 0):
            j = _find_sig6(options, (7, NIGHT, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (8, DARK, 2, IMP, 5, 0):
            j = _find_sig6(options, (8, DARK, 2, FROSLASS, 4, 0))
            if j is not None:
                return [j]
        if cur == (7, PAD, 2, 0, 0, 0):
            j = _find_sig6(options, (7, NIGHT, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur in ((8, DARK, 2, IMP, 4, 0), (8, DARK, 2, MORG, 4, 0)):
            j = _find_sig6(options, (12, 0, 0, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 3:
        if cur in ((3, MUNK, 5, 0, 0, 0), (3, 741, 5, 0, 0, 0), (3, 742, 5, 0, 0, 0)):
            j = _find_sig6(options, (3, 140, 5, 0, 0, 0))
            if j is not None:
                return [j]
        for old_id, new_id in ((434, 401), (341, 342), (265, 269)):
            if cur == (3, old_id, 5, 0, 0, 0):
                j = _find_sig6(options, (3, new_id, 5, 0, 0, 0))
                if j is not None:
                    return [j]
    if ctx in (13, 15):
        if cur == (3, 434, 5, 0, 0, 0):
            j = _find_sig6(options, (3, 401, 5, 0, 0, 0))
            if j is not None:
                return [j]
        pairs = ((343, 5, 345, 4), (305, 5, 848, 5), (414, 5, 345, 4), (117, 5, 345, 4), (112, 5, 410, 5), (414, 5, 401, 5), (247, 5, 92, 5), (463, 5, 401, 5), (174, 5, 64, 5), (271, 5, 269, 5))
        for old_id, old_zone, new_id, new_zone in pairs:
            if cur == (3, old_id, old_zone, 0, 0, 0):
                j = _find_sig6(options, (3, new_id, new_zone, 0, 0, 0))
                if j is not None:
                    return [j]
    if ctx == 13:
        active = (st.get('op', {}).get('active') or [{}])[0] or {}
        active_hp = int(active.get('hp', 0) or 0)
        active_max = int(active.get('maxHp', 0) or 0)
        active_en = int(active.get('en', 0) or 0)
        cur_hp = remaining_hp(st, options[base[0]])
        if cur == (3, 344, 5, 0, 0, 0) and cur_hp >= 40 and (active_en >= 2):
            j = _find_sig6(options, (3, 345, 4, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, 345, 5, 0, 0, 0) and cur_hp > 40:
            j = _find_sig6(options, (3, 345, 4, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, 434, 5, 0, 0, 0) and (active_hp <= 100 or len(st.get('op', {}).get('bench') or []) >= 3):
            j = _find_sig6(options, (3, 401, 4, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MUNK, 5, 0, 0, 0) and cur_hp >= 50:
            j = _find_sig6(options, (3, 345, 4, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, 756, 5, 0, 0, 0) and cur_hp >= 100:
            j = _find_sig6(options, (3, 345, 4, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 16 and cur == (3, FROSLASS, 4, 0, 0, 0):
        j = _find_sig6(options, (3, IMP, 5, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v11_base = choose

def _v12_pick_sig(options, sig):
    for i, o in enumerate(options):
        if _sig6(o) == sig:
            return i
    return None

def _v12_replace(options, base, old_sig, new_sig):
    if not base or len(base) != 1 or _sig6(options[base[0]]) != old_sig:
        return None
    j = _v12_pick_sig(options, new_sig)
    return [j] if j is not None else None

def _v12_poffin_counts(options, picks):
    c = Counter((int(options[i].get('source_id', 0) or 0) for i in picks))
    return (c[IMP], c[SNOR])

def _v12_poffin_pick(options, imp_n, snor_n):
    out = []
    for cid, need in ((IMP, imp_n), (SNOR, snor_n)):
        for i, o in enumerate(options):
            if i not in out and int(o.get('source_id', 0) or 0) == cid:
                out.append(i)
                if sum((int(options[j].get('source_id', 0) or 0) == cid for j in out)) >= need:
                    break
    return out

def choose(st, options, history):
    base = _choose_v11_base(st, options, history)
    if not base or not options:
        return base
    ctx = int(st.get('context', -1))
    if ctx == 5:
        pred = _v12_poffin_counts(options, base)
        me = st.get('me') or {}
        cards = (me.get('active') or []) + (me.get('bench') or [])
        board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
        hand = Counter(me.get('hand_ids') or [])
        slots = max(0, 5 - len(me.get('bench') or []))
        max_count = int(st.get('max', 0) or 0)
        prize_n = int(me.get('prize_n', 0) or 0)
        opt_imp = sum((int(o.get('source_id', 0) or 0) == IMP for o in options))
        opt_snor = sum((int(o.get('source_id', 0) or 0) == SNOR for o in options))
        if pred == (1, 0) and max_count >= 2 and (board[FROSLASS] >= 1) and (opt_snor >= 1):
            p = _v12_poffin_pick(options, 1, 1)
            if len(p) == 2:
                return p
        if pred == (1, 0) and max_count == 2 and (prize_n == 5) and (opt_snor >= 1):
            p = _v12_poffin_pick(options, 1, 1)
            if len(p) == 2:
                return p
        if pred == (0, 0) and slots == 4 and (max_count == 2) and (opt_imp == 0) and (opt_snor >= 2):
            p = _v12_poffin_pick(options, 0, 2)
            if len(p) == 2:
                return p
    if ctx == 0 and len(base) == 1:
        rules = (((8, DARK, 2, IMP, 5, 0), (7, POFFIN, 2, 0, 0, 0)), ((7, PAD, 2, 0, 0, 0), (7, NIGHT, 2, 0, 0, 0)), ((8, DARK, 2, GRIM, 4, 0), (7, PETREL, 2, 0, 0, 0)), ((8, DARK, 2, GRIM, 5, 0), (7, PETREL, 2, 0, 0, 0)), ((8, DARK, 2, IMP, 5, 0), (8, DARK, 2, MORG, 5, 0)), ((9, GRIM, 2, MORG, 5, 0), (7, GEAR, 2, 0, 0, 0)), ((10, MUNK, 4, MUNK, 4, 0), (9, FROSLASS, 2, SNOR, 5, 0)), ((8, DARK, 2, MORG, 5, 0), (7, NIGHT, 2, 0, 0, 0)), ((7, DAWN, 2, 0, 0, 0), (7, GEAR, 2, 0, 0, 0)))
        for old_sig, new_sig in rules:
            out = _v12_replace(options, base, old_sig, new_sig)
            if out is not None:
                return out
        me = st.get('me') or {}
        cards = (me.get('active') or []) + (me.get('bench') or [])
        board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
        hand = Counter(me.get('hand_ids') or [])
        turn = int(st.get('turn', 0) or 0)
        for old_sig in ((8, DARK, 2, IMP, 5, 0), (8, DARK, 2, MORG, 5, 0)):
            out = _v12_replace(options, base, old_sig, (7, SNOR, 2, 0, 0, 0))
            if out is not None:
                return out
        if turn <= 6 and hand[CANDY] == 0:
            out = _v12_replace(options, base, (7, MUNK, 2, 0, 0, 0), (9, FROSLASS, 2, SNOR, 5, 0))
            if out is not None:
                return out
        if not (turn == 4 and hand[STAMP] >= 1 and (hand[GYM] >= 1)):
            out = _v12_replace(options, base, (9, MORG, 2, IMP, 5, 0), (9, FROSLASS, 2, SNOR, 5, 0))
            if out is not None:
                return out
        if int(me.get('hand_n', 0) or 0) >= 4:
            out = _v12_replace(options, base, (7, STAMP, 2, 0, 0, 0), (10, 0, 7, 0, 7, 0))
            if out is not None:
                return out
    if ctx == 7 and len(base) == 1:
        rules = (((3, MORG, 2, 0, 0, 0), (3, 0, 0, 0, 0, 0)), ((3, GYM, 2, 0, 0, 0), (3, LILLIE, 2, 0, 0, 0)), ((3, CANDY, 2, 0, 0, 0), (3, DARK, 2, 0, 0, 0)), ((3, DARK, 2, 0, 0, 0), (3, POFFIN, 2, 0, 0, 0)))
        for old_sig, new_sig in rules:
            out = _v12_replace(options, base, old_sig, new_sig)
            if out is not None:
                return out
    if ctx == 13 and len(base) == 1:
        pair_rules = {(434, 5): ((431, 5),), (184, 5): ((756, 4),), (112, 4): ((689, 5),), (878, 5): ((311, 5),), (766, 4): ((766, 5),), (414, 5): ((401, 4),), (344, 5): ((344, 4),), (305, 5): ((140, 4),), (247, 5): ((93, 5),), (235, 4): ((410, 5),), (140, 4): ((112, 5),), (112, 5): ((293, 5), (31, 5)), (108, 5): ((63, 5),), (96, 5): ((756, 5),)}
        cur = options[base[0]]
        key = (int(cur.get('source_id', 0) or 0), int(cur.get('source_zone', 0) or 0))
        for nid, nz in pair_rules.get(key, ()):
            j = _v12_pick_sig(options, (3, nid, nz, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 15 and len(base) == 1:
        out = _v12_replace(options, base, (3, 96, 5, 0, 0, 0), (3, 756, 5, 0, 0, 0))
        if out is not None:
            return out
    return base
_choose_v12_base = choose

def choose(st, options, history):
    base = _choose_v12_base(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    if ctx != 0:
        return base
    me = st.get('me') or {}
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    hand = Counter(me.get('hand_ids') or [])
    active = (me.get('active') or [{}])[0] or {}
    active_en = int(active.get('en', 0) or 0)
    cur = _sig6(options[base[0]])
    if cur == (7, STAMP, 2, 0, 0, 0) and board[GRIM] <= 1:
        j = _v12_pick_sig(options, (7, DAWN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (7, STAMP, 2, 0, 0, 0) and active_en <= 1 and (board[MUNK] <= 3):
        j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (7, LILLIE, 2, 0, 0, 0) and int(me.get('hand_n', 0) or 0) >= 5:
        j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (7, MUNK, 2, 0, 0, 0) and hand[NIGHT] == 0:
        j = _v12_pick_sig(options, (9, FROSLASS, 2, SNOR, 5, 0))
        if j is not None:
            return [j]
    if cur == (9, MORG, 2, IMP, 4, 0) and board[MORG] == 0:
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    if cur == (9, MORG, 2, IMP, 4, 0) and board[GRIM] == 0:
        j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (9, MORG, 2, IMP, 4, 0) and active_en <= 1:
        j = _v12_pick_sig(options, (9, GRIM, 2, MORG, 5, 0))
        if j is not None:
            return [j]
    if cur == (8, DARK, 2, MUNK, 4, 0) and board[GRIM] == 0:
        j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (8, DARK, 2, MUNK, 4, 0) and board[GRIM] == 0:
        j = _v12_pick_sig(options, (7, SNOR, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (8, DARK, 2, MUNK, 4, 0) and bench_slots(st) == 3:
        j = _v12_pick_sig(options, (7, LILLIE, 2, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v13_main = choose

def choose(st, options, history):
    base = _choose_v13_main(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    if ctx not in (13, 15):
        return base
    cur = _sig6(options[base[0]])
    my_prize = int((st.get('me') or {}).get('prize_n', 0) or 0)
    op_prize = int((st.get('op') or {}).get('prize_n', 0) or 0)
    turn = int(st.get('turn', 0) or 0)

    def pick(sig):
        j = _v12_pick_sig(options, sig)
        return [j] if j is not None else None

    def option_obj(sig):
        j = _v12_pick_sig(options, sig)
        return (j, card_obj(st, options[j])) if j is not None else (None, {})
    if ctx == 13:
        if cur == (3, 344, 5, 0, 0, 0):
            sig = (3, 345, 4, 0, 0, 0)
            j, obj = option_obj(sig)
            if j is not None:
                dmg = max(0, int(obj.get('maxHp', 0) or 0) - int(obj.get('hp', 0) or 0))
                if dmg >= 30:
                    return [j]
            sig = (3, 345, 5, 0, 0, 0)
            j, obj = option_obj(sig)
            if j is not None and int(obj.get('en', 0) or 0) >= 2:
                return [j]
        if cur == (3, 756, 5, 0, 0, 0):
            sig = (3, 345, 4, 0, 0, 0)
            j, obj = option_obj(sig)
            hp = int(obj.get('hp', 0) or 0)
            mx = int(obj.get('maxHp', 0) or 0)
            if j is not None and mx <= 190 and (hp >= 70):
                return [j]
        if cur == (3, 305, 5, 0, 0, 0) and my_prize >= 4:
            out = pick((3, 849, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 414, 4, 0, 0, 0) and my_prize == 1:
            out = pick((3, 431, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 174, 5, 0, 0, 0) and turn <= 9:
            out = pick((3, 848, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 90, 5, 0, 0, 0) and my_prize <= 2:
            out = pick((3, 92, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 112, 5, 0, 0, 0) and op_prize <= 5:
            hp = remaining_hp(st, options[base[0]])
            if hp >= 100:
                out = pick((3, 119, 5, 0, 0, 0))
                if out is not None:
                    return out
    if ctx == 15:
        if cur == (3, 380, 5, 0, 0, 0) and remaining_hp(st, options[base[0]]) >= 80:
            out = pick((3, 342, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 112, 5, 0, 0, 0) and remaining_hp(st, options[base[0]]) >= 90:
            out = pick((3, 119, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 742, 5, 0, 0, 0) and remaining_hp(st, options[base[0]]) >= 60:
            out = pick((3, 343, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 305, 5, 0, 0, 0):
            sig = (3, 849, 5, 0, 0, 0)
            j, obj = option_obj(sig)
            if j is not None and int(obj.get('hp', 0) or 0) <= 150:
                return [j]
        if cur == (3, 174, 5, 0, 0, 0) and op_prize >= 4:
            out = pick((3, 848, 5, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, 434, 5, 0, 0, 0) and my_prize >= 4:
            out = pick((3, 431, 5, 0, 0, 0))
            if out is not None:
                return out
    return base
_choose_v13_targets = choose

def choose(st, options, history):
    base = _choose_v13_targets(st, options, history)
    if not base or not options or len(base) != 1 or (int(st.get('context', -1)) != 16):
        return base
    cur = _sig6(options[base[0]])

    def pick_obj(sig):
        j = _v12_pick_sig(options, sig)
        return (j, card_obj(st, options[j])) if j is not None else (None, {})
    old_obj = card_obj(st, options[base[0]])
    old_hp = int(old_obj.get('hp', 0) or 0)
    old_max = int(old_obj.get('maxHp', 0) or 0)
    old_en = int(old_obj.get('en', 0) or 0)
    old_dmg = max(0, old_max - old_hp)
    if cur == (3, MUNK, 5, 0, 0, 0) and old_hp >= 70 and (old_en == 0):
        j, obj = pick_obj((3, GRIM, 4, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (3, MUNK, 5, 0, 0, 0) and old_hp >= 90:
        j, obj = pick_obj((3, GRIM, 5, 0, 0, 0))
        if j is not None:
            new_dmg = max(0, int(obj.get('maxHp', 0) or 0) - int(obj.get('hp', 0) or 0))
            if new_dmg - old_dmg >= 150:
                return [j]
    if cur == (3, GRIM, 4, 0, 0, 0):
        j, obj = pick_obj((3, IMP, 5, 0, 0, 0))
        if j is not None and int(obj.get('hp', 0) or 0) <= 30:
            return [j]
    if cur == (3, IMP, 5, 0, 0, 0):
        j, obj = pick_obj((3, GRIM, 4, 0, 0, 0))
        if j is not None:
            hp = int(obj.get('hp', 0) or 0)
            if 170 <= hp <= 200:
                return [j]
    if cur == (3, MUNK, 4, 0, 0, 0):
        j, obj = pick_obj((3, MUNK, 5, 0, 0, 0))
        if j is not None:
            new_dmg = max(0, int(obj.get('maxHp', 0) or 0) - int(obj.get('hp', 0) or 0))
            if new_dmg - old_dmg >= 20:
                return [j]
    return base
_choose_v13_sources = choose

def choose(st, options, history):
    base = _choose_v13_sources(st, options, history)
    if not base or not options or len(base) != 1 or (int(st.get('context', -1)) != 0):
        return base
    me = st.get('me') or {}
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    hand = Counter(me.get('hand_ids') or [])
    cur = _sig6(options[base[0]])
    if cur == (7, STAMP, 2, 0, 0, 0) and board[SNOR] >= 1:
        j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (9, MORG, 2, IMP, 4, 0) and bench_slots(st) >= 1 and (hand[STAMP] == 0):
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    if cur == (7, MUNK, 2, 0, 0, 0) and int(me.get('hand_n', 0) or 0) >= 7 and (hand[GRIM] == 0):
        j = _v12_pick_sig(options, (9, FROSLASS, 2, SNOR, 5, 0))
        if j is not None:
            return [j]
    if cur == (8, DARK, 2, MUNK, 4, 0) and hand[FROSLASS] == 1:
        j = _v12_pick_sig(options, (7, SNOR, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (7, LILLIE, 2, 0, 0, 0) and board[IMP] == 1:
        j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (8, DARK, 2, MUNK, 4, 0) and board[MORG] <= 1 and (hand[DARK] == 1):
        j = _v12_pick_sig(options, (7, LILLIE, 2, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v13_residual_order = choose

def choose(st, options, history):
    base = _choose_v13_residual_order(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    me = st.get('me') or {}
    op = st.get('op') or {}
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    hand = Counter(me.get('hand_ids') or [])
    cur = _sig6(options[base[0]])
    turn = int(st.get('turn', 0) or 0)
    my_prize = int(me.get('prize_n', 0) or 0)
    if ctx == 7:
        discard_n = len(me.get('discard_ids') or [])
        active = (me.get('active') or [{}])[0] or {}
        active_en = int(active.get('en', 0) or 0)
        if cur == (3, MORG, 3, 0, 0, 0) and board[SNOR] >= 1 and (turn <= 10):
            j = _v12_pick_sig(options, (3, FROSLASS, 3, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MORG, 3, 0, 0, 0) and bench_slots(st) >= 1 and (discard_n <= 18):
            j = _v12_pick_sig(options, (3, MUNK, 3, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, GRIM, 3, 0, 0, 0) and hand[CANDY] == 0 and (discard_n <= 19):
            j = _v12_pick_sig(options, (3, MUNK, 3, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, SNOR, 3, 0, 0, 0) and active_en <= 2 and (bench_slots(st) <= 2):
            j = _v12_pick_sig(options, (3, DARK, 3, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 13:
        if cur == (3, 431, 5, 0, 0, 0):
            obj = card_obj(st, options[base[0]])
            if int(obj.get('en', 0) or 0) == 0:
                j = _v12_pick_sig(options, (3, 414, 5, 0, 0, 0))
                if j is not None:
                    return [j]
        if cur == (3, 434, 4, 0, 0, 0):
            obj = card_obj(st, options[base[0]])
            if int(obj.get('hp', 0) or 0) == 60:
                j = _v12_pick_sig(options, (3, 431, 5, 0, 0, 0))
                if j is not None:
                    return [j]
        if cur == (3, 305, 5, 0, 0, 0) and my_prize >= 4:
            j = _v12_pick_sig(options, (3, 743, 5, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 15:
        if cur == (3, IMP, 5, 0, 0, 0):
            obj = card_obj(st, options[base[0]])
            if int(obj.get('hp', 0) or 0) == 70:
                j = _v12_pick_sig(options, (3, SNOR, 5, 0, 0, 0))
                if j is not None:
                    return [j]
        if cur == (3, 434, 5, 0, 0, 0):
            j = _v12_pick_sig(options, (3, 414, 5, 0, 0, 0))
            if j is not None:
                obj = card_obj(st, options[j])
                if int(obj.get('hp', 0) or 0) <= 80:
                    return [j]
        if cur == (3, 184, 5, 0, 0, 0) and turn <= 7:
            j = _v12_pick_sig(options, (3, 756, 5, 0, 0, 0))
            if j is not None:
                return [j]
    return base
_choose_v13_search_targets = choose

def choose(st, options, history):
    base = _choose_v13_search_targets(st, options, history)
    if not options or int(st.get('context', -1)) != 5:
        return base
    me = st.get('me') or {}
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    hand = Counter(me.get('hand_ids') or [])
    turn = int(st.get('turn', 0) or 0)
    slots = bench_slots(st)
    opt_imp = sum((int(o.get('source_id', 0) or 0) == IMP for o in options))
    opt_snor = sum((int(o.get('source_id', 0) or 0) == SNOR for o in options))
    pat = tuple((int(options[i].get('source_id', 0) or 0) for i in base))
    if pat == (IMP,) and turn == 1 and (hand[FROSLASS] >= 1) and (opt_snor >= 1) and (opt_imp >= 1):
        p = []
        for cid in (SNOR, IMP):
            j = next((i for i, o in enumerate(options) if i not in p and int(o.get('source_id', 0) or 0) == cid), None)
            if j is not None:
                p.append(j)
        if len(p) == 2:
            return p
    if pat == (IMP,) and hand[IMP] == 1 and (opt_snor >= 1):
        j = next((i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == SNOR), None)
        if j is not None:
            return [j]
    if pat == () and slots == 4 and (opt_snor >= 2):
        p = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == SNOR][:2]
        if len(p) == 2:
            return p
    if pat == (IMP, IMP) and int(st.get('stadium', 0) or 0) == 1257 and (board[SNOR] == 0) and (opt_snor >= 1):
        p = []
        for cid in (SNOR, IMP):
            j = next((i for i, o in enumerate(options) if i not in p and int(o.get('source_id', 0) or 0) == cid), None)
            if j is not None:
                p.append(j)
        if len(p) == 2:
            return p
    if pat == (IMP, IMP) and hand[MUNK] >= 2 and (opt_snor >= 1):
        p = _v12_poffin_pick(options, 1, 1)
        if len(p) == 2:
            return p
    return base
_choose_v14_base = choose

def choose(st, options, history):
    base = _choose_v14_base(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    me = st.get('me') or {}
    op = st.get('op') or {}
    own_cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in own_cards))
    hand = Counter(me.get('hand_ids') or [])
    discard_ids = me.get('discard_ids') or []
    recoverable = sum((discard_ids.count(cid) for cid in (DARK, IMP, MORG, GRIM, MUNK, SNOR, FROSLASS)))
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    active_id = int(active.get('id', 0) or 0)
    active_hp = int(active.get('hp', 0) or 0)
    active_en = int(active.get('en', 0) or 0)
    op_active_id = int(op_active.get('id', 0) or 0)
    turn = int(st.get('turn', 0) or 0)
    tac = int(st.get('tac', 0) or 0)
    cur = _sig6(options[base[0]])
    if ctx == 0:
        if cur == (9, GRIM, 2, MORG, 5, 0) and turn >= 7 and (len(discard_ids) <= 5):
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (7, LILLIE, 2, 0, 0, 0) and op_active_id == 743 and (len(discard_ids) >= 16):
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (7, MUNK, 2, 0, 0, 0) and op_active_id == 743:
            j = _v12_pick_sig(options, (9, MORG, 2, IMP, 5, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and board[GRIM] >= 2 and (bench_slots(st) == 0):
            j = _v12_pick_sig(options, (7, PAD, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (7, IMP, 2, 0, 0, 0) and board[MORG] == 2 and (int(me.get('hand_n', 0) or 0) <= 3):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (8, DARK, 2, MUNK, 5, 0) and op_active_id == 743 and (active_hp <= 90):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (7, PAD, 2, 0, 0, 0) and recoverable >= 8 and (active_en == 1):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and int(op.get('prize_n', 0) or 0) == 3 and (tac >= 16):
            j = _v12_pick_sig(options, (7, LILLIE, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and turn >= 19 and (recoverable >= 5):
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (9, GRIM, 2, MORG, 5, 0) and turn >= 23:
            j = _v12_pick_sig(options, (13, 0, 0, 0, 0, SHADOW))
            if j is not None:
                return [j]
        if cur == (12, 0, 0, 0, 0, 0) and turn == 10 and (hand[BOSS] >= 1):
            j = _v12_pick_sig(options, (13, 0, 0, 0, 0, SHADOW))
            if j is not None:
                return [j]
        if cur == (7, MUNK, 2, 0, 0, 0) and recoverable >= 10 and (int(me.get('hand_n', 0) or 0) <= 6):
            j = _v12_pick_sig(options, (7, IMP, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and op_active_id == 434 and (bench_slots(st) >= 4):
            j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 7:
        if cur == (3, FROSLASS, 1, 0, 0, 0) and op_active_id == IMP:
            j = _v12_pick_sig(options, (3, MUNK, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MUNK, 1, 0, 0, 0) and op_active_id == 743 and (hand[MUNK] == 1):
            j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MORG, 1, 0, 0, 0) and hand[CANDY] == 1 and (hand[PAD] >= 1):
            j = _v12_pick_sig(options, (3, GRIM, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, GRIM, 1, 0, 0, 0) and active_id == SNOR and (board[SNOR] == 2):
            j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, GRIM, 1, 0, 0, 0) and bench_slots(st) >= 4 and (op_active_id == MUNK):
            j = _v12_pick_sig(options, (3, IMP, 1, 0, 0, 0))
            if j is not None:
                return [j]
    return base
_choose_v14_resource_phase = choose

def choose(st, options, history):
    base = _choose_v14_resource_phase(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    me = st.get('me') or {}
    op = st.get('op') or {}
    own_cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in own_cards))
    cur = _sig6(options[base[0]])
    turn = int(st.get('turn', 0) or 0)
    if ctx == 16:
        old_obj = card_obj(st, options[base[0]])
        old_hp = int(old_obj.get('hp', 0) or 0)
        old_dmg = max(0, int(old_obj.get('maxHp', 0) or 0) - old_hp)

        def candidate(sig6):
            j = _v12_pick_sig(options, sig6)
            return (j, card_obj(st, options[j])) if j is not None else (None, {})
        if cur == (3, MUNK, 5, 0, 0, 0):
            j, obj = candidate((3, GRIM, 4, 0, 0, 0))
            if j is not None:
                new_dmg = max(0, int(obj.get('maxHp', 0) or 0) - int(obj.get('hp', 0) or 0))
                if board[FROSLASS] >= 1 and new_dmg - old_dmg >= 230:
                    return [j]
            j, obj = candidate((3, GRIM, 5, 0, 0, 0))
            if j is not None and turn >= 15 and (old_hp == 100):
                return [j]
        if cur == (3, GRIM, 4, 0, 0, 0):
            if int(me.get('prize_n', 0) or 0) == 1 and old_hp == 100:
                j, _ = candidate((3, MUNK, 5, 0, 0, 0))
                if j is not None:
                    return [j]
            j, obj = candidate((3, MORG, 5, 0, 0, 0))
            if j is not None and bench_slots(st) >= 1 and (int(obj.get('hp', 0) or 0) <= 50):
                return [j]
            j, obj = candidate((3, IMP, 5, 0, 0, 0))
            if j is not None and board[GRIM] == 1 and (int(obj.get('en', 0) or 0) >= 1):
                return [j]
    if ctx == 13:
        if cur == (3, 344, 5, 0, 0, 0) and turn >= 6:
            old_obj = card_obj(st, options[base[0]])
            if int(old_obj.get('en', 0) or 0) == 0:
                j = _v12_pick_sig(options, (3, 345, 4, 0, 0, 0))
                if j is not None:
                    return [j]
    if ctx == 15:
        if cur == (3, 380, 5, 0, 0, 0):
            old_obj = card_obj(st, options[base[0]])
            op_active = (op.get('active') or [{}])[0] or {}
            if int(old_obj.get('en', 0) or 0) == 0 and int(op_active.get('en', 0) or 0) == 1:
                j = _v12_pick_sig(options, (3, 342, 5, 0, 0, 0))
                if j is not None:
                    return [j]
        if cur == (3, 434, 5, 0, 0, 0):
            if int(me.get('prize_n', 0) or 0) >= 2 and int(op.get('prize_n', 0) or 0) >= 4:
                j = _v12_pick_sig(options, (3, 431, 5, 0, 0, 0))
                if j is not None:
                    return [j]
    return base
_choose_v15_base = choose

def choose(st, options, history):
    base = _choose_v15_base(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    if int(st.get('context', -1)) != 0:
        return base
    me = st.get('me') or {}
    op = st.get('op') or {}
    hand = Counter(me.get('hand_ids') or [])
    cur = _sig6(options[base[0]])
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    active_hp = int(active.get('hp', 0) or 0)
    op_active_id = int(op_active.get('id', 0) or 0)
    discard_n = len(me.get('discard_ids') or [])
    hist_n = len(history or [])
    energy_flag = bool((st.get('flags') or {}).get('energy'))
    my_prize = int(me.get('prize_n', 0) or 0)
    op_prize = int(op.get('prize_n', 0) or 0)
    if cur == (10, 0, 7, 0, 7, 0) and op_active_id == 344 and (active_hp <= 130):
        j = _v12_pick_sig(options, (8, DARK, 2, MUNK, 5, 0))
        if j is not None:
            return [j]
    if cur == (7, PAD, 2, 0, 0, 0) and hand[CANDY] == 1 and (hist_n <= 2):
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    if op_active_id == 743:
        if cur == (10, 0, 7, 0, 7, 0) and discard_n >= 19:
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (7, LILLIE, 2, 0, 0, 0) and hand[DARK] >= 1:
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (7, MUNK, 2, 0, 0, 0) and op_prize <= 2:
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
    if cur == (9, GRIM, 2, MORG, 5, 0) and int(me.get('hand_n', 0) or 0) == 6 and energy_flag:
        j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
        if j is not None:
            return [j]
    board = Counter((int((c or {}).get('id', 0) or 0) for c in (me.get('active') or []) + (me.get('bench') or [])))
    if cur == (10, 0, 7, 0, 7, 0) and board[IMP] == 0 and (op_active_id == SNOR):
        j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (10, 0, 7, 0, 7, 0) and my_prize <= 2 and (bench_slots(st) == 2):
        j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v15_phase1 = choose

def choose(st, options, history):
    base = _choose_v15_phase1(st, options, history)
    if not base or not options or len(base) != 1 or (int(st.get('context', -1)) != 0):
        return base
    me = st.get('me') or {}
    op = st.get('op') or {}
    hand = Counter(me.get('hand_ids') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in (me.get('active') or []) + (me.get('bench') or [])))
    cur = _sig6(options[base[0]])
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    op_active_id = int(op_active.get('id', 0) or 0)
    op_active_max = int(op_active.get('maxHp', 0) or 0)
    active_hp = int(active.get('hp', 0) or 0)
    discard_n = len(me.get('discard_ids') or [])
    my_prize = int(me.get('prize_n', 0) or 0)
    op_prize = int(op.get('prize_n', 0) or 0)
    if cur == (10, 0, 7, 0, 7, 0):
        if my_prize == 2 and discard_n >= 24:
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if hand[MORG] == 2 and op_prize <= 3:
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if board[GRIM] >= 2 and hand[LILLIE] == 1:
            j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if hand[GRIM] >= 2 and hand[BOSS] == 1:
            j = _v12_pick_sig(options, (7, POFFIN, 2, 0, 0, 0))
            if j is not None:
                return [j]
    if cur == (7, PAD, 2, 0, 0, 0) and op_prize == 1 and (discard_n <= 16):
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    if cur == (9, GRIM, 2, MORG, 5, 0) and op_active_max <= 80 and (active_hp >= 120):
        j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (7, MUNK, 2, 0, 0, 0) and op_prize == 1 and (op_active_id == 401):
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    if cur == (7, LILLIE, 2, 0, 0, 0) and hand[CANDY] >= 1 and (op_active_id == 743):
        j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
        if j is not None:
            return [j]
    return base
_choose_v15_order2 = choose

def choose(st, options, history):
    base = _choose_v15_order2(st, options, history)
    if not base or not options or len(base) != 1 or (int(st.get('context', -1)) != 16):
        return base
    me = st.get('me') or {}
    board = Counter((int((c or {}).get('id', 0) or 0) for c in (me.get('active') or []) + (me.get('bench') or [])))
    cur = _sig6(options[base[0]])
    old = card_obj(st, options[base[0]])
    old_hp = int(old.get('hp', 0) or 0)
    old_max = int(old.get('maxHp', 0) or 0)
    old_en = int(old.get('en', 0) or 0)
    old_dmg = max(0, old_max - old_hp)

    def candidate(ss):
        j = _v12_pick_sig(options, ss)
        return (j, card_obj(st, options[j])) if j is not None else (None, {})
    if cur == (3, GRIM, 4, 0, 0, 0):
        j, obj = candidate((3, MUNK, 5, 0, 0, 0))
        if j is not None and old_hp >= 220 and (int(obj.get('en', 0) or 0) >= 2):
            return [j]
        j, obj = candidate((3, IMP, 5, 0, 0, 0))
        if j is not None and old_en >= 2 and (int(obj.get('en', 0) or 0) >= 1):
            return [j]
        j, obj = candidate((3, MORG, 5, 0, 0, 0))
        if j is not None:
            new_dmg = max(0, int(obj.get('maxHp', 0) or 0) - int(obj.get('hp', 0) or 0))
            if new_dmg - old_dmg >= -100:
                return [j]
    if cur == (3, MUNK, 4, 0, 0, 0) and bench_slots(st) == 1:
        j, obj = candidate((3, MUNK, 5, 0, 0, 0))
        if j is not None and int(obj.get('hp', 0) or 0) == 100:
            return [j]
    if cur == (3, MUNK, 5, 0, 0, 0) and int(st.get('turn', 0) or 0) >= 17 and (old_hp >= 90):
        j, _ = candidate((3, GRIM, 5, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v15_sources = choose

def choose(st, options, history):
    base = _choose_v15_sources(st, options, history)
    if not base or not options or len(base) != 1 or (int(st.get('context', -1)) != 7):
        return base
    me = st.get('me') or {}
    op = st.get('op') or {}
    hand = Counter(me.get('hand_ids') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in (me.get('active') or []) + (me.get('bench') or [])))
    discard = Counter(me.get('discard_ids') or [])
    cur = _sig6(options[base[0]])
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    turn = int(st.get('turn', 0) or 0)
    tac = int(st.get('tac', 0) or 0)
    prize = int(me.get('prize_n', 0) or 0)
    active_id = int(active.get('id', 0) or 0)
    active_max = int(active.get('maxHp', 0) or 0)
    op_active_id = int(op_active.get('id', 0) or 0)
    discard_n = len(me.get('discard_ids') or [])
    recoverable = sum((discard[c] for c in (DARK, IMP, MORG, GRIM, MUNK, SNOR, FROSLASS)))
    if cur == (3, GYM, 1, 0, 0, 0):
        if active_id == IMP and hand[GRIM] >= 1:
            j = _v12_pick_sig(options, (3, CANDY, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if bench_slots(st) == 4 and hand[GRIM] >= 1:
            j = _v12_pick_sig(options, (3, CANDY, 1, 0, 0, 0))
            if j is not None:
                return [j]
    if cur == (3, MORG, 1, 0, 0, 0):
        if int(me.get('hand_n', 0) or 0) <= 4 and hand[CANDY] == 2 or (turn >= 12 and bench_slots(st) >= 2):
            j = _v12_pick_sig(options, (3, GRIM, 1, 0, 0, 0))
            if j is not None:
                return [j]
    if cur == (3, GRIM, 1, 0, 0, 0) and hand[CANDY] == 0 and (active_id == SNOR):
        j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (3, MUNK, 1, 0, 0, 0):
        if board[SNOR] >= 1 and op_active_id == 743:
            j = _v12_pick_sig(options, (3, FROSLASS, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if active_max == 90 and discard_n >= 8:
            j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if tac >= 20 and prize <= 2 or (hand[DARK] == 0 and recoverable >= 7):
            j = _v12_pick_sig(options, (3, IMP, 1, 0, 0, 0))
            if j is not None:
                return [j]
    if cur == (3, GRIM, 1, 0, 0, 0) and turn <= 1 and (board[IMP] == 1):
        j = _v12_pick_sig(options, (3, IMP, 1, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (3, FROSLASS, 1, 0, 0, 0) and hand[DARK] >= 1 and (op_active_id == MUNK):
        j = _v12_pick_sig(options, (3, MUNK, 1, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (3, NIGHT, 1, 0, 0, 0) and board[SNOR] >= 1 and (hand[DARK] >= 1):
        j = _v12_pick_sig(options, (3, PAD, 1, 0, 0, 0))
        if j is not None:
            return [j]
    if cur == (3, PAD, 1, 0, 0, 0):
        if board[MORG] >= 2 and hand[GYM] >= 1:
            j = _v12_pick_sig(options, (3, NIGHT, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if discard_n >= 22:
            j = _v12_pick_sig(options, (3, LILLIE, 1, 0, 0, 0))
            if j is not None:
                return [j]
    if cur == (3, STAMP, 1, 0, 0, 0) and bench_slots(st) >= 4 and (hand[LILLIE] >= 2):
        j = _v12_pick_sig(options, (3, GYM, 1, 0, 0, 0))
        if j is not None:
            return [j]
    return base
_choose_v15_search = choose

def choose(st, options, history):
    base = _choose_v15_search(st, options, history)
    if int(st.get('context', -1)) != 5 or not options:
        return base
    me = st.get('me') or {}
    hand = Counter(me.get('hand_ids') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in (me.get('active') or []) + (me.get('bench') or [])))
    discard = Counter(me.get('discard_ids') or [])
    active = (me.get('active') or [{}])[0] or {}
    source_ids = tuple((int(options[i].get('source_id', 0) or 0) for i in base or []))
    slots = bench_slots(st)
    discard_n = len(me.get('discard_ids') or [])
    prize = int(me.get('prize_n', 0) or 0)
    stadium = int(st.get('stadium', 0) or 0)
    active_en = int(active.get('en', 0) or 0)
    recoverable = sum((discard[c] for c in (DARK, IMP, MORG, GRIM, MUNK, SNOR, FROSLASS)))

    def pick_ids(want):
        out = []
        used = set()
        for cid in want:
            j = next((i for i, o in enumerate(options) if i not in used and int((o or {}).get('source_id', 0) or 0) == cid), None)
            if j is None:
                return None
            out.append(j)
            used.add(j)
        return out
    if source_ids == (IMP, IMP):
        if board[IMP] == 2 and hand[PAD] == 1 or (hand[GYM] == 1 and stadium == 0):
            chosen = pick_ids((IMP, SNOR))
            if chosen is not None:
                return chosen
    if source_ids == ():
        if board[IMP] == 1 and stadium <= 1257 or (prize <= 2 and recoverable <= 6):
            chosen = pick_ids((SNOR,))
            if chosen is not None:
                return chosen
    if source_ids == (IMP,):
        if slots >= 3 and active_en >= 3:
            chosen = pick_ids((SNOR, IMP))
            if chosen is not None:
                return chosen
        if slots >= 2 and discard_n >= 15:
            chosen = pick_ids((IMP, SNOR))
            if chosen is not None:
                return chosen
    return base
_choose_v16_base = choose

def choose(st, options, history):
    base = _choose_v16_base(st, options, history)
    if not base or not options or len(base) != 1:
        return base
    ctx = int(st.get('context', -1))
    me = st.get('me') or {}
    op = st.get('op') or {}
    hand = Counter(me.get('hand_ids') or [])
    cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in cards))
    discard = Counter(me.get('discard_ids') or [])
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    cur = _sig6(options[base[0]])
    active_id = int(active.get('id', 0) or 0)
    active_hp = int(active.get('hp', 0) or 0)
    active_max = int(active.get('maxHp', 0) or 0)
    active_en = int(active.get('en', 0) or 0)
    op_active_id = int(op_active.get('id', 0) or 0)
    tac = int(st.get('tac', 0) or 0)
    recoverable = sum((discard[c] for c in (DARK, IMP, MORG, GRIM, MUNK, SNOR, FROSLASS)))
    if ctx == 0:
        if cur == (10, 0, 7, 0, 7, 0) and active_id == SNOR and (active_hp <= 60):
            j = _v12_pick_sig(options, (8, DARK, 2, MUNK, 5, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and active_max == 110 and (hand[GYM] == 3):
            j = _v12_pick_sig(options, (8, DARK, 2, MUNK, 5, 0))
            if j is not None:
                return [j]
        if cur == (7, PAD, 2, 0, 0, 0) and active_max == 100 and (hand[CANDY] >= 1):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (9, GRIM, 2, MORG, 5, 0) and op_active_id == 345:
            j = _v12_pick_sig(options, (7, PETREL, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (10, 0, 7, 0, 7, 0) and op_active_id == 345 and (active_en >= 2):
            j = _v12_pick_sig(options, (7, LILLIE, 2, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (7, MUNK, 2, 0, 0, 0) and op_active_id == 741:
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (7, LILLIE, 2, 0, 0, 0) and op_active_id == 305 and (hand[CANDY] >= 1):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
        if cur == (7, PAD, 2, 0, 0, 0) and op_active_id == 121 and (bench_slots(st) >= 1):
            j = _v12_pick_sig(options, (10, 0, 7, 0, 7, 0))
            if j is not None:
                return [j]
    if ctx == 7:
        if cur == (3, MORG, 1, 0, 0, 0) and hand[CANDY] >= 1 and (op_active_id == 305):
            j = _v12_pick_sig(options, (3, GRIM, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, GRIM, 1, 0, 0, 0) and board[SNOR] == 2 and (board[GRIM] >= 1):
            j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MUNK, 1, 0, 0, 0) and op_active_id == 119:
            j = _v12_pick_sig(options, (3, IMP, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MUNK, 1, 0, 0, 0) and tac >= 8 and (recoverable >= 10):
            j = _v12_pick_sig(options, (3, MORG, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, FROSLASS, 1, 0, 0, 0) and op_active_id == GRIM and (bench_slots(st) >= 2):
            j = _v12_pick_sig(options, (3, MUNK, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, MUNK, 1, 0, 0, 0) and op_active_id == 345 and (board[SNOR] >= 1):
            j = _v12_pick_sig(options, (3, FROSLASS, 1, 0, 0, 0))
            if j is not None:
                return [j]
        if cur == (3, NIGHT, 1, 0, 0, 0) and board[SNOR] == 2:
            j = _v12_pick_sig(options, (3, PAD, 1, 0, 0, 0))
            if j is not None:
                return [j]
    if ctx == 16:
        candidates = [i for i, o in enumerate(options) if int((o or {}).get('source_id', 0) or 0) == MUNK and int((o or {}).get('source_zone', 0) or 0) == 5]
        if candidates:
            j = min(candidates, key=lambda i: (remaining_hp(st, options[i]), i))
            if remaining_hp(st, options[j]) == 20:
                return [j]
    return base
_choose_v16_second_base = choose

def choose(st, options, history):
    base = _choose_v16_second_base(st, options, history)
    if not options:
        return base
    ctx = int(st.get('context', -1))
    me = st.get('me') or {}
    op = st.get('op') or {}
    hand = Counter(me.get('hand_ids') or [])
    board_cards = (me.get('active') or []) + (me.get('bench') or [])
    board = Counter((int((c or {}).get('id', 0) or 0) for c in board_cards))
    discard_n = len(me.get('discard_ids') or [])
    active = (me.get('active') or [{}])[0] or {}
    op_active = (op.get('active') or [{}])[0] or {}
    active_hp = int(active.get('hp', 0) or 0)
    op_active_id = int(op_active.get('id', 0) or 0)
    turn = int(st.get('turn', 0) or 0)
    tac = int(st.get('tac', 0) or 0)
    prize = int(me.get('prize_n', 0) or 0)
    slots = bench_slots(st)

    def pick_sig(s):
        j = _v12_pick_sig(options, s)
        return [j] if j is not None else None
    if ctx == 0 and base and (len(base) == 1):
        cur = _sig6(options[base[0]])
        if cur == (10, 0, 7, 0, 7, 0) and slots == 4 and (hand[LILLIE] == 2):
            out = pick_sig((7, POFFIN, 2, 0, 0, 0))
            if out is not None:
                return out
        if cur == (7, LILLIE, 2, 0, 0, 0) and hand[LILLIE] == 2 and (discard_n >= 21):
            out = pick_sig((10, 0, 7, 0, 7, 0))
            if out is not None:
                return out
        if cur == (7, MUNK, 2, 0, 0, 0) and prize <= 2 and (hand[PETREL] >= 2):
            out = pick_sig((10, 0, 7, 0, 7, 0))
            if out is not None:
                return out
        if cur == (7, PAD, 2, 0, 0, 0) and tac >= 9 and (discard_n <= 2):
            out = pick_sig((10, 0, 7, 0, 7, 0))
            if out is not None:
                return out
        if cur == (7, LILLIE, 2, 0, 0, 0) and hand[DARK] >= 1 and (op_active_id == 401):
            out = pick_sig((10, 0, 7, 0, 7, 0))
            if out is not None:
                return out
    if ctx == 7 and base and (len(base) == 1):
        cur = _sig6(options[base[0]])
        if cur == (3, MORG, 1, 0, 0, 0) and hand[MORG] >= 1 and (hand[PAD] == 1):
            out = pick_sig((3, GRIM, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, GRIM, 1, 0, 0, 0) and op_active_id == SNOR and (hand[CANDY] == 0):
            out = pick_sig((3, MORG, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, MUNK, 1, 0, 0, 0) and int(me.get('hand_n', 0) or 0) <= 2 and (slots == 4):
            out = pick_sig((3, IMP, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, MUNK, 1, 0, 0, 0) and op_active_id == 140 and (tac >= 10):
            out = pick_sig((3, MORG, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, NIGHT, 1, 0, 0, 0) and hand[LILLIE] == 2 and (turn <= 10):
            out = pick_sig((3, PAD, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, PAD, 1, 0, 0, 0) and hand[DARK] == 0 and (op_active_id == GRIM) and (turn >= 10):
            out = pick_sig((3, LILLIE, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, GYM, 1, 0, 0, 0) and int(me.get('hand_n', 0) or 0) >= 7 and (hand[GRIM] == 1):
            out = pick_sig((3, CANDY, 1, 0, 0, 0))
            if out is not None:
                return out
        if cur == (3, STAMP, 1, 0, 0, 0) and hand[CANDY] == 2 and (discard_n == 0):
            out = pick_sig((3, GYM, 1, 0, 0, 0))
            if out is not None:
                return out
    if ctx == 13 and base and (len(base) == 1):
        cur_o = options[base[0]]
        cur_id = int(cur_o.get('source_id', 0) or 0)
        cur_zone = int(cur_o.get('source_zone', 0) or 0)
        cur_damage = damage(st, cur_o)
        if cur_id == MUNK and cur_zone == 5 and (prize == 1):
            active_grim = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == GRIM and int(o.get('source_zone', 0) or 0) == 4]
            if active_grim:
                j = active_grim[0]
                if damage(st, options[j]) - cur_damage >= 220:
                    return [j]
            bench_grim = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == GRIM and int(o.get('source_zone', 0) or 0) == 5]
            if bench_grim:
                j = max(bench_grim, key=lambda i: (damage(st, options[i]), -i))
                if damage(st, options[j]) - cur_damage >= 210:
                    return [j]
        if cur_id == MUNK and cur_zone == 5 and (prize <= 2) and (int(me.get('hand_n', 0) or 0) >= 10):
            cand = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == IMP and int(o.get('source_zone', 0) or 0) == 5]
            if cand:
                return [cand[-1]]
        opp_imp = sum((int((c or {}).get('id', 0) or 0) == IMP for c in (op.get('active') or []) + (op.get('bench') or [])))
        if cur_id == MUNK and cur_zone == 5 and (prize <= 2) and (opp_imp == 1):
            cand = [i for i, o in enumerate(options) if int(o.get('source_id', 0) or 0) == SNOR and int(o.get('source_zone', 0) or 0) == 5]
            if cand:
                return [cand[-1]]
    if ctx == 22:
        pred_n = len(base)
        n = len(options)
        evo = next((h for h in reversed(history) if int(h.get('type', -1)) == 9 and int(h.get('source_id', 0) or 0) == GRIM), None)
        area = int((evo or {}).get('target_area', 0) or 0)
        idx = int((evo or {}).get('inplay_index', -1) or -1)
        arr = me.get('active') or [] if area == 4 else me.get('bench') or [] if area == 5 else []
        target = arr[idx] if 0 <= idx < len(arr) else {}
        target_en = int((target or {}).get('en', 0) or 0)
        if pred_n == 2 and n == 2 and (target_en == 1) and (tac >= 28):
            return [0]
        if pred_n == 3 and n == 6 and (tac >= 13) and (active_hp <= 70):
            return [0, 1]
        if pred_n == 3 and n == 6 and (discard_n == 4) and (hand[DARK] == 3):
            return [0, 1]
        if pred_n == 2 and n >= 5 and (active_hp == 100):
            return [0, 1, 2]
    return base
