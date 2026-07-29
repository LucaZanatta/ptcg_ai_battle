"""Is the root choice separated from its alternatives, or picked out of rollout noise?"""
import sys, math, statistics; sys.path.insert(0,'/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from kaggle_environments import make
from cg import teachers as T, c009_eval as ce, c019_determinize as D19
from cg import c021_mcgs_agent as AG
deck = D19.archetype_decks()['mega_lucario']
cfg = {'first_move_seconds':0.9,'continuing_move_seconds':0.7,'match_clock_seconds':60}
ag = AG.MCGSAgent(deck, cfg, seed=7)
env = make('cabt'); env.run([lambda o: ag.act(o), lambda o: T.make_fresh('dragapult', ce.SOURCES)(o)])

rows = [d for d in ag.decisions_log if len(d.get('values') or []) > 1]
print(f"decisions with >1 root edge: {len(rows)}")
sep = 0; noisy = 0
for d in rows:
    vals = sorted(d['values'], reverse=True); vis = d['visits']
    best, med = vals[0], statistics.median(vals)
    n = max(1, d.get('chosen_visits') or 1)
    p = min(max(best, 0.0), 1.0)
    se = math.sqrt(max(p*(1-p), 1e-9)/n)          # rollout noise at the chosen edge's visits
    gap = best - med
    if gap > 2*se: sep += 1
    else: noisy += 1
print(f"  chosen edge separated from median by >2 rollout-SE : {sep}")
print(f"  inside noise                                       : {noisy}")
if rows:
    ex = rows[len(rows)//2]
    v = sorted(ex['values'], reverse=True)
    print(f"  example: sims={ex.get('simulations')} edges={ex.get('edges')} "
          f"chosen_visits={ex.get('chosen_visits')}")
    print(f"           top values {[round(x,4) for x in v[:6]]}")
