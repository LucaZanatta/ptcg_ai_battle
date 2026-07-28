"""Direct check: at a manual-coin context, are BOTH options reachable and do they differ?
A confounded set-difference over two walks cannot answer this; stepping both options from the
identical state can."""
import sys, collections, json
sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import api as A, c019_core as K, c020_determinize as DT, c019_determinize as D19
from cg import c021_mcgs_abstraction as AB
import numpy as np
deck = D19.archetype_decks()["mega_lucario"]
captured=[]
class Probe:
    def __call__(self, obs):
        sel = obs.get("select")
        if sel is None: return list(deck)
        opts = K.canonical_options(sel)
        if len(captured) < 2 and len(opts) > 1: captured.append(dict(obs))
        return K.to_select_payload([opts[0]], sel)
from cg import teachers as T, c009_eval as ce
env = make("cabt"); env.run([lambda o: Probe()(o), lambda o: T.make_fresh("dragapult", ce.SOURCES)(o)])
o = A.to_observation_class(captured[0]); view = K.visible_view(o)
det,_ = DT.determinize(view, deck, np.random.default_rng(7))

def pay(sel, opt, opts):
    lo = max(1, int(getattr(sel,'minCount',1) or 1))
    ch=[opt]
    if lo>1: ch.extend([x for x in opts if x.key()!=opt.key()][:lo-1])
    return K.to_select_payload(ch, sel)

TARGET = {4,5,46}
found = {}          # ctx -> (sid, obs)
for seed in range(40):
    if set(found) >= TARGET: break
    r = np.random.default_rng(1000+seed)
    st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck, det.opponent_prize,
                        det.opponent_hand, det.opponent_active, manual_coin=True)
    sid, ob = st.searchId, st.observation
    for i in range(400):
        s = getattr(ob,'select',None)
        if s is None: break
        op = K.canonical_options(s)
        if not op: break
        c = int(getattr(s,'context',-1) or -1)
        if c in TARGET and c not in found:
            # step EVERY option from THIS EXACT state
            res=[]
            for oi,opt in enumerate(op):
                try:
                    nx = A.search_step(sid, pay(s, opt, op))
                    h = hash(AB.StateAbstraction(nx.observation, None, None, True)) if nx.observation is not None else None
                    res.append((oi, int(getattr(opt,'option_type',-1) or -1), h))
                except Exception as e:
                    res.append((oi, int(getattr(opt,'option_type',-1) or -1), f"ERR:{type(e).__name__}"))
            hs = [x[2] for x in res if isinstance(x[2], int)]
            found[c] = {"n_options": len(op), "minCount": int(getattr(s,'minCount',0) or 0),
                        "maxCount": int(getattr(s,'maxCount',0) or 0),
                        "option_types": [x[1] for x in res],
                        "distinct_successors": len(set(hs)), "reachable": len(hs)}
        try: nx = A.search_step(sid, pay(s, op[int(r.integers(len(op)))], op))
        except Exception: break
        sid, ob = nx.searchId, nx.observation
    A.search_end()
print(json.dumps(found, indent=2))
