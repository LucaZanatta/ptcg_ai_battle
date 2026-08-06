from __future__ import annotations
from collections import Counter, defaultdict
import sys
from pathlib import Path
if '__file__' in globals():_ROOT=Path(globals()['__file__']).resolve().parent
else:
 _roots=(Path('/kaggle_simulations/agent'),Path.cwd())
 _ROOT=next((r for r in _roots if (r/'base_impl.py').is_file()),Path.cwd())
if str(_ROOT) not in sys.path:sys.path.insert(0,str(_ROOT))
import base_impl, human_policy, council_policy, top_player_guard, foresight_overlay

def _read_fixed_deck():
 candidates=(_ROOT/'deck.csv',Path('/kaggle_simulations/agent/deck.csv'),Path.cwd()/'deck.csv')
 for path in candidates:
  try:
   values=[int(x) for x in path.read_text(encoding='utf-8').split()]
  except Exception:
   continue
  if len(values)==60:return values
 raise RuntimeError('The packaged deck.csv must contain exactly 60 card IDs.')

DECK=_read_fixed_deck()
EXPECTED_DECK=tuple(DECK)
if len(DECK)!=60:raise RuntimeError('Fixed deck length check failed.')
_SEEN=Counter();_PROFILE='unknown';_STYLE='unknown';_STYLE_TURNS=0
MIRROR_IDS={104,112,646,647,648,860};WALL_IDS={117,344,345,756};GRASS_IDS={25,96,1094,1127,1251};PURE_GRASS_SIGNATURES={1201,1223};TECH_GRASS_SIGNATURES={25,1081,1097,1116,1123,1152}

def _opponent_public_ids(obs):
 cur=(obs or {}).get('current') or {};ps=cur.get('players') or [];y=int(cur.get('yourIndex',0) or 0);opi=1-y;ids=[]
 if len(ps)>=2 and 0<=opi<len(ps):
  op=ps[opi] or {}
  for card in (op.get('active') or [])+(op.get('bench') or [])+(op.get('discard') or []):
   if isinstance(card,dict):ids.append(int(card.get('id',0) or 0))
 for log in (obs or {}).get('logs') or []:
  if not isinstance(log,dict):continue
  try:pl=int(log.get('playerIndex',-1))
  except Exception:pl=-1
  if pl!=opi:continue
  for key in ('cardId','cardIdTarget'):
   cid=int(log.get(key,0) or 0)
   if cid:ids.append(cid)
 return ids

def _profile(obs):
 global _PROFILE
 _SEEN.update(_opponent_public_ids(obs));seen=set(_SEEN)
 if len(seen&MIRROR_IDS)>=2:_PROFILE='mirror'
 elif seen&WALL_IDS:_PROFILE='wall'
 elif seen&TECH_GRASS_SIGNATURES:_PROFILE='grass_tech'
 elif seen&PURE_GRASS_SIGNATURES:_PROFILE='grass_pure'
 elif seen&GRASS_IDS:_PROFILE='grass_unknown'
 return _PROFILE

def _style(obs):
 global _STYLE,_STYLE_TURNS
 if _STYLE=='stable':return _STYLE
 seen=set(_SEEN)
 if 860 in seen:
  _STYLE='stable';return _STYLE
 cur=(obs or {}).get('current') or {};turn=int(cur.get('turn',0) or 0)
 if turn>_STYLE_TURNS:_STYLE_TURNS=turn
 mirror_seen=len(seen&(MIRROR_IDS-{860}))
 # Do not label an opponent from the opening board alone.  A top player waits
 # for enough public evidence to distinguish a slow setup from a true no-Snorunt plan.
 if _STYLE=='unknown' and _STYLE_TURNS>=3 and mirror_seen>=3:_STYLE='hybrid'
 return _STYLE

def _legal(obs,a):
 s=(obs or {}).get('select') or {};n=len(s.get('option') or []);mn=int(s.get('minCount',0) or 0);mx=int(s.get('maxCount',0) or 0)
 return isinstance(a,list) and mn<=len(a)<=mx and len(a)==len(set(a)) and all(isinstance(i,int) and 0<=i<n for i in a)

def _hybrid(obs,human,votes):
 if not _legal(obs,human):return council_policy.choose_votes(obs,votes)
 if not votes:return human
 council=council_policy.choose_votes(obs,votes);groups=defaultdict(list)
 for name,a in votes:groups[tuple(a)].append(name)
 groups[tuple(human)].append('human');m=max(len(v) for v in groups.values());winners=[a for a,v in groups.items() if len(v)==m]
 if tuple(human) in winners:return human
 if tuple(council) in winners:return council
 return list(winners[0])

def _is_deck_request(obs):
 if not isinstance(obs,dict) or not obs:return True
 current=obs.get('current')
 select=obs.get('select')
 return current is None or select is None or (not current and not select)

def agent(obs):
 global _SEEN,_PROFILE,_STYLE,_STYLE_TURNS
 if _is_deck_request(obs):
  _SEEN=Counter();_PROFILE='unknown';_STYLE='unknown';_STYLE_TURNS=0;base_impl._SPECIALIST_ON=False
  try:base_impl.agent(obs)
  except Exception:pass
  try:human_policy.reset_runtime_state()
  except Exception:pass
  try:council_policy.reset()
  except Exception:pass
  try:top_player_guard.reset()
  except Exception:pass
  try:foresight_overlay.reset()
  except Exception:pass
  return list(DECK)
 profile=_profile(obs);base_impl._SPECIALIST_ON=profile=='grass_pure';base_action=base_impl.agent(obs)
 try:human_action=list(human_policy.agent(obs))
 except Exception:human_action=[]
 try:votes=council_policy.collect_votes(obs)
 except Exception:votes=[]
 proposed=base_action
 try:
  profile2=top_player_guard.observe(obs)
  if profile=='unknown' and profile2!='unknown':profile=profile2
 except Exception:
  profile2=profile
 try:foresight_overlay.observe(obs,profile)
 except Exception:pass
 if profile=='mirror':
  try:
   out=council_policy.choose_votes(obs,votes)
   if _legal(obs,out):return out
  except Exception:pass
  if _legal(obs,human_action):return human_action
  return base_action
 if profile=='grass_pure':
  try:
   out=top_player_guard.choose(obs,base_action,profile)
   if not _legal(obs,out):out=base_action
   out2=foresight_overlay.choose(obs,out,profile)
   if _legal(obs,out2):return out2
   if _legal(obs,out):return out
  except Exception:pass
 return base_action

def get_stats():return {'profile':_PROFILE,'style':_STYLE,'seen':dict(_SEEN),'council':council_policy.get_stats(),'top_player':top_player_guard.stats()}
