from __future__ import annotations
from collections import Counter, defaultdict

# Public-information only. The overlay never reads hidden hand/deck contents.
DARK=7; FROSLASS=104; MUNKIDORI=112; IMPIDIMP=646; MORGREM=647; GRIMMSNARL=648; SNORUNT=860
TOOL_SCRAPPER=1137; BOSS=1182; SPIKEMUTH=1259; LIVELY_STADIUM=1251; HERO_CAPE=1159
SHADOW_BULLET=937; CORKSCREW_IMPIDIMP=935; CORKSCREW_MORGREM=936
TERA_IDS={37,75,80,96,99,108,117,121,150,153,154,161,176,189,193,210,223,229,231,232,236,239,241,243,244,246,248,249,269,272,283,293,299,302,306,313,316,320,326,328,329,331,336,337,340,357,369,372,381,389,404,407,424,431,447,455,458,471,481,509,515,525,527,547,561,573,583,598,618,631,641,648}

_SEEN_SERIALS=set(); _VISIBLE=Counter(); _ATTACKS=Counter(); _STADIUMS=Counter(); _LAST_KEY=None; _STATS=Counter()

def reset():
    global _SEEN_SERIALS,_VISIBLE,_ATTACKS,_STADIUMS,_LAST_KEY
    _SEEN_SERIALS=set();_VISIBLE=Counter();_ATTACKS=Counter();_STADIUMS=Counter();_LAST_KEY=None;_STATS.clear()

def stats():
    return {'visible_cards':dict(_VISIBLE),'opponent_attacks':dict(_ATTACKS),'stadiums':dict(_STADIUMS),'decisions':dict(_STATS)}

def cid(x):
    try:return int((x or {}).get('id',0) or 0)
    except Exception:return 0

def serial(x):
    try:return int((x or {}).get('serial',0) or 0)
    except Exception:return 0

def _players(obs):
    cur=(obs or {}).get('current') or {}; ps=cur.get('players') or [{},{}]; y=int(cur.get('yourIndex',0) or 0)
    if not (0<=y<len(ps)):y=0
    me=ps[y] if y<len(ps) else {};op=ps[1-y] if len(ps)>1 else {}
    return cur,me,op,y

def _zone(p,area):return {2:p.get('hand') or [],3:p.get('discard') or [],4:p.get('active') or [],5:p.get('bench') or [],6:p.get('prize') or []}.get(int(area or 0),[])

def _source(obs,opt):
    cur,me,op,y=_players(obs);sel=(obs or {}).get('select') or {};area=opt.get('area');idx=opt.get('index');pidx=opt.get('playerIndex',y)
    try:pidx=int(pidx)
    except Exception:pidx=y
    p=me if pidx==y else op
    arr=sel.get('deck') or [] if area==1 else _zone(p,area)
    return arr[idx] if isinstance(idx,int) and 0<=idx<len(arr) else None

def _target(obs,opt):
    cur,me,op,y=_players(obs);area=opt.get('inPlayArea');idx=opt.get('inPlayIndex');pidx=opt.get('playerIndex',y)
    if area is None and _otype(opt)==10:area=opt.get('area');idx=opt.get('index')
    try:pidx=int(pidx)
    except Exception:pidx=y
    p=me if pidx==y else op;arr=_zone(p,area)
    return arr[idx] if isinstance(idx,int) and 0<=idx<len(arr) else None

def _otype(o):
    try:return int(o.get('type',-1))
    except Exception:return -1

def _en(c):return len((c or {}).get('energyCards') or []) if isinstance(c,dict) else 0

def _hp(c):return int((c or {}).get('hp',9999) or 9999) if isinstance(c,dict) else 9999

def _maxhp(c):return int((c or {}).get('maxHp',0) or 0) if isinstance(c,dict) else 0

def _dam(c):return max(0,_maxhp(c)-_hp(c))

def legal(obs,a):
    s=(obs or {}).get('select') or {};n=len(s.get('option') or []);mn=int(s.get('minCount',0) or 0);mx=int(s.get('maxCount',0) or 0)
    return isinstance(a,list) and mn<=len(a)<=mx and len(a)==len(set(a)) and all(isinstance(i,int) and 0<=i<n for i in a)

def observe(obs,profile='unknown'):
    global _LAST_KEY
    if not obs or obs.get('select') is None:reset();return
    cur,me,op,y=_players(obs);key=(int(cur.get('turn',0) or 0),int(cur.get('turnActionCount',0) or 0),y,len(obs.get('logs') or []))
    if key==_LAST_KEY:return
    _LAST_KEY=key
    for c in (op.get('active') or [])+(op.get('bench') or [])+(op.get('discard') or []):
        s=serial(c);i=cid(c)
        if i and (not s or s not in _SEEN_SERIALS):
            _VISIBLE[i]+=1
            if s:_SEEN_SERIALS.add(s)
    st=cur.get('stadium') or []
    if st:_STADIUMS[cid(st[0])]+=1
    for log in obs.get('logs') or []:
        if not isinstance(log,dict):continue
        try:pi=int(log.get('playerIndex',-1));aid=int(log.get('attackId',0) or 0)
        except Exception:continue
        if pi==1-y and aid:_ATTACKS[aid]+=1

def _main(obs):
    opts=((obs or {}).get('select') or {}).get('option') or []
    return [(i,o,_otype(o),cid(_source(obs,o)),cid(_target(obs,o))) for i,o in enumerate(opts)]

def _attack_damage(obs):
    cur,me,op,y=_players(obs);a=(me.get('active') or [None])[0];cc=cid(a);en=_en(a)
    if cc==GRIMMSNARL and en>=2:return 180
    if cc==MORGREM and en>=2:return 60
    if cc==IMPIDIMP and en>=1:return 30
    return 0

def _shadow_ready(obs):
    return any(t==13 and int(o.get('attackId',0) or 0)==SHADOW_BULLET for i,o,t,sid,tid in _main(obs))

def _froslass_count(me):return sum(cid(c)==FROSLASS for c in (me.get('active') or [])+(me.get('bench') or []))

def _prizes_left(p):
    # Engine observations expose the remaining prize cards as a list.
    pr=p.get('prize')
    return len(pr) if isinstance(pr,list) else 6

def _closing_main(obs,proposed):
    cur,me,op,y=_players(obs);oa=(op.get('active') or [None])[0];damage=_attack_damage(obs)
    if damage<=0 or not isinstance(oa,dict):return proposed
    own_left=_prizes_left(me);active_hp=_hp(oa)
    # A top player converts a guaranteed two-Prize KO before spending the turn
    # on generic draw/search. This branch is evidence-gated by visible HP.
    if active_hp>damage:
        bench=op.get('bench') or []
        killable=[c for c in bench if _hp(c)<=damage]
        valuable=[c for c in killable if _maxhp(c)>=200 or _en(c)>=2]
        if valuable and (own_left<=2 or active_hp>damage+30):
            for i,o,t,sid,tid in _main(obs):
                if t==7 and sid==BOSS:
                    _STATS['boss_exact_ko_line']+=1;return [i]
    # Remove an HP modifier only when it changes the current attack into a KO.
    tools=(oa.get('tools') or oa.get('toolCards') or [])
    if tools and active_hp>damage:
        has_cape=any((int(x) if not isinstance(x,dict) else cid(x))==HERO_CAPE for x in tools)
        if has_cape and active_hp-100<=damage:
            for i,o,t,sid,tid in _main(obs):
                if t==7 and sid==TOOL_SCRAPPER:
                    _STATS['tool_threshold_ko']+=1;return [i]
    st=cur.get('stadium') or []
    if st and cid(st[0])==LIVELY_STADIUM and active_hp>damage and active_hp-30<=damage:
        for i,o,t,sid,tid in _main(obs):
            if t==7 and sid==SPIKEMUTH:
                _STATS['stadium_threshold_ko']+=1;return [i]
    return proposed

def _boss_target(obs,proposed):
    cur,me,op,y=_players(obs);damage=_attack_damage(obs);opts=(obs.get('select') or {}).get('option') or []
    if damage<=0:return proposed
    rows=[]
    for i,o in enumerate(opts):
        c=_target(obs,o) or _source(obs,o)
        if not isinstance(c,dict):continue
        try:is_opp=int(o.get('playerIndex',y))!=y
        except Exception:is_opp=False
        if not is_opp:continue
        hp=_hp(c);two=_maxhp(c)>=200;ko=hp<=damage
        # Exact KO dominates, then prize value, attached resources and engine body.
        score=100000*ko+18000*two+1200*_en(c)+_dam(c)-hp
        rows.append((score,-i,i))
    if not rows:return proposed
    out=[max(rows)[-1]]
    if legal(obs,out):_STATS['boss_target_forecast']+=int(out!=proposed);return out
    return proposed

def _counter_target(obs,context,proposed):
    cur,me,op,y=_players(obs);opts=(obs.get('select') or {}).get('option') or [];shadow=_shadow_ready(obs);frost=_froslass_count(me);rows=[]
    for i,o in enumerate(opts):
        c=_target(obs,o) or _source(obs,o)
        if not isinstance(c,dict):continue
        try:is_opp=int(o.get('playerIndex',y))!=y
        except Exception:is_opp=True
        if not is_opp:continue
        area=int(o.get('area',o.get('inPlayArea',0)) or 0);active=area==4;hp=_hp(c);cc=cid(c);en=_en(c)
        score=0
        if context in (13,14):
            # Adrena-Brain: take the 30-HP KO, or bridge the Active exactly into
            # Shadow Bullet. Public HP makes this deterministic, not speculative.
            score=100000*(hp<=30)+70000*(shadow and active and hp<=210)+6000*active+900*en+_dam(c)-hp
        else: # Shadow Bullet bench splash
            tera_penalty=100000 if area==5 and cc in TERA_IDS else 0
            delayed_ko=(hp<=30+10*frost)
            score=90000*(hp<=30)+45000*delayed_ko+1500*en+_dam(c)-hp-tera_penalty
        rows.append((score,-i,i))
    if not rows:return proposed
    out=[max(rows)[-1]]
    if legal(obs,out):_STATS['damage_target_forecast']+=int(out!=proposed);return out
    return proposed

def _damage_source(obs,proposed):
    cur,me,op,y=_players(obs);opts=(obs.get('select') or {}).get('option') or [];rows=[]
    # Remove counters from the piece whose loss most damages the next-turn plan.
    for i,o in enumerate(opts):
        c=_target(obs,o) or _source(obs,o)
        if not isinstance(c,dict):continue
        try:is_own=int(o.get('playerIndex',y))==y
        except Exception:is_own=True
        if not is_own:continue
        cc=cid(c);hp=_hp(c);dam=_dam(c);role=5000 if cc==GRIMMSNARL else 3300 if cc==FROSLASS else 2600 if cc==MUNKIDORI else 1200
        endangered=25000 if hp<=30 else 9000 if hp<=60 else 0
        score=100*dam+role+endangered+400*_en(c)
        rows.append((score,-i,i))
    if not rows:return proposed
    out=[max(rows)[-1]]
    if legal(obs,out):_STATS['damage_source_forecast']+=int(out!=proposed);return out
    return proposed

def choose(obs,proposed,profile):
    if profile!='grass_pure' or not legal(obs,proposed):return proposed
    sel=(obs or {}).get('select') or {};ctx=int(sel.get('context',-1) if sel.get('context') is not None else -1);out=proposed
    if ctx==0:out=_closing_main(obs,out)
    elif ctx==3:out=_boss_target(obs,out)
    elif ctx in (13,14,15):out=_counter_target(obs,ctx,out)
    elif ctx==16:out=_damage_source(obs,out)
    return out if legal(obs,out) else proposed
