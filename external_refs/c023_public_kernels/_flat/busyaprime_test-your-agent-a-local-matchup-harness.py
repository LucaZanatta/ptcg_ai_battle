import glob, os, sys, importlib, types
def find_dir(pats, must):
    for p in pats:
        for d in glob.glob(p, recursive=True):
            if os.path.isdir(d) and os.path.exists(os.path.join(d, must)):
                return d
    return None
SAMPLE = find_dir(["/kaggle/input/**/sample_submission/**", "/kaggle/input/**/sample_submission"], "main.py")
CG = find_dir(["/kaggle/input/**/sample_submission/**/cg", "/kaggle/input/**/cg"], "api.py")
sys.path.insert(0, os.path.dirname(CG))
from cg.api import to_observation_class, all_card_data, all_attack
from cg.game import battle_start, battle_select, battle_finish
SAMPLE_DECK = [int(x) for x in open(os.path.join(SAMPLE, "deck.csv")).read().splitlines() if x.strip()]
print("engine ready, sample deck has", len(SAMPLE_DECK), "cards")

#%%CELL%%

def play(agent_a, deck_a, agent_b, deck_b, a_first=True):
    d0, d1 = (deck_a, deck_b) if a_first else (deck_b, deck_a)
    obs, start = battle_start(d0, d1)
    if obs is None:
        return {"outcome": "deck_rejected", "errorType": getattr(start, "errorType", None)}
    a_seat = 0 if a_first else 1
    try:
        steps = 0
        while obs["current"]["result"] < 0 and steps < 100000:
            seat = obs["current"]["yourIndex"]
            move = (agent_a if seat == a_seat else agent_b)(obs)
            obs = battle_select(move)
            steps += 1
        res = obs["current"]["result"]        # -1 ongoing, 0 or 1 winner seat, 2 draw
        return {"outcome": "done", "a_win": res == a_seat, "draw": res == 2, "turns": obs["current"]["turn"]}
    except Exception as e:
        return {"outcome": "error", "error": type(e).__name__}     # an illegal index throws, and that loses
    finally:
        battle_finish()

def matchup(agent_a, deck_a, agent_b, deck_b, n=60):
    wins = draws = errors = done = 0; turns = []
    for g in range(n):
        r = play(agent_a, deck_a, agent_b, deck_b, a_first=(g % 2 == 0))
        if r["outcome"] != "done":
            errors += 1; continue
        done += 1; turns.append(r["turns"])
        draws += r["draw"]; wins += (r["a_win"] and not r["draw"])
    return {"games": done, "win_rate": round(wins / max(1, done), 3), "draws": draws,
            "errors": errors, "avg_turns": round(sum(turns) / max(1, len(turns)), 1)}
print("harness ready")

#%%CELL%%

_C = {c.cardId: c for c in all_card_data()}
_A = {a.attackId: a for a in all_attack()}
PLAY, ATTACH, EVOLVE, ABILITY, DISCARD, RETREAT, ATTACK, END, SKILL, NUMBER = 7, 8, 9, 10, 11, 12, 13, 14, 15, 0
MAIN, ACTIVE = 0, 4

def _damage(attack_id, attacker, defender):
    a = _A.get(attack_id)
    if a is None:
        return 0
    d = a.damage or 0
    if attacker is not None and defender is not None:
        atype = getattr(_C.get(attacker.id), "energyType", None)
        weak = getattr(_C.get(defender.id), "weakness", None)
        res = getattr(_C.get(defender.id), "resistance", None)
        if atype is not None and weak is not None and int(weak) == int(atype):
            d *= 2
        elif atype is not None and res is not None and int(res) == int(atype):
            d = max(0, d - 30)
    return d

def make_baseline(deck):
    def agent(obs_dict):
        obs = to_observation_class(obs_dict)
        sel = obs.select
        if sel is None:
            return deck
        opts = sel.option; n = len(opts)
        lo = int(getattr(sel, "minCount", 1) or 0); hi = int(getattr(sel, "maxCount", 1) or 1)
        try:
            if int(sel.type) == MAIN:
                st = obs.current
                me = st.players[st.yourIndex]; opp = st.players[1 - st.yourIndex]
                my_active = me.active[0] if me.active and me.active[0] else None
                opp_active = opp.active[0] if opp.active and opp.active[0] else None
                scores = []
                for op in opts:
                    t = int(op.type)
                    if t == ATTACK:
                        dmg = _damage(op.attackId, my_active, opp_active)
                        s = (1000 + dmg) if (opp_active is not None and dmg >= (opp_active.hp or 9999)) else 30 + min(dmg, 250) / 10.0
                    elif t == ABILITY: s = 62
                    elif t == EVOLVE: s = 58 if (op.inPlayArea is not None and int(op.inPlayArea) == ACTIVE) else 55
                    elif t == ATTACH: s = 52 if (op.inPlayArea is not None and int(op.inPlayArea) == ACTIVE) else 46
                    elif t == PLAY: s = 40
                    elif t == SKILL: s = 25
                    elif t == RETREAT: s = 8
                    elif t == DISCARD: s = 4
                    elif t == END: s = 0
                    else: s = 20
                    scores.append(s)
                return [max(range(n), key=lambda i: scores[i])]
            if n and all(int(o.type) == NUMBER for o in opts):
                vals = [(o.number if o.number is not None else 0) for o in opts]
                k = min(max(lo, 1), hi, n)
                return sorted(sorted(range(n), key=lambda i: -vals[i])[:k])
            k = min(max(lo, 1), hi, n) if hi >= 1 else 0
            return list(range(k))
        except Exception:
            k = min(max(lo, 1), hi, n) if (n and hi >= 1) else 0
            return list(range(k)) if k else ([0] if n else [])
    return agent
print("baseline ready")

#%%CELL%%

sys.path.insert(0, SAMPLE)
random_sample = importlib.import_module("main").agent    # the official random sample agent
baseline = make_baseline(SAMPLE_DECK)

print("baseline vs the random sample :", matchup(baseline, SAMPLE_DECK, random_sample, SAMPLE_DECK, n=60))
print("baseline vs a mirror of itself:", matchup(baseline, SAMPLE_DECK, make_baseline(SAMPLE_DECK), SAMPLE_DECK, n=30))