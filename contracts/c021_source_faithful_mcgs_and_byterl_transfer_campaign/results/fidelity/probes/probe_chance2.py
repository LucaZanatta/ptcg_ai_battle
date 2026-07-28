import sys, collections
sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import api as A, c019_core as K, c020_determinize as DT, c019_determinize as D19
from cg import c021_mcgs_abstraction as AB
import numpy as np
deck = D19.archetype_decks()["mega_lucario"]
rng = np.random.default_rng(7)
captured=[]
class Probe:
    def __call__(self, obs):
        sel = obs.get("select")
        if sel is None: return list(deck)
        opts = K.canonical_options(sel)
        if len(captured) < 3 and len(opts) > 1: captured.append(dict(obs))
        return K.to_select_payload([opts[0]], sel)
from cg import teachers as T, c009_eval as ce
env = make("cabt"); env.run([lambda o: Probe()(o), lambda o: T.make_fresh("dragapult", ce.SOURCES)(o)])

o = A.to_observation_class(captured[0])
view = K.visible_view(o); det,_ = DT.determinize(view, deck, rng)

# Q1: does an INTERIOR observation carry search_begin_input?
st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck, det.opponent_prize,
                    det.opponent_hand, det.opponent_active)
sel = getattr(o,'select',None); opts = K.canonical_options(sel)
succ = A.search_step(st.searchId, K.to_select_payload([opts[0]], sel))
print("root  obs.search_begin_input is None:", getattr(o,'search_begin_input',None) is None)
print("interior obs.search_begin_input is None:", getattr(succ.observation,'search_begin_input',None) is None)
A.search_end()

# Q2: does re-begin with a DIFFERENT determinization give different successors?
hs = collections.Counter()
for t in range(8):
    d2,_ = DT.determinize(view, deck, np.random.default_rng(100+t))
    s2 = A.search_begin(o, d2.your_deck, d2.your_prize, d2.opponent_deck, d2.opponent_prize,
                        d2.opponent_hand, d2.opponent_active)
    sc = A.search_step(s2.searchId, K.to_select_payload([opts[0]], sel))
    hs[hash(AB.StateAbstraction(sc.observation, None, None, True))] += 1
    A.search_end()
print("re-begin w/ fresh determinization ->", len(hs), "distinct of 8:", list(hs.values()))

# Q3: manual_coin -- does it surface coin flips as selectable options?
s3 = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck, det.opponent_prize,
                    det.opponent_hand, det.opponent_active, manual_coin=True)
seen=collections.Counter(); sid=s3.searchId; ob=s3.observation
for step in range(160):
    s = getattr(ob,'select',None)
    if s is None: break
    op = K.canonical_options(s)
    if not op: break
    seen[(int(getattr(s,'selectType',-1) or -1), int(getattr(s,'context',-1) or -1))]+=1
    try: nx = A.search_step(sid, K.to_select_payload([op[int(rng.integers(len(op)))]], s))
    except Exception as e: print("  step err", e); break
    sid = nx.searchId; ob = nx.observation
print("manual_coin select (selectType,context) histogram:", dict(seen))
A.search_end()
