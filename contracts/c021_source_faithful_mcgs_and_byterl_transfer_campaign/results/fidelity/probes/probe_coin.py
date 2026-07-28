import sys, collections
sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import api as A, c019_core as K, c020_determinize as DT, c019_determinize as D19
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
o = A.to_observation_class(captured[0]); view = K.visible_view(o)
det,_ = DT.determinize(view, deck, rng)
sel0 = getattr(o,'select',None); opts0 = K.canonical_options(sel0)

def pay(sel, opt, opts):
    lo = max(1, int(getattr(sel,'minCount',1) or 1))
    ch=[opt]
    if lo>1: ch.extend([x for x in opts if x.key()!=opt.key()][:lo-1])
    return K.to_select_payload(ch, sel)

def walk(manual, seed, nsteps=400):
    r = np.random.default_rng(seed)
    st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck, det.opponent_prize,
                        det.opponent_hand, det.opponent_active, manual_coin=manual)
    sid, ob = st.searchId, st.observation
    ctx = collections.Counter(); samples={}
    for i in range(nsteps):
        s = getattr(ob,'select',None)
        if s is None: break
        op = K.canonical_options(s)
        if not op: break
        c = int(getattr(s,'context',-1) or -1)
        ctx[c]+=1
        if c not in samples:
            samples[c] = (len(op), [ (getattr(x,'option_type',None), getattr(x,'referenced_card_id',None)) for x in op[:4] ],
                          int(getattr(s,'minCount',0) or 0), int(getattr(s,'maxCount',0) or 0))
        try: nx = A.search_step(sid, pay(s, op[int(r.integers(len(op)))], op))
        except Exception as e: break
        sid, ob = nx.searchId, nx.observation
    A.search_end()
    return ctx, samples

cF, sF = walk(False, 11)
cT, sT = walk(True, 11)
print("contexts WITHOUT manual_coin:", sorted(cF))
print("contexts WITH    manual_coin:", sorted(cT))
extra = sorted(set(cT) - set(cF))
print("CONTEXTS ONLY WITH manual_coin:", extra)
for c in extra: print("   ctx", c, "-> nopts,opt(type,cardid),min,max =", sT[c])
