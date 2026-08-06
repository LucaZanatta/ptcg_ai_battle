from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable
import json, math
from council_parts.v22 import main as _expert_a
from council_parts.rule_v24 import main as _expert_b
from council_parts.v26_reexport import main as _expert_c
from council_parts.handwritten_v26 import main as _expert_d
from council_parts.v28 import main as _expert_e
from council_parts.v32 import main as _expert_f

DECK=[int(x) for x in (Path(__file__).resolve().parent/'deck.csv').read_text().split()]
_W=json.loads((Path(__file__).resolve().parent/'context_weights.json').read_text())
_VOTERS:tuple[tuple[str,Callable[[dict],list[int]]],...]=(
 ('v22',_expert_a.agent),('rule_v24',_expert_b.agent),('v26_reexport',_expert_c.agent),
 ('handwritten_v26',_expert_d.agent),('v28',_expert_e.agent),('v32',_expert_f.agent),)
_STATS:Counter[str]=Counter()

def _legal(obs,action):
 s=(obs or {}).get('select') or {};n=len(s.get('option') or []);mn=int(s.get('minCount',0) or 0);mx=int(s.get('maxCount',0) or 0)
 return isinstance(action,list) and mn<=len(action)<=mx and len(action)==len(set(action)) and all(isinstance(i,int) and 0<=i<n for i in action)

def _fallback(obs):
 s=(obs or {}).get('select') or {};n=len(s.get('option') or []);mn=int(s.get('minCount',0) or 0);mx=min(int(s.get('maxCount',0) or 0),n)
 return list(range(min(max(mn,mx),n)))

def _rate(pair,prior,alpha):
 c,n=pair;return (float(c)+alpha*prior)/(float(n)+alpha)

def reset():
 _STATS.clear()
 for _,fn in _VOTERS:
  try:fn({})
  except Exception:pass

def get_stats():return dict(_STATS)

def collect_votes(obs):
 if not obs or obs.get('select') is None:reset();return []
 votes=[]
 for name,fn in _VOTERS:
  try:a=list(fn(obs))
  except Exception:_STATS[name+'_exception']+=1;continue
  if _legal(obs,a):votes.append((name,a))
  else:_STATS[name+'_illegal']+=1
 return votes

def vote_summary(obs,votes):
 grouped=defaultdict(list)
 for name,a in votes:grouped[tuple(a)].append(name)
 context=str(int(((obs or {}).get('select') or {}).get('context',-1) or -1));family=_W['family_by_context'].get(context,'other')
 return grouped,context,family,max((len(x) for x in grouped.values()),default=0)

def choose_votes(obs,votes):
 if not votes:return _fallback(obs)
 grouped,context,family,max_support=vote_summary(obs,votes)
 majority=[a for a,s in grouped.items() if len(s)==max_support]
 if max_support>=4 and len(majority)==1:return list(majority[0])
 sm=_W['smoothing'];scores={}
 for action,supporters in grouped.items():
  key='|'.join(sorted(supporters));gr=[_rate(_W['global_agent'][a],.5,sm['agent_global']) for a in supporters];fallback=sum(gr)/len(gr)
  base=_rate(_W['global_coalition'].get(key,[0,0]),fallback,sm['coalition_global'])
  p=_rate(_W['family_coalition'].get(f'{family}::{key}',[0,0]),base,sm['coalition_family']);p=min(.99999,max(.00001,p))
  scores[action]=math.log(p/(1-p))+sm['support_bonus']*len(supporters)
 best=max(scores.values());winners={a for a,v in scores.items() if abs(v-best)<1e-12}
 if len(winners)==1:return list(next(iter(winners)))
 chosen=None;bestp=-1.0
 for name,a in votes:
  ta=tuple(a)
  if ta not in winners:continue
  gp=_rate(_W['global_agent'][name],.5,sm['agent_global']);fp=_rate(_W['family_agent'].get(family,{}).get(name,[0,0]),gp,sm['tie_agent_family'])
  if fp>bestp:bestp=fp;chosen=ta
 return list(chosen if chosen is not None else next(iter(winners)))

def agent(obs):
 if not obs or obs.get('select') is None:reset();return list(DECK)
 return choose_votes(obs,collect_votes(obs))
