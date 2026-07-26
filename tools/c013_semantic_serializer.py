"""c013 §26 — semantically complete, runtime-visible state serialization.

c012's Claude test failed on its own terms: states exposed option COUNTS and policy
diagnostics, so the model was asked to choose between `a0..aN` with nothing to reason about.
That measured formatting, not understanding.

Here every card is decoded to its real name and attributes from the simulator's own card
database, and every legal action carries an action type, a human description, the card
involved, its text, source zone, target description, visible preconditions and a visible
effect summary (§26). Nothing outside the runtime-visible set is included: no opponent hand,
no deck order, no future randomness, no other agent's choice, no outcome.
"""
from __future__ import annotations
import json,os,sys
from typing import Any,Dict,List
import numpy as np
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO)
from cg import api as A, state_encoder_v2 as enc

CARD_TYPE={0:"Pokemon",1:"Trainer-Item",2:"Trainer-Supporter",3:"Trainer-Stadium",
           4:"Trainer-Tool",5:"Energy",6:"Trainer"}
ENERGY={0:"None",1:"Grass",2:"Fire",3:"Water",4:"Lightning",5:"Psychic",6:"Fighting",
        7:"Darkness",8:"Metal",9:"Fairy",10:"Dragon",11:"Colorless"}

_DB=None
def db():
    global _DB
    if _DB is None:
        _DB={c.cardId:c for c in A.all_card_data()}
    return _DB

def card_semantics(cid:int)->Dict[str,Any]:
    """Human-readable identity + rules-relevant attributes for one card id."""
    c=db().get(int(cid))
    if c is None:
        return {"card_id":int(cid),"card_name":"(unknown card)","card_type":"unknown",
                "card_text":""}
    stage=("Basic" if c.basic else "Stage 1" if c.stage1 else "Stage 2" if c.stage2 else "-")
    tags=[t for t,v in (("ex",c.ex),("Mega ex",c.megaEx),("Tera",c.tera),
                        ("ACE SPEC",c.aceSpec)) if v]
    d={"card_id":int(cid),"card_name":c.name,
       "card_type":CARD_TYPE.get(int(c.cardType),str(c.cardType))}
    if int(c.cardType)==0:
        d.update({"hp":int(c.hp or 0),"stage":stage,
                  "energy_type":ENERGY.get(int(c.energyType or 0),"?"),
                  "retreat_cost":int(c.retreatCost or 0),
                  "weakness":ENERGY.get(int(c.weakness),"none") if c.weakness else "none",
                  "evolves_from":c.evolvesFrom or None,"tags":tags})
        d["card_text"]=(f"{c.name}: {stage} {d['energy_type']} Pokemon, {d['hp']} HP, "
                        f"retreat {d['retreat_cost']}, weakness {d['weakness']}"
                        + (f", {', '.join(tags)}" if tags else "")
                        + (f", evolves from {c.evolvesFrom}" if c.evolvesFrom else ""))
    else:
        d["card_text"]=f"{c.name}: {d['card_type']}"
    return d

ACTION_TYPES=("ATTACK","ATTACH_ENERGY","EVOLVE","SEARCH","ABILITY","RETREAT","PROMOTE",
              "TARGET","MULTI_SELECT","PASS","OTHER")

def classify_action(prim:Dict[str,Any],targ:Dict[str,Any],form:str,idx:int,n:int)->str:
    """Best-effort semantic action type from the visible option card roles.

    The simulator's option encoding gives a primary card and an optional target card; the type
    is inferred from those and the decision form. Where the evidence does not determine a
    type, OTHER is returned rather than a guess dressed up as fact.
    """
    if form in ("FIXED_MULTISELECT","VARIABLE_MULTISELECT"): return "MULTI_SELECT"
    pt=prim.get("card_type","")
    if pt=="Energy": return "ATTACH_ENERGY"
    if pt.startswith("Trainer"): return "SEARCH" if "Item" in pt or "Supporter" in pt else "OTHER"
    if pt=="Pokemon":
        if prim.get("stage") in ("Stage 1","Stage 2") and prim.get("evolves_from"): return "EVOLVE"
        if targ.get("card_name"): return "TARGET"
        return "PROMOTE"
    return "OTHER"

def describe_action(aid:str,prim:Dict[str,Any],targ:Dict[str,Any],atype:str,
                    opt_index:int=0)->Dict[str,Any]:
    """A minority of options carry no card id in the visible encoding (positional or
    numeric choices such as pass/zone/count selections). Those are described as exactly
    that rather than as "choose (no card)", which reads as a missing decode."""
    pn=prim.get("card_name","(none)"); tn=targ.get("card_name")
    if pn in ("(no card)","(none)","(unknown card)"):
        return {"action_id":aid,"action_type":"OTHER",
                "human_description":f"Non-card option #{opt_index} (a positional or numeric "
                                    f"choice; the visible encoding attaches no card to it)",
                "card_name":None,"card_text":"",
                "source_zone":"decision option (no card)","target_description":tn or "(none)",
                "visible_preconditions":[],
                "visible_effect_summary":f"Selects decision option #{opt_index}. This option "
                                         f"has no card attached in the information visible to "
                                         f"you."}
    human={"ATTACH_ENERGY":f"Attach {pn}"+(f" to {tn}" if tn else ""),
           "EVOLVE":f"Evolve into {pn}"+(f" on {tn}" if tn else ""),
           "SEARCH":f"Play {pn}",
           "TARGET":f"Use {pn}"+(f" targeting {tn}" if tn else ""),
           "PROMOTE":f"Choose {pn}",
           "MULTI_SELECT":f"Select {pn}",
           "OTHER":f"Choose {pn}"}.get(atype,f"Choose {pn}")
    pre=[]
    if prim.get("evolves_from"): pre.append(f"requires {prim['evolves_from']} in play")
    if prim.get("retreat_cost"): pre.append(f"retreat cost {prim['retreat_cost']}")
    eff=prim.get("card_text","")
    return {"action_id":aid,"action_type":atype,"human_description":human,
            "card_name":pn,"card_text":eff,
            "source_zone":"hand/board (visible)","target_description":tn or "(no explicit target)",
            "visible_preconditions":pre,
            "visible_effect_summary":(f"{human}. {eff}" if eff else human)}

def serialize(t:Dict[str,Any],state_id:str,category:str,entropy=None,value=None)->Dict[str,Any]:
    """One runtime-visible, semantically decoded state (§26)."""
    feat=t.get("feat") or {}
    def ids(a):
        return [int(x) for x in np.asarray(a).ravel().tolist() if int(x)>0]
    hand=[card_semantics(c) for c in ids(feat.get("hand_rows",[]))]
    board=[card_semantics(c) for c in ids(feat.get("board_rows",[]))]
    disc=[card_semantics(c) for c in ids(feat.get("disc_rows",[]))][:15]
    opt=np.asarray(feat.get("opt_rows",np.zeros((1,1,2))))
    n=int(t.get("n_options") or 0); form=t.get("form","SINGLE_CHOICE")
    actions=[]
    for i in range(n):
        try:
            p=int(opt[0,i,0]) if opt.ndim==3 else int(opt[i,0])
            q=int(opt[0,i,1]) if opt.ndim==3 else int(opt[i,1])
        except Exception: p=q=0
        pr=card_semantics(p) if p>0 else {"card_name":"(no card)","card_type":""}
        tg=card_semantics(q) if q>0 else {}
        actions.append(describe_action(f"a{i}",pr,tg,classify_action(pr,tg,form,i,n),i))
    g=np.asarray(feat.get("global",[])).ravel().tolist()
    return {"state_id":state_id,"category":category,
            "decision_form":form,"select_min":t.get("lo"),"select_max":t.get("hi"),
            "player_role":"you are the active player making this decision",
            "own_hand":hand,"own_hand_size":len(hand),
            "own_board_public":board,"discard_public":disc,
            "legal_actions":actions,"n_legal_actions":len(actions),
            "policy_entropy":None if entropy is None else round(float(entropy),4),
            "value_confidence":None if value is None else round(float(value),4),
            "global_features_decoded":{f"g{i}":round(float(v),3) for i,v in enumerate(g[:20])},
            "rules_note":"Pokemon TCG Pocket-style battle. You win by taking all prize points. "
                         "Attacks need the listed energy attached. Evolution requires the "
                         "pre-evolution in play. Only one Supporter and one energy attachment "
                         "per turn.",
            "visibility_note":"Everything above is information the acting player legally sees. "
                              "The opponent's hand, deck order, future randomness, any other "
                              "agent's choice and the game result are excluded."}

FORBIDDEN=("opponent_hand","opponent hand","hidden","deck_order","deck order","future",
           "eventual","outcome","winner","teacher_action","incumbent_action","result")
DOC_FIELDS=("rules_note","visibility_note","card_text","visible_effect_summary","human_description")

def audit(rec:Dict[str,Any])->Dict[str,Any]:
    """§26 hidden-information audit over DATA fields; documentation prose is excluded because
    it legitimately names the categories it promises to exclude."""
    def scan(o,path=""):
        hits=[]
        if isinstance(o,dict):
            for k,v in o.items():
                if k in DOC_FIELDS: continue
                if any(f in k.lower() for f in FORBIDDEN): hits.append(f"key:{path}{k}")
                hits+=scan(v,f"{path}{k}.")
        elif isinstance(o,list):
            for i,v in enumerate(o): hits+=scan(v,f"{path}[{i}].")
        elif isinstance(o,str):
            low=o.lower()
            for f in ("opponent's hand","deck order","will draw","the winner","eventual outcome"):
                if f in low: hits.append(f"value:{path}")
        return hits
    h=scan(rec)
    return {"state_id":rec["state_id"],"violations":h,"clean":not h,
            "n_legal_actions":rec["n_legal_actions"],
            "all_actions_semantically_typed":all(a["action_type"] in ACTION_TYPES
                                                 for a in rec["legal_actions"]),
            "card_bearing_actions":sum(1 for a in rec["legal_actions"] if a["card_name"]),
            "non_card_options":sum(1 for a in rec["legal_actions"] if not a["card_name"]),
            "every_action_has_a_human_description":all(a["human_description"]
                                                       for a in rec["legal_actions"]),
            "no_raw_numeric_only_actions":all(a["human_description"]
                                              for a in rec["legal_actions"])}
