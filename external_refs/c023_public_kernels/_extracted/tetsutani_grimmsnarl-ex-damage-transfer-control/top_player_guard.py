from __future__ import annotations
from collections import Counter

# Fixed-deck domain constants.
DARK=7; FROSLASS=104; MUNKIDORI=112; IMPIDIMP=646; MORGREM=647; GRIMMSNARL=648; SNORUNT=860
RARE_CANDY=1079; UNFAIR_STAMP=1080; POFFIN=1086; NIGHT_STRETCHER=1097; POKEGEAR=1122
TOOL_SCRAPPER=1137; POKE_PAD=1152; BOSS=1182; PETREL=1219; LILLIE=1227; DAWN=1231; SPIKEMUTH=1259
CORKSCREW_IMPIDIMP=935; CORKSCREW_MORGREM=936; SHADOW_BULLET=937
TERA_IDS={37,75,80,96,99,108,117,121,150,153,154,161,176,189,193,210,223,229,231,232,236,239,241,243,244,246,248,249,269,272,283,293,299,302,306,313,316,320,326,328,329,331,336,337,340,357,369,372,381,389,404,407,424,431,447,455,458,471,481,509,515,525,527,547,561,573,583,598,618,631,641,648}
MIRROR_IDS={104,112,646,647,648,860}
WALL_IDS={117,344,345,756}
GRASS_CORE={96,1127,1094,1118,1119,1251}
GRASS_TECH={25,1081,1097,1116,1123,1152}
GRASS_PURE={1201,1223}

_SEEN=Counter(); _LAST_TURN=-1; _PENDING=0; _PENDING_ATTACK=0; _LAST_STEP=None
_STATS=Counter()

def reset():
 global _SEEN,_LAST_TURN,_PENDING,_PENDING_ATTACK,_LAST_STEP
 _SEEN=Counter();_LAST_TURN=-1;_PENDING=0;_PENDING_ATTACK=0;_LAST_STEP=None;_STATS.clear()

def stats(): return dict(_STATS)

def cid(x): return int(x.get('id',0) or 0) if isinstance(x,dict) else 0
def any_cid(x):
 try:
  return int(x.get('id',0) or 0) if isinstance(x,dict) else int(x or 0)
 except Exception:
  return 0

def _players(obs):
 cur=(obs or {}).get('current') or {}; ps=cur.get('players') or [{},{}]; y=int(cur.get('yourIndex',0) or 0)
 if not (0<=y<len(ps)): y=0
 me=ps[y] if y<len(ps) else {}; op=ps[1-y] if len(ps)>1 else {}
 return cur,me,op,y

def _zone(p,area): return {2:p.get('hand') or [],3:p.get('discard') or [],4:p.get('active') or [],5:p.get('bench') or [],6:p.get('prize') or []}.get(int(area or 0),[])

def _source(obs,opt):
 cur,me,op,y=_players(obs); sel=(obs or {}).get('select') or {}; area=opt.get('area'); idx=opt.get('index'); pidx=opt.get('playerIndex',y)
 try:pidx=int(pidx)
 except:pidx=y
 p=me if pidx==y else op
 arr=[]
 if area==1: arr=sel.get('deck') or []
 elif area in (2,3,4,5,6): arr=_zone(p,area)
 elif isinstance(idx,int): arr=me.get('hand') or []
 return arr[idx] if isinstance(idx,int) and 0<=idx<len(arr) else None

def _target(obs,opt):
 cur,me,op,y=_players(obs); area=opt.get('inPlayArea'); idx=opt.get('inPlayIndex'); pidx=opt.get('playerIndex',y)
 if area is None and int(opt.get('type',-1) or -1)==10: area=opt.get('area');idx=opt.get('index')
 try:pidx=int(pidx)
 except:pidx=y
 p=me if pidx==y else op; arr=_zone(p,area)
 return arr[idx] if isinstance(idx,int) and 0<=idx<len(arr) else None

def _all_ids(p):
 out=[]
 for z in ('active','bench','discard'):
  out += [cid(c) for c in p.get(z) or []]
 return out

def observe(obs):
 global _LAST_STEP,_LAST_TURN
 if not obs or obs.get('select') is None: reset(); return 'unknown'
 cur,me,op,y=_players(obs); key=(int(cur.get('turn',0) or 0),int(cur.get('turnActionCount',0) or 0),y,len((obs.get('logs') or [])))
 if key!=_LAST_STEP:
  _LAST_STEP=key
  _SEEN.update(i for i in _all_ids(op) if i)
  for log in obs.get('logs') or []:
   if not isinstance(log,dict):continue
   try:pi=int(log.get('playerIndex',-1))
   except:pi=-1
   if pi==1-y:
    for k in ('cardId','cardIdTarget'):
     try:i=int(log.get(k,0) or 0)
     except:i=0
     if i:_SEEN[i]+=1
 _LAST_TURN=max(_LAST_TURN,int(cur.get('turn',0) or 0))
 s=set(_SEEN)
 if len(s&MIRROR_IDS)>=2:return 'mirror'
 if s&WALL_IDS:return 'wall'
 if s&GRASS_CORE:
  if s&GRASS_TECH:return 'grass_tech'
  if s&GRASS_PURE:return 'grass_pure'
  return 'grass_unknown'
 return 'unknown'

def legal(obs,a):
 s=(obs or {}).get('select') or {}; n=len(s.get('option') or []); mn=int(s.get('minCount',0) or 0); mx=int(s.get('maxCount',0) or 0)
 return isinstance(a,list) and mn<=len(a)<=mx and len(a)==len(set(a)) and all(isinstance(i,int) and 0<=i<n for i in a)

def _inplay(me,c): return sum(cid(x)==c for x in (me.get('active') or [])+(me.get('bench') or []))
def _inhand(me,c): return sum(cid(x)==c for x in me.get('hand') or [])
def _dam(card): return max(0,int(card.get('maxHp',0) or 0)-int(card.get('hp',0) or 0)) if isinstance(card,dict) else 0
def _en(card): return len(card.get('energyCards') or []) if isinstance(card,dict) else 0
def _remaining(card): return int(card.get('hp',0) or 0) if isinstance(card,dict) else 9999

def _has_dark_in_hand(me): return any(cid(c)==DARK for c in me.get('hand') or [])
def _has_in_hand(me,c): return any(cid(x)==c for x in me.get('hand') or [])

def _opt_type(o):
 try:return int(o.get('type',-1))
 except:return -1

def _main_candidates(obs):
 opts=((obs or {}).get('select') or {}).get('option') or []
 return [(i,o,_opt_type(o),cid(_source(obs,o)),cid(_target(obs,o))) for i,o in enumerate(opts)]

def _has_grimmsnarl_evolve(obs):
 return _best_grimmsnarl_evolve(obs) is not None

def _eligible_inplay(me,cid_):
 for c in (me.get('active') or [])+(me.get('bench') or []):
  if cid(c)==cid_ and not bool(c.get('appearThisTurn')):return True
 return False

def _main_play(obs,cid_):
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==7 and sid==cid_:return [i]
 return None

def _main_ability(obs,cid_):
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==10 and sid==cid_:return [i]
 return None

def _rare_candy_turn_plan(obs,profile):
 if not profile.startswith('grass'):return None
 cur,me,op,y=_players(obs)
 if not _eligible_inplay(me,IMPIDIMP):return None
 grim=_inhand(me,GRIMMSNARL)>0;candy=_inhand(me,RARE_CANDY)>0
 if grim and candy:
  a=_main_play(obs,RARE_CANDY)
  if a:return a
 if grim and not candy and _inhand(me,PETREL)>0:
  a=_main_play(obs,PETREL)
  if a:return a
 if candy and not grim:
  a=_main_ability(obs,SPIKEMUTH)
  if a:return a
 return None

def _best_needed_basic_play(obs,profile):
 cur,me,op,y=_players(obs);bench_free=max(0,5-len(me.get('bench') or []))
 if bench_free<=0:return None
 inp=Counter(cid(x) for x in (me.get('active') or [])+(me.get('bench') or []))
 target=None
 if profile.startswith('grass'):
  mline=inp[IMPIDIMP]+inp[MORGREM]+inp[GRIMMSNARL]
  fline=inp[SNORUNT]+inp[FROSLASS]
  if mline<2:target=IMPIDIMP
  elif fline<1:target=SNORUNT
  elif inp[MUNKIDORI]<1:target=MUNKIDORI
  # Ogerpon is a three-KO prize race.  Preserve a third attacker line before
  # spending the final Bench slot on a duplicate engine Pokemon.
  elif profile=='grass_pure' and mline<3:target=IMPIDIMP
  elif fline<2:target=SNORUNT
 elif profile=='wall':
  if inp[IMPIDIMP]+inp[MORGREM]<2:target=IMPIDIMP
  elif inp[SNORUNT]+inp[FROSLASS]<2:target=SNORUNT
  elif inp[MUNKIDORI]<3:target=MUNKIDORI
 if target is None:return None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==7 and sid==target:return [i]
 return None

def _best_munkidori_ability(obs):
 cur,me,op,y=_players(obs)
 if not any(_dam(c)>0 for c in (me.get('active') or [])+(me.get('bench') or [])):return None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==10 and sid==MUNKIDORI:return [i]
 return None

def _prepunk_munkidori(obs,profile):
 if not profile.startswith('grass') and profile!='wall':return None
 cur,me,op,y=_players(obs)
 if not _has_grimmsnarl_evolve(obs):return None
 if any(cid(c)==MUNKIDORI and _en(c)>0 for c in (me.get('active') or [])+(me.get('bench') or [])):return None
 if len(me.get('bench') or [])>=5:return None
 has_dark=_inhand(me,DARK)>0
 if not has_dark:return None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==7 and sid==MUNKIDORI:return [i]
 return None

def _best_morgrem_evolve(obs):
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=9 or sid!=MORGREM or tid!=IMPIDIMP:continue
  tgt=_target(obs,o);score=700+100*_en(tgt)+30*(int(o.get('inPlayArea',0) or 0)==4)
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best else None

def _best_wall_attach(obs):
 cur,me,op,y=_players(obs);best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=8 or sid!=DARK:continue
  tgt=_target(obs,o);en=_en(tgt);score=-1000
  if tid==MORGREM:score=1200-300*en
  elif tid==IMPIDIMP:score=750-250*en
  elif tid==MUNKIDORI:score=650-500*min(1,en)
  elif tid==GRIMMSNARL:score=-1500
  elif tid in (SNORUNT,FROSLASS):score=-1800
  if int(o.get('inPlayArea',0) or 0)==4:score+=80
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best and best[0]>0 else None

def _best_wall_attack(obs):
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=13:continue
  aid=int(o.get('attackId',0) or 0);score={CORKSCREW_MORGREM:1000,CORKSCREW_IMPIDIMP:400,SHADOW_BULLET:-1000}.get(aid,0)
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best and best[0]>0 else None

def _best_grimmsnarl_evolve(obs):
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=9 or sid!=GRIMMSNARL:continue
  tgt=_target(obs,o); score=1000
  if tid==MORGREM:score+=100
  if _en(tgt):score+=30*_en(tgt)
  if int(o.get('inPlayArea',0) or 0)==4:score+=20
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best else None

def _best_froslass_evolve(obs,profile):
 if not profile.startswith('grass'):return None
 cur,me,op,y=_players(obs)
 if _inplay(me,FROSLASS)>=2:return None
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==9 and sid==FROSLASS and tid==SNORUNT:
   tgt=_target(obs,o);score=500+_dam(tgt)
   if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best else None

def _best_attack(obs):
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=13:continue
  aid=int(o.get('attackId',0) or 0);score=1000+(300 if aid==SHADOW_BULLET else 0)
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best else None

def _ready_grim_bench(obs):
 cur,me,op,y=_players(obs)
 return any(cid(c)==GRIMMSNARL and _en(c)>=2 for c in me.get('bench') or [])

def _active_card(obs):
 return ((_players(obs)[1].get('active') or [None])[0])

def _best_retreat(obs):
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==12:return [i]
 return None

def _best_attach(obs,profile):
 cur,me,op,y=_players(obs); has_grim=_inplay(me,GRIMMSNARL)>0; energized_monkey=any(cid(c)==MUNKIDORI and _en(c)>0 for c in (me.get('active') or [])+(me.get('bench') or []))
 best=None
 for i,o,t,sid,tid in _main_candidates(obs):
  if t!=8 or sid!=DARK:continue
  tgt=_target(obs,o);score=0
  if tid==GRIMMSNARL:
   score=(1100+180*max(0,2-_en(tgt))) if _en(tgt)<2 else (-1200 if profile.startswith('grass') else 120)
  elif tid==MORGREM:
   score=(900 if not has_grim else 620) if _en(tgt)<2 else (-1050 if profile.startswith('grass') else 100)
  elif tid==IMPIDIMP:
   # One Energy attacks now; two makes the future Stage 1/2 line ready.
   score=(820 if _en(tgt)==0 else 650 if _en(tgt)==1 else (-950 if profile.startswith('grass') else 80))
  elif tid==MUNKIDORI:
   # If Grimmsnarl can evolve now, Punk Up will cover the Marnie's attacker;
   # the manual attachment belongs on the damage-transfer engine.
   imminent=_has_grimmsnarl_evolve(obs)
   score=(980 if (imminent and not energized_monkey and (profile.startswith('grass') or profile=='wall')) else 430 if not energized_monkey else 80)
   if profile.startswith('grass') and energized_monkey:score-=100
  elif tid==FROSLASS:score=-500
  elif tid==SNORUNT:score=-600
  if int(o.get('inPlayArea',0) or 0)==4:
   score+=40
   active=_active_card(obs)
   if _ready_grim_bench(obs) and cid(active)!=GRIMMSNARL and _en(active)==0:
    score+=1400
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best and best[0]>0 else None

def _play_source(obs,action):
 if not action:return 0,0
 opts=((obs or {}).get('select') or {}).get('option') or []
 if not (0<=action[0]<len(opts)):return 0,0
 o=opts[action[0]];return _opt_type(o),cid(_source(obs,o))

def _should_preempt(proposed_type,proposed_cid):
 # Free board development should happen before searches or ending the turn.
 return proposed_type in (-1,7,10,14) and proposed_cid not in (UNFAIR_STAMP,)

def _select_score(cid_,profile,me,op,source):
 inplay=Counter(cid(x) for x in (me.get('active') or [])+(me.get('bench') or [])); hand=Counter(cid(x) for x in me.get('hand') or [])
 bench_free=max(0,5-len(me.get('bench') or []))
 ready_morg=inplay[MORGREM]>0; ready_imp=inplay[IMPIDIMP]>0; ready_snow=inplay[SNORUNT]>0
 score=0
 if cid_==GRIMMSNARL:score=1000+(300 if ready_morg else 0)+(120 if ready_imp and hand[RARE_CANDY] else 0)-250*hand[GRIMMSNARL]
 elif cid_==MORGREM:score=780+(220 if ready_imp else 0)-220*(inplay[MORGREM]+hand[MORGREM])
 elif cid_==FROSLASS:score=720+(260 if ready_snow else 0)-260*(inplay[FROSLASS]+hand[FROSLASS])
 elif cid_==IMPIDIMP:
  target_lines=3 if profile=='grass_pure' else 2
  lines=inplay[IMPIDIMP]+inplay[MORGREM]+inplay[GRIMMSNARL]+hand[IMPIDIMP]
  score=720+180*(lines<target_lines)-260*max(0,lines-target_lines+1);score+=100 if bench_free else -1000
 elif cid_==SNORUNT:
  target=2 if profile.startswith('grass') else 1
  score=620+120*(inplay[FROSLASS]<target)-260*(inplay[SNORUNT]+inplay[FROSLASS]+hand[SNORUNT]);score+=100 if bench_free else -1000
 elif cid_==MUNKIDORI:
  target=1 if profile=='wall' else 2 if profile=='mirror' else 1 if profile.startswith('grass') else 2
  score=520-300*max(0,inplay[MUNKIDORI]+hand[MUNKIDORI]-target+1);score+=60 if bench_free else -1000
 elif cid_==RARE_CANDY:score=900 if ready_imp and hand[GRIMMSNARL] else 480
 elif cid_==UNFAIR_STAMP:score=850 if int(op.get('handCount',0) or 0)>=4 else 500
 elif cid_==POFFIN:score=760 if bench_free>=2 and (inplay[IMPIDIMP]<1 or inplay[SNORUNT]<1) else 100
 elif cid_==TOOL_SCRAPPER:
  tools=sum(len(c.get('tools') or []) for c in (op.get('active') or [])+(op.get('bench') or []));score=820 if tools else 80
 elif cid_==BOSS:
  damaged=max([_dam(c) for c in op.get('bench') or []] or [0]);score=780 if damaged>=30 else 350
 elif cid_==DAWN:score=700 if not ready_morg or not ready_snow else 300
 elif cid_==LILLIE:score=650 if int(me.get('handCount',len(me.get('hand') or [])) or 0)<=4 else 250
 elif cid_==SPIKEMUTH:score=620 if inplay[GRIMMSNARL]==0 else 250
 elif cid_==NIGHT_STRETCHER:score=500
 elif cid_==DARK:score=450
 else:score=50
 if profile=='wall':
  if cid_==MORGREM:score+=900
  elif cid_==FROSLASS:score+=750
  elif cid_==MUNKIDORI:score+=120 if inplay[MUNKIDORI]+hand[MUNKIDORI]<1 else -500
  elif cid_==IMPIDIMP:score+=500
  elif cid_==SNORUNT:score+=450
  elif cid_==GRIMMSNARL:score+=250 if inplay[MORGREM] else -250
  elif cid_==RARE_CANDY:score+=150 if inplay[IMPIDIMP] else -300
 if source==POKE_PAD:
  if profile.startswith('grass'):
   marnie_lines=inplay[IMPIDIMP]+inplay[MORGREM]+inplay[GRIMMSNARL]
   if cid_==IMPIDIMP and marnie_lines<2:score+=900
   if cid_==MORGREM and marnie_lines<2:score-=500
   if cid_==GRIMMSNARL and not ready_morg:score-=650
   if cid_==MUNKIDORI:score-=350
 if source==SPIKEMUTH:
  # Search the next missing rung, not the top stage too early.
  if ready_imp and not ready_morg:
   if cid_==MORGREM:score+=700
   if cid_==GRIMMSNARL:score-=500
  elif ready_morg:
   if cid_==GRIMMSNARL:score+=700
 if source==PETREL:
  if ready_imp and hand[GRIMMSNARL] and not hand[RARE_CANDY] and cid_==RARE_CANDY:score+=900
  if profile.startswith('grass') and cid_==POFFIN and inplay[IMPIDIMP]+inplay[MORGREM]+inplay[GRIMMSNARL]<2:score+=500
 return score

def _choose_to_hand(obs,profile,proposed):
 global _PENDING
 cur,me,op,y=_players(obs);sel=obs.get('select') or {};opts=sel.get('option') or [];source=any_cid(sel.get('effect')) or any_cid(sel.get('contextCard')) or _PENDING
 rows=[]
 for i,o in enumerate(opts):
  c=cid(_source(obs,o)); rows.append((_select_score(c,profile,me,op,source),i,c))
 if not rows:return proposed
 rows.sort(reverse=True);mn=int(sel.get('minCount',0) or 0);mx=min(int(sel.get('maxCount',0) or 0),len(rows))
 k=max(mn,mx)
 # For optional searches, choose only positive-value cards, but satisfy minimum.
 chosen=[];used_stage=set()
 for sc,i,c in rows:
  if len(chosen)>=k:break
  if source==DAWN:
   stage=0 if c in (IMPIDIMP,SNORUNT,MUNKIDORI) else 1 if c in (MORGREM,FROSLASS) else 2 if c==GRIMMSNARL else 9
   if stage in used_stage:continue
   used_stage.add(stage)
  if sc>0 or len(chosen)<mn:chosen.append(i)
 if len(chosen)<mn:chosen=[i for _,i,_ in rows[:mn]]
 _PENDING=0
 return chosen if legal(obs,chosen) else proposed

def _choose_poffin(obs,profile,proposed):
 # Poffin is a board-shape decision.  Build the attacker chain first, then
 # exactly one Froslass line, and only then spend a slot on redundancy.
 cur,me,op,y=_players(obs);sel=obs.get('select') or {};opts=sel.get('option') or []
 inplay=Counter(cid(x) for x in (me.get('active') or [])+(me.get('bench') or []))
 hand=Counter(cid(x) for x in me.get('hand') or [])
 mlines=inplay[IMPIDIMP]+inplay[MORGREM]+inplay[GRIMMSNARL]
 flines=inplay[SNORUNT]+inplay[FROSLASS]
 bench_free=max(0,5-len(me.get('bench') or []))
 rows=[]
 for i,o in enumerate(opts):
  c=cid(_source(obs,o));score=-1000
  if c==IMPIDIMP:
   # Two attacker lines are mandatory; a confirmed pure-Grass prize race
   # benefits from a third basic only after one Froslass line exists.
   target=3 if profile=='grass_pure' else 2
   future=mlines+hand[IMPIDIMP]
   score=1600 if future<2 else 1050 if (profile=='grass_pure' and future<target and flines>=1) else 300-250*future
  elif c==SNORUNT:
   score=1350 if flines+hand[SNORUNT]<1 else 700 if (mlines>=2 and flines<2) else 50-300*flines
  rows.append((score,-i,i,c))
 if not rows:return proposed
 rows.sort(reverse=True);mn=int(sel.get('minCount',0) or 0);mx=min(int(sel.get('maxCount',0) or 0),len(rows),bench_free if bench_free else len(rows))
 k=max(mn,mx);chosen=[];picked=Counter()
 for sc,ni,i,c in rows:
  if len(chosen)>=k:break
  # Avoid selecting two copies of the same Basic when the complementary role
  # is still missing, unless minimum count forces it.
  if c==SNORUNT and picked[SNORUNT] and mlines+picked[IMPIDIMP]<2:continue
  if c==IMPIDIMP and picked[IMPIDIMP]>=2:continue
  chosen.append(i);picked[c]+=1
 if len(chosen)<mn:
  for sc,ni,i,c in rows:
   if i not in chosen:chosen.append(i)
   if len(chosen)>=mn:break
 return chosen if legal(obs,chosen) else proposed


def _bench_duplicate_veto(obs,profile,proposed):
 # Do not give away Bench slots to redundant utility Pokemon.  The public
 # information ledger may identify Grass before the exact list is known, but
 # one Munkidori is enough for the immediate damage-transfer plan.
 if not profile.startswith('grass'):return proposed
 cur,me,op,y=_players(obs);ptype,pcid=_play_source(obs,proposed)
 if ptype!=7:return proposed
 inplay=Counter(cid(x) for x in (me.get('active') or [])+(me.get('bench') or []))
 redundant=(pcid==MUNKIDORI and inplay[MUNKIDORI]>=1) or (pcid==SNORUNT and inplay[SNORUNT]+inplay[FROSLASS]>=2)
 if not redundant:return proposed
 # Prefer a concrete tempo action over a redundant bench play.
 for alt in (_best_grimmsnarl_evolve(obs),_best_morgrem_evolve(obs),_best_froslass_evolve(obs,profile),_best_attach(obs,profile),_best_munkidori_ability(obs),_best_attack(obs)):
  if alt and legal(obs,alt):return alt
 # If nothing advances the board, simply decline the redundant play.
 for i,o,t,sid,tid in _main_candidates(obs):
  if t==14 and legal(obs,[i]):return [i]
 return proposed


def _choose_target(obs,profile,context,proposed):
 cur,me,op,y=_players(obs);opts=(obs.get('select') or {}).get('option') or [];best=None
 for i,o in enumerate(opts):
  c=_source(obs,o); target=_target(obs,o) or c; c_id=cid(target); score=0
  # playerIndex lets us distinguish own and opponent cards.
  try:rel_opp=int(o.get('playerIndex',y))!=y
  except:rel_opp=False
  if context==16: # remove damage from our side
   score=_dam(target)+300*(c_id==GRIMMSNARL)+180*(c_id==FROSLASS)+120*(c_id==MUNKIDORI)+500*(_remaining(target)<=30)
  elif context in (13,14,15):
   # Munkidori / attack damage target. Focus KOs and the active prize race.
   area=int(o.get('area',o.get('inPlayArea',0)) or 0);active=(area==4)
   score=500*(_remaining(target)<=30)+220*active+120*(int(target.get('maxHp',0) or 0)>=200)+20*_en(target)+_dam(target)
   if _PENDING_ATTACK==SHADOW_BULLET and area==5 and c_id in TERA_IDS:score-=1000
  elif context==3: # Boss target or our retreat/switch destination
   area=int(o.get('area',0) or 0)
   try:is_own=int(o.get('playerIndex',y))==y
   except:is_own=False
   if is_own:
    score=1000*(c_id==GRIMMSNARL and _en(target)>=2)+300*(c_id==GRIMMSNARL)+80*_en(target)-_dam(target)
   else:
    score=500*(_remaining(target)<=180)+160*(int(target.get('maxHp',0) or 0)>=200)+25*_en(target)+_dam(target)-_remaining(target)/10
  elif context==4: # promote our Pokemon
   # Promotion is a one-turn forecast, not merely a current-Energy sort.
   # A top player promotes the Pokemon that can become an attacker after the
   # next legal attachment/evolution sequence and avoids feeding a utility
   # Pokemon as a free Prize.
   en=_en(target); dark=_has_dark_in_hand(me); grim_hand=_has_in_hand(me,GRIMMSNARL)
   candy_hand=_has_in_hand(me,RARE_CANDY); morg_hand=_has_in_hand(me,MORGREM)
   score=-200
   if c_id==GRIMMSNARL:
    score=1250 if en>=2 else 1050 if en==1 and dark else 300
   elif c_id==MORGREM:
    # Grimmsnarl in hand turns this into an immediate Punk Up line.
    score=1220 if grim_hand else 900 if en>=2 else 820 if en==1 and dark else 420 if dark else 180
   elif c_id==IMPIDIMP:
    if grim_hand and candy_hand:score=1180
    elif morg_hand:score=720 if (en>=1 or dark) else 430
    else:score=520 if en>=1 else 360 if dark else 80
   elif c_id==MUNKIDORI:score=40 if en else -260
   elif c_id==FROSLASS:score=-450
   elif c_id==SNORUNT:score=-300
   score+=35*en-0.25*_dam(target)
  if best is None or score>best[0]:best=(score,i)
 return [best[1]] if best and legal(obs,[best[1]]) else proposed

def _choose_count(obs,proposed):
 opts=(obs.get('select') or {}).get('option') or [];best=None
 for i,o in enumerate(opts):
  try:n=int(o.get('number',0) or 0)
  except:n=0
  if best is None or n>best[0]:best=(n,i)
 return [best[1]] if best and legal(obs,[best[1]]) else proposed



def _wall_state(obs):
 cur,me,op,y=_players(obs)
 active=(me.get('active') or [None])[0]
 opp_active=(op.get('active') or [None])[0]
 cards=(me.get('active') or [])+(me.get('bench') or [])
 ready_grim=any(cid(c)==GRIMMSNARL and _en(c)>=2 for c in cards)
 ready_morg=any(cid(c)==MORGREM and _en(c)>=2 for c in cards)
 ready_imp=any(cid(c)==IMPIDIMP and _en(c)>=1 for c in cards)
 dark_hand=_inhand(me,DARK)>0
 frost=_inplay(me,FROSLASS)
 energized_monkey=any(cid(c)==MUNKIDORI and _en(c)>0 for c in cards)
 hard_active=cid(opp_active) in (117,345)
 kanga_active=cid(opp_active)==756
 return cur,me,op,y,active,opp_active,ready_grim,ready_morg,ready_imp,dark_hand,frost,energized_monkey,hard_active,kanga_active


def _wall_immediate_attack_ready(obs):
 cur,me,op,y,active,opp_active,rg,rm,ri,dh,fr,em,hard,kanga=_wall_state(obs)
 aid=cid(active); en=_en(active)
 if aid==GRIMMSNARL and en>=2:return True
 if aid==MORGREM and en>=2:return True
 if aid==IMPIDIMP and en>=1:return True
 return False


def _wall_boss_is_live(obs):
 # Boss is a tempo card, not a setup card.  Use it only when an attack is
 # already available and the gust changes the prize/lock outcome this turn.
 if not _wall_immediate_attack_ready(obs):return False
 cur,me,op,y,active,opp_active,rg,rm,ri,dh,fr,em,hard,kanga=_wall_state(obs)
 own=cid(active)
 for c in op.get('bench') or []:
  hp=_remaining(c); target=cid(c)
  if own==GRIMMSNARL and (hp<=180 or target==756):return True
  if own in (MORGREM,IMPIDIMP) and target in (117,345) and hp<=60:return True
 return False


def _wall_main_score(obs,i,o,t,sid,tid):
 cur,me,op,y,active,opp_active,rg,rm,ri,dh,fr,em,hard,kanga=_wall_state(obs)
 active_id=cid(active); active_en=_en(active); bench_free=max(0,5-len(me.get('bench') or []))
 target=_target(obs,o); target_en=_en(target); score=-200
 # The order mirrors a strong human turn: guaranteed damage/KO, abilities,
 # attacker readiness, engine development, then optional value plays.
 if t==13:
  aid=int(o.get('attackId',0) or 0)
  if aid==CORKSCREW_MORGREM:
   score=5600 if hard else 3500
  elif aid==CORKSCREW_IMPIDIMP:
   score=3600 if hard else 2200
  elif aid==SHADOW_BULLET:
   # Into Crustle/Cornerstone the active hit may be prevented, but the 30
   # Bench damage remains useful.  Into Kangaskhan it is the primary plan.
   score=5200 if kanga else (2800 if hard and (op.get('bench') or []) else 4300)
  else:score=2500
 elif t==10:
  if sid==MUNKIDORI and any(_dam(c)>0 for c in (me.get('active') or [])+(me.get('bench') or [])):
   score=6200
  elif sid==SPIKEMUTH:score=1350
  else:score=1800
 elif t==9:
  if sid==FROSLASS:
   score=4200 if fr<2 else 700
  elif sid==MORGREM:
   score=3900+300*target_en
  elif sid==GRIMMSNARL:
   if target_en>=2:
    score=5100 if not hard else (3400 if op.get('bench') else 1200)
   else:
    score=2600 if kanga else (1100 if hard else 2300)
  else:score=1800
 elif t==8 and sid==DARK:
  if tid==GRIMMSNARL:
   score=4550 if target_en<2 and not hard else (2600 if target_en<2 else 100)
  elif tid==MORGREM:
   score=4700 if target_en<2 else 100
   if target is active:score+=300
  elif tid==IMPIDIMP:
   score=3900 if target_en<1 else (3000 if target_en<2 else 50)
  elif tid==MUNKIDORI:
   # One energized Munkidori is enough until an attacker and Froslass exist.
   score=3100 if (not em and fr>0 and (rg or rm or ri)) else (1350 if not em else -800)
  else:score=-1800
 elif t==12:
  # Retreat only when it creates an attack now or a one-attachment attack.
  candidates=[]
  for c in me.get('bench') or []:
   ce=_en(c);cc=cid(c)
   v=0
   if cc==GRIMMSNARL and ce>=2:v=4900
   elif cc==MORGREM and (ce>=2 or (ce==1 and dh)):v=4500
   elif cc==IMPIDIMP and (ce>=1 or dh):v=3300
   candidates.append(v)
  score=max(candidates or [0])
  if active_id in (MUNKIDORI,SNORUNT,FROSLASS):score+=250
 elif t==7:
  if sid==BOSS:
   score=3500 if _wall_boss_is_live(obs) else -6000
  elif sid==TOOL_SCRAPPER:
   tools=sum(len(c.get('tools') or []) for c in (op.get('active') or [])+(op.get('bench') or []))
   score=3800 if tools else -500
  elif sid==POFFIN:
   missing_att=_inplay(me,IMPIDIMP)+_inplay(me,MORGREM)+_inplay(me,GRIMMSNARL)<2
   missing_frost=_inplay(me,SNORUNT)+fr<2
   score=3200 if bench_free and (missing_att or missing_frost) else 300
  elif sid==POKE_PAD:score=2850
  elif sid==PETREL:score=2700
  elif sid==DAWN:score=2400
  elif sid==NIGHT_STRETCHER:score=2200
  elif sid==UNFAIR_STAMP:score=2600 if int(op.get('handCount',0) or 0)>=5 else 1000
  elif sid==LILLIE:score=2100 if int(me.get('handCount',len(me.get('hand') or [])) or 0)<=4 else 900
  elif sid==RARE_CANDY:
   # Rare Candy is valid against Kangaskhan or when it unlocks Bench pressure;
   # do not ban the ex line merely because a wall exists.
   score=3400 if (kanga or (op.get('bench') or [])) and _inhand(me,GRIMMSNARL)>0 else 500
  elif sid==IMPIDIMP:
   score=3300 if bench_free and _inplay(me,IMPIDIMP)+_inplay(me,MORGREM)+_inplay(me,GRIMMSNARL)<2 else 250
  elif sid==SNORUNT:
   score=3000 if bench_free and _inplay(me,SNORUNT)+fr<2 else 200
  elif sid==MUNKIDORI:
   score=2200 if bench_free and _inplay(me,MUNKIDORI)<1 else 150
  else:score=1200
 elif t==14:
  score=-1000
 return score


def _wall_main_choice(obs,proposed):
 rows=[]
 for i,o,t,sid,tid in _main_candidates(obs):
  rows.append((_wall_main_score(obs,i,o,t,sid,tid),-i,i,t,sid,tid))
 if not rows:return proposed
 rows.sort(reverse=True);best=rows[0]
 # Preserve the learned action when our domain model has no clearly positive
 # preference.  Otherwise execute the best full-turn step.
 if best[0] < 1000:return proposed
 return [best[2]]




def _punk_up_select_energy_cards(obs,profile,proposed):
 # Punk Up is optional (0..5).  A human stops once the current attacker and
 # one backup are ready.  This also denies Ogerpon free damage scaling from
 # surplus Energy on our Active Pokemon.
 cur,me,op,y=_players(obs); opts=(obs.get('select') or {}).get('option') or []
 mons=[c for c in (me.get('active') or [])+(me.get('bench') or []) if cid(c) in (IMPIDIMP,MORGREM,GRIMMSNARL)]
 active=(me.get('active') or [None])[0]
 mons.sort(key=lambda c:(0 if c is active else 1,0 if cid(c)==GRIMMSNARL else 1 if cid(c)==MORGREM else 2,_en(c)))
 # Two attackers are the prize-race plan.  Do not feed a third line while the
 # first two are unfinished.
 needed=sum(max(0,2-_en(c)) for c in mons[:2])
 needed=max(0,min(needed,len(opts),int((obs.get('select') or {}).get('maxCount',0) or 0)))
 out=list(range(needed))
 return out if legal(obs,out) else proposed


def _punk_up_choose_recipient(obs,profile,proposed):
 cur,me,op,y=_players(obs); opts=(obs.get('select') or {}).get('option') or []
 active=(me.get('active') or [None])[0]; rows=[]
 for i,o in enumerate(opts):
  c=_source(obs,o); cc=cid(c); deficit=max(0,2-_en(c))
  if cc not in (IMPIDIMP,MORGREM,GRIMMSNARL):continue
  stage=3 if cc==GRIMMSNARL else 2 if cc==MORGREM else 1
  # Fill the Active attacker first, then the most advanced backup.  Once a
  # Pokemon reaches two Energy its score drops below any unfinished line.
  score=10000*deficit + 1000*(c is active) + 100*stage - 10*_en(c)
  if profile.startswith('grass') and _en(c)>=2:score-=20000
  rows.append((score,-i,i))
 if not rows:return proposed
 out=[max(rows)[-1]]
 return out if legal(obs,out) else proposed


def choose(obs,proposed,profile):
 global _PENDING,_PENDING_ATTACK
 if not legal(obs,proposed):
  s=obs.get('select') or {};n=len(s.get('option') or []);mn=int(s.get('minCount',0) or 0);proposed=list(range(min(mn,n)))
 sel=obs.get('select') or {};ctx=int(sel.get('context',-1) if sel.get('context') is not None else -1)
 out=proposed
 # Before the opponent list is identified, change only actions that are
 # mechanically dominant across all Grass variants.  This is evidence-gated
 # adaptation: broad board-shape rules wait for a confirmed signature.
 if profile=='grass_unknown':
  if ctx==22 and any_cid(sel.get('effect'))==GRIMMSNARL:
   out=_punk_up_select_energy_cards(obs,profile,proposed);_STATS['unknown_safe_energy_cap']+=int(out!=proposed)
  elif ctx==21 and any_cid(sel.get('effect'))==GRIMMSNARL:
   out=_punk_up_choose_recipient(obs,profile,proposed);_STATS['unknown_safe_energy_target']+=int(out!=proposed)
  elif ctx in (3,4,13,14,15,16):
   out=_choose_target(obs,profile,ctx,proposed);_STATS['unknown_safe_target']+=int(out!=proposed)
  elif ctx in (39,40):
   out=_choose_count(obs,proposed);_STATS['unknown_safe_count']+=int(out!=proposed)
  return out if legal(obs,out) else proposed
 if ctx==0:
  ptype,pcid=_play_source(obs,proposed)
  if profile=='wall':
   out=_wall_main_choice(obs,proposed)
   _STATS['wall_full_turn_rerank']+=int(out!=proposed)
   typ,scid=_play_source(obs,out);_PENDING=scid if typ in (7,10) else 0
   opts=sel.get('option') or []
   if out and 0<=out[0]<len(opts):_PENDING_ATTACK=int(opts[out[0]].get('attackId',0) or 0)
   else:_PENDING_ATTACK=0
   return out if legal(obs,out) else proposed
  candy_plan=_rare_candy_turn_plan(obs,profile)
  prep=_prepunk_munkidori(obs,profile)
  needed=_best_needed_basic_play(obs,profile)
  g=_best_grimmsnarl_evolve(obs)
  ability=_best_munkidori_ability(obs)
  pivot=_best_retreat(obs) if _ready_grim_bench(obs) else None
  active=_active_card(obs)
  # Full-turn order: secure a turn-3 Rare Candy line when possible, establish
  # the transfer engine, attach manually, evolve, activate abilities, attack.
  if candy_plan:out=candy_plan;_STATS['rare_candy_turn_plan']+=1
  elif prep:out=prep;_STATS['prepunk_munkidori']+=1
  elif ability and pivot:out=ability;_STATS['pivot_ability_first']+=1
  elif pivot and _en(active)>0:out=pivot;_STATS['pivot_to_ready_grim']+=1
  elif ptype==8:
   at=_best_attach(obs,profile)
   if at:out=at;_STATS['rerank_attachment']+=int(out!=proposed)
  elif needed and ptype==7 and pcid in (SNORUNT,MUNKIDORI,IMPIDIMP):
   out=needed;_STATS['bench_role_priority']+=int(out!=proposed)
  elif g and _should_preempt(ptype,pcid):out=g;_STATS['force_grimmsnarl']+=1
  elif ability and ptype in (13,14):out=ability;_STATS['ability_before_attack']+=1
  else:
   f=_best_froslass_evolve(obs,profile)
   if f and ptype in (10,14):out=f;_STATS['force_froslass']+=1
   elif ptype==14:
    a=_best_attack(obs)
    if a:out=a;_STATS['prevent_end_attack']+=1
    else:
     at=_best_attach(obs,profile)
     if at:out=at;_STATS['prevent_end_attach']+=1
   elif ptype==10 and pcid==SPIKEMUTH and g:
    out=g;_STATS['evolve_before_stadium_search']+=1
  out=_bench_duplicate_veto(obs,profile,out)
  typ,scid=_play_source(obs,out)
  _PENDING=scid if typ in (7,10) else 0
  opts=sel.get('option') or []
  if out and 0<=out[0]<len(opts):_PENDING_ATTACK=int(opts[out[0]].get('attackId',0) or 0)
  else:_PENDING_ATTACK=0
 elif ctx==22 and any_cid(sel.get('effect'))==GRIMMSNARL:
  out=_punk_up_select_energy_cards(obs,profile,proposed);_STATS['punk_up_energy_cap']+=int(out!=proposed)
 elif ctx==21 and any_cid(sel.get('effect'))==GRIMMSNARL:
  out=_punk_up_choose_recipient(obs,profile,proposed);_STATS['punk_up_target_plan']+=int(out!=proposed)
 elif ctx==5:
  out=_choose_poffin(obs,profile,proposed);_STATS['poffin_board_plan']+=int(out!=proposed)
 elif ctx==7:
  out=_choose_to_hand(obs,profile,proposed);_STATS['search_ranked']+=int(out!=proposed)
 elif ctx in (3,4,13,14,15,16):
  out=_choose_target(obs,profile,ctx,proposed);_STATS['target_ranked']+=int(out!=proposed)
 elif ctx in (39,40):
  out=_choose_count(obs,proposed);_STATS['count_maximized']+=int(out!=proposed)
 elif ctx==43:
  # Activate Punk Up and useful abilities whenever legal; YES is option type 1.
  yes=[i for i,o in enumerate(sel.get('option') or []) if _opt_type(o)==1]
  if yes and legal(obs,[yes[0]]):out=[yes[0]]
 if not legal(obs,out):out=proposed
 return out
