"""Does stepping the SAME action from the SAME state twice give different successors?
That is the engine-level property a chance node samples over."""
import sys, collections
sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import api as A, c019_core as K, c020_determinize as DT, c019_determinize as D19
from cg import c021_mcgs_abstraction as AB
import numpy as np

deck = D19.archetype_decks()["mega_lucario"]
rng = np.random.default_rng(7)
captured = []
class Probe:
    def __call__(self, obs):
        sel = obs.get("select")
        if sel is None: return list(deck)
        opts = K.canonical_options(sel)
        if len(captured) < 6 and len(opts) > 1:
            captured.append(dict(obs))
        return K.to_select_payload([opts[0]], sel)
from cg import teachers as T, c009_eval as ce
env = make("cabt")
env.run([lambda o: Probe()(o), lambda o: T.make_fresh("dragapult", ce.SOURCES)(o)])
print("captured", len(captured))

for ci, od in enumerate(captured[:4]):
    o = A.to_observation_class(od)
    view = K.visible_view(o)
    det,_ = DT.determinize(view, deck, rng)
    st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck,
                        det.opponent_prize, det.opponent_hand, det.opponent_active)
    sel = getattr(o,'select',None)
    opts = K.canonical_options(sel)
    # step the SAME action index 12 times from the SAME parent state
    for oi in range(min(3, len(opts))):
        payload = K.to_select_payload([opts[oi]], sel)
        hashes = collections.Counter()
        for t in range(12):
            try:
                succ = A.search_step(st.searchId, payload)
            except Exception as e:
                print("  step err", e); break
            so = succ.observation
            if so is None: hashes['NONE']+=1; continue
            hashes[hash(AB.StateAbstraction(so, None, None, True))] += 1
            A.search_release(succ.searchId)
        print(f"capture{ci} opt{oi} otype={getattr(opts[oi],'option_type',None)} -> {len(hashes)} distinct successors out of 12 : {list(hashes.values())}")
    A.search_release(st.searchId)
    A.search_end()
