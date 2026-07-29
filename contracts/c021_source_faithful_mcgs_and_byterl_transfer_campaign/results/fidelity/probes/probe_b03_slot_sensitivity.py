"""B03: does a change to ONE board slot move only that slot's token?

Marked PASS from architecture rather than measurement. If a change to my bench leaks into the
opponent's tokens -- or into every token -- the slot embeddings are decorative.
"""
import sys, copy; sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
import numpy as np
from kaggle_environments import make
from cg import api as A, c019_core as K, c019_determinize as D19, teachers as T, c009_eval as ce
from cg import c021_byterl_encode as EN
deck=D19.archetype_decks()['mega_lucario']
cap=[]
class P:
    def __call__(s,obs):
        sel=obs.get('select')
        if sel is None: return list(deck)
        o=K.canonical_options(sel)
        if not o: return [0]
        if len(cap)<1:
            v=K.visible_view(A.to_observation_class(obs))
            b=v.board('mine')
            if (b.get('bench') or []) and b.get('active'): cap.append(copy.deepcopy(dict(obs)))
        return K.to_select_payload([o[0]],sel)
env=make('cabt'); env.run([lambda o: P()(o), lambda o: T.make_fresh('dragapult', ce.SOURCES)(o)])
if not cap: print("no capture with an occupied bench"); sys.exit()
base = EN.encode_battle(A.to_observation_class(cap[0]), None, None)['board']
print(f"board tensor: {base.shape} (12 slots x {base.shape[1]} features)")

def perturb(d, path, val):
    o = copy.deepcopy(d); cur = o
    for k in path[:-1]: cur = cur[k]
    cur[path[-1]] = val
    return EN.encode_battle(A.to_observation_class(o), None, None)['board']

st = cap[0]['current']; yi = st['yourIndex']
me = st['players'][yi]
tests = []
if me.get('active'):
    tests.append(("my ACTIVE hp", ['current','players',yi,'active',0,'hp'],
                  (me['active'][0].get('hp') or 0) - 30, 0))
if me.get('bench'):
    tests.append(("my BENCH[0] hp", ['current','players',yi,'bench',0,'hp'],
                  (me['bench'][0].get('hp') or 0) - 30, 1))
opp = st['players'][1-yi]
if opp.get('active'):
    tests.append(("opp ACTIVE hp", ['current','players',1-yi,'active',0,'hp'],
                  (opp['active'][0].get('hp') or 0) - 30, 6))
for name, path, val, expect in tests:
    try: new = perturb(cap[0], path, val)
    except Exception as e:
        print(f"  {name:22s} -> could not perturb ({type(e).__name__})"); continue
    moved = sorted(np.where(np.abs(new-base).sum(1) > 1e-9)[0].tolist())
    ok = moved == [expect]
    print(f"  {name:22s} -> slots changed {moved}  expected [{expect}]  {'OK' if ok else '*** LEAK ***'}")
