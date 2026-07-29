"""The hidden-information guarantee, tested with the REAL accessor names on a MID-GAME state.

DECISION_RULES forbids submitting an oracle-information candidate. Every c021 encoder and
abstraction reads through visible_view, so if these do not raise, the whole campaign is one.
"""
import sys; sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import api as A, c019_core as K, c019_determinize as D19, teachers as T, c009_eval as ce
deck=D19.archetype_decks()['mega_lucario']
cap=[]
class P:
    def __call__(s,obs):
        sel=obs.get('select')
        if sel is None: return list(deck)
        o=K.canonical_options(sel)
        if not o: return [0]
        v=K.visible_view(A.to_observation_class(obs))
        c=v.counts()
        if c['my_hand']>2 and c['opp_hand']>2 and len(cap)<1: cap.append(dict(obs))
        return K.to_select_payload([o[0]],sel)
env=make('cabt'); env.run([lambda o: P()(o), lambda o: T.make_fresh('dragapult', ce.SOURCES)(o)])
if not cap: print("no mid-game capture"); sys.exit()
v=K.visible_view(A.to_observation_class(cap[0]))
print("mid-game counts:", {k: v.counts()[k] for k in ('my_hand','opp_hand','my_deck','opp_deck','my_prize')})
forbidden=[("opponent_hand_contents", lambda: v.opponent_hand_contents()),
           ("deck_contents('mine')",  lambda: v.deck_contents('mine')),
           ("deck_contents('theirs')",lambda: v.deck_contents('theirs')),
           ("prize_contents('mine')", lambda: v.prize_contents('mine')),
           ("prize_contents('theirs')",lambda: v.prize_contents('theirs'))]
leaks=0
for name, fn in forbidden:
    try:
        r=fn(); leaks+=1; print(f"  {name:26s} -> RETURNED {str(r)[:40]}  *** LEAK ***")
    except K.HiddenInformationAccess:
        print(f"  {name:26s} -> HiddenInformationAccess  OK")
print(f"  leaks: {leaks}")
allowed=[("my_hand", lambda: len(v.my_hand())),
         ("discard('mine')", lambda: len(v.discard('mine'))),
         ("discard('theirs')", lambda: len(v.discard('theirs'))),
         ("board('theirs')", lambda: len(v.board('theirs').get('bench') or []))]
print("  allowed reads:")
for name, fn in allowed:
    try: print(f"    {name:20s} -> {fn()}")
    except Exception as e: print(f"    {name:20s} -> raised {type(e).__name__}  *** OVER-BLOCKED ***")
