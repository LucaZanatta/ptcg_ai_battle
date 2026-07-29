import sys; sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from cg import c021_byterl_actor as AC, c021_byterl_deck as DK, c021_byterl_model as M, c021_byterl_encode as EN
pool = DK.CardPool.from_archetypes(); d = EN.dims()
net = M.fresh(d['global_dim'], d['slot_dim'], d['option_dim'], pool.size(), width=32, blocks=1, seed=0)
a = AC.ByteRLActor(net, pool, seed=1, fixed_deck=DK.greedy_reference_deck(pool))
# make every policy evaluation raise, exactly as a broken network would
def boom(*args, **kw): raise RuntimeError("injected policy failure")
a.net.encode = boom
sel = {"selectType": 0, "context": 0, "minCount": 1, "maxCount": 1,
       "option": [{"optionType": 7, "area": 2, "index": 0}, {"optionType": 14}]}
for _ in range(25):
    a.act({"select": sel})
ep = a.finish(0.0, True, {})
print("n_errors        :", ep.info["n_errors"])
print("n_decisions     :", ep.info["n_decisions"])
print("battle_steps    :", ep.battle_steps(), "(0 = nothing was recorded, so the rate is 1.0)")
rate = ep.info["n_errors"] / max(1, ep.info["n_decisions"])
print("actor_error_rate:", round(rate, 4))
assert ep.info["n_errors"] == 25, ep.info["n_errors"]
assert rate == 1.0
print("DETECTED: a fully-broken policy now reports rate 1.0 instead of a silent 0")
