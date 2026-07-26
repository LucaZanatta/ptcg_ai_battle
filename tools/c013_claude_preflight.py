"""c013 §25-§29 — Claude Opus SEMANTIC preflight.

This is a semantic-understanding test, not teacher qualification (§25), and it may not claim
teacher superiority (§29). The one thing it fixes relative to c012 is the input: states carry
real card names, card text, decoded board fields and typed, human-readable legal actions, so
a wrong answer means the model misunderstood the position rather than that it was handed
opaque indices.
"""
import argparse,gzip,hashlib,json,os,pickle,subprocess,sys,time
from collections import Counter
import numpy as np
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c013_semantic_serializer as S
C013=os.path.join(_REPO,"contracts","c013_fixed_deck_policy_combination_and_learnability")
ART=os.path.join(C013,"results","artifacts"); LOGD=os.path.join(C013,"results","test_logs")
MODEL="opus"; OPUS_PREFIX="claude-opus"

SCHEMA={"type":"object","additionalProperties":False,
    "required":["state_id","selected_action_id","ranked_action_ids","confidence",
                "strategic_tags","short_rationale"],
    "properties":{"state_id":{"type":"string"},"selected_action_id":{"type":"string"},
      "ranked_action_ids":{"type":"array","items":{"type":"string"}},
      "confidence":{"type":"number","minimum":0,"maximum":1},
      "strategic_tags":{"type":"array","items":{"type":"string"}},
      "short_rationale":{"type":"string","maxLength":600}}}

PROMPT="""You are choosing one action in a Pokemon Trading Card Game position.

Everything below is information the acting player can legally see. You do NOT see the
opponent's hand, the deck order, future randomness, any other agent's choice, or the eventual
result. Do not reason about hidden cards as though you knew them.

Each legal action is described with its type, the card involved, that card's text, and what it
targets. Choose the single best legal action and then rank the legal actions best to worst.
Your rationale must refer to the cards and effects actually shown.

POSITION
{state}

Reply with ONE JSON object and nothing else:
{{"state_id": "<the state_id above>",
  "selected_action_id": "<an action_id from legal_actions>",
  "ranked_action_ids": ["<action_id>", ...],
  "confidence": <number between 0 and 1>,
  "strategic_tags": ["<short tag>", ...],
  "short_rationale": "<one to three sentences naming the cards or effects that drove the choice>"}}

Rules: selected_action_id must appear in legal_actions; ranked_action_ids may contain only
legal action_ids with no duplicates; confidence in [0,1]."""

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def call(state,timeout=240):
    prompt=PROMPT.format(state=json.dumps(state,indent=2))
    t0=time.time()
    try:
        r=subprocess.run(["claude","-p",prompt,"--model",MODEL,"--allowed-tools","",
                          "--output-format","json"],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok":False,"error":"timeout","result":None,"resolved_models":[],
                "opus_output_tokens":0,"model_verified":False,"cost_usd":0.0,
                "seconds":time.time()-t0,"prompt":prompt}
    except Exception as e:
        return {"ok":False,"error":repr(e)[:200],"result":None,"resolved_models":[],
                "opus_output_tokens":0,"model_verified":False,"cost_usd":0.0,
                "seconds":time.time()-t0,"prompt":prompt}
    try: env=json.loads(r.stdout)
    except Exception:
        return {"ok":False,"error":"unparseable_wrapper","result":None,"resolved_models":[],
                "opus_output_tokens":0,"model_verified":False,"cost_usd":0.0,
                "seconds":time.time()-t0,"prompt":prompt}
    u=env.get("modelUsage") or {}
    opus=[m for m in u if m.startswith(OPUS_PREFIX)]
    tok=sum(u[m].get("outputTokens",0) for m in opus)
    return {"ok":not env.get("is_error"),"result":env.get("result"),
            "resolved_models":sorted(u),"opus_output_tokens":tok,
            "model_verified":bool(opus and tok>0),"cost_usd":env.get("total_cost_usd"),
            "seconds":time.time()-t0,"prompt":prompt}

def parse(txt):
    if not txt: return None
    i,j=txt.find("{"),txt.rfind("}")
    if i<0 or j<0: return None
    try: return json.loads(txt[i:j+1])
    except Exception: return None

def validate(lab,state):
    """§28 — legality, schema, hidden-information, and SEMANTIC GROUNDING of the rationale."""
    errs=[]
    if not lab: return ["unparseable"],{}
    legal={a["action_id"] for a in state["legal_actions"]}
    for k in SCHEMA["required"]:
        if k not in lab: errs.append(f"missing:{k}")
    if lab.get("state_id")!=state["state_id"]: errs.append("state_id_mismatch")
    if lab.get("selected_action_id") not in legal: errs.append("illegal_selected_action")
    rk=lab.get("ranked_action_ids") or []
    if any(x not in legal for x in rk): errs.append("illegal_in_ranking")
    if len(rk)!=len(set(rk)): errs.append("duplicate_in_ranking")
    c=lab.get("confidence")
    if not isinstance(c,(int,float)) or not (0<=c<=1): errs.append("confidence_out_of_range")
    txt=(lab.get("short_rationale") or "")
    low=json.dumps(lab).lower()
    for f in ("opponent's hand","opponent hand","their hand","deck order","top of deck",
              "will draw","the outcome was","eventual"):
        if f in low: errs.append(f"hidden_information_reference:{f}")
    # semantic grounding: does the rationale name a card or action type actually supplied?
    names={a["card_name"].lower() for a in state["legal_actions"] if a.get("card_name")}
    names|={c["card_name"].lower() for c in state.get("own_hand",[])}
    types={a["action_type"].lower() for a in state["legal_actions"]}
    tl=txt.lower()
    grounded=any(n and n in tl for n in names) or any(t.replace("_"," ") in tl for t in types)
    sem={"rationale_names_supplied_card_or_action_type":bool(grounded),
         "rationale_len":len(txt),
         "selected_action_type":next((a["action_type"] for a in state["legal_actions"]
                                      if a["action_id"]==lab.get("selected_action_id")),None)}
    if not grounded: errs.append("rationale_not_semantically_grounded")
    return errs,sem

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True,choices=["build","label","repeat"])
    p.add_argument("--n",type=int,default=30); p.add_argument("--max-cost",type=float,default=14.0)
    a=p.parse_args(argv)
    os.makedirs(ART,exist_ok=True); os.makedirs(LOGD,exist_ok=True)
    bench=os.path.join(ART,"semantic_state_benchmark.jsonl.gz")

    if a.stage=="build":
        from cg import c010_train as ct, c009_eval as ce
        from cg.teachers import make_fresh
        reg=json.load(open(os.path.join(ART,"candidate_registry.json")))["candidates"]
        inc=reg["C012_SOUP_622_633"]; ck=os.path.join(_REPO,inc["checkpoint_path"])
        deck=make_fresh("dragapult",ce.SOURCES).deck
        opps=["dragapult","mega_lucario","iono","mega_abomasnow"]
        jobs=[{"policy_ckpt":ck,"policy_version":1,"policy_sha256":inc["checkpoint_sha256"],
               "arm":"SEM","seed":13,"game_index":i,"opponent":("teacher",opps[i%4]),
               "seat":i%2,"rng_seed":70000+i,"deck":deck} for i in range(40)]
        out=ct.run_rollout(jobs,16)
        trs=[t for r in out for t in (r.get("transitions") or [])]
        recs=[]
        for i,t in enumerate(trs):
            form=t.get("form","SINGLE_CHOICE"); n=int(t.get("n_options") or 0)
            if n<2: cat="promotion"
            elif form!="SINGLE_CHOICE": cat="multi_select"
            elif n>=8: cat="target_selection"
            else: cat="setup"
            r=S.serialize(t,f"SS{i:04d}",cat,entropy=None,value=t.get("value"))
            types=Counter(x["action_type"] for x in r["legal_actions"])
            r["category"]=(types.most_common(1)[0][0].lower() if types else cat)
            recs.append(r)
        # §27: <=4 states per category
        by=Counter(); sel=[]
        for r in sorted(recs,key=lambda x:-x["n_legal_actions"]):
            if by[r["category"]]>=4: continue
            by[r["category"]]+=1; sel.append(r)
            if len(sel)>=a.n: break
        aud=[S.audit(r) for r in sel]
        with gzip.open(bench,"wt") as fh:
            for r in sel: fh.write(json.dumps(r)+"\n")
        json.dump({"n_states":len(sel),"categories":dict(by),
                   "max_per_category":max(by.values()) if by else 0,
                   "cap_rule":"§27 no more than four states from one category",
                   "all_hidden_information_clean":all(x["clean"] for x in aud),
                   "all_actions_semantically_typed":all(x["all_actions_semantically_typed"] for x in aud),
                   "card_bearing_actions":sum(x["card_bearing_actions"] for x in aud),
                   "non_card_options":sum(x["non_card_options"] for x in aud),
                   "every_action_has_a_human_description":all(
                       x["every_action_has_a_human_description"] for x in aud),
                   "semantic_note":"A minority of options carry no card id in the visible "
                                   "encoding (positional/numeric choices). Those are labelled "
                                   "as such rather than left as undecoded indices.",
                   "benchmark_sha256":sha(bench),"audits":aud},
                  open(os.path.join(ART,"semantic_state_schema.json"),"w"),indent=2)
        open(os.path.join(ART,"claude_prompt.md"),"w").write("# Frozen prompt (§26/§28)\n\n```\n"+PROMPT+"\n```\n")
        json.dump(SCHEMA,open(os.path.join(ART,"claude_output_schema.json"),"w"),indent=2)
        print(json.dumps({"n_states":len(sel),"categories":dict(by),
                          "clean":all(x["clean"] for x in aud)},indent=2))
        return 0

    states=[json.loads(l) for l in gzip.open(bench,"rt")]
    if a.stage=="label": subset=states[:a.n]; phase="primary"
    else:
        op=os.path.join(ART,"claude_preflight_outputs.jsonl.gz")
        done=[json.loads(l)["state_id"] for l in gzip.open(op,"rt")
              if json.loads(l)["phase"]=="primary" and (json.loads(l).get("raw_result") or "").strip()]
        subset=[s for s in states if s["state_id"] in set(done[:a.n])]; phase="repeat"
    mode="wt" if phase=="primary" else "at"
    fi=gzip.open(os.path.join(ART,"claude_preflight_inputs.jsonl.gz"),mode)
    fo=gzip.open(os.path.join(ART,"claude_preflight_outputs.jsonl.gz"),mode)
    outs=[];cost=0.0
    for i,st in enumerate(subset):
        if cost>a.max_cost:
            print(f"cost cap reached after {i}",flush=True); break
        r=call(st); lab=parse(r.get("result")); errs,sem=validate(lab,st)
        cost+=r.get("cost_usd") or 0
        fi.write(json.dumps({"phase":phase,"state_id":st["state_id"],
            "prompt_sha256":hashlib.sha256(r["prompt"].encode()).hexdigest(),"state":st})+"\n"); fi.flush()
        rec={"phase":phase,"state_id":st["state_id"],"category":st["category"],
             "raw_result":r.get("result"),"label":lab,"errors":errs,"schema_valid":not errs,
             "semantic":sem,"model_verified":r.get("model_verified"),
             "resolved_models":r.get("resolved_models"),"cost_usd":r.get("cost_usd"),
             "seconds":r.get("seconds")}
        outs.append(rec); fo.write(json.dumps(rec)+"\n"); fo.flush()
        if (i+1)%5==0: print(f"  {phase} {i+1}/{len(subset)} ${cost:.2f}",flush=True)
    fi.close(); fo.close()
    ret=[o for o in outs if (o.get("raw_result") or "").strip()]
    val={"phase":phase,"n":len(outs),"n_returned":len(ret),
         "n_call_failures":len(outs)-len(ret),
         "schema_valid_rate":sum(1 for o in ret if o["schema_valid"])/max(1,len(ret)),
         "legal_action_rate":sum(1 for o in ret if not any(e.startswith("illegal") for e in o["errors"]))/max(1,len(ret)),
         "hidden_information_violations":sum(1 for o in ret if any("hidden_information" in e for e in o["errors"])),
         "semantically_grounded_rate":sum(1 for o in ret if o["semantic"].get("rationale_names_supplied_card_or_action_type"))/max(1,len(ret)),
         "model_verified_rate":sum(1 for o in ret if o["model_verified"])/max(1,len(ret)),
         "categories_covered":sorted({o["category"] for o in ret}),
         "error_counts":dict(Counter(e for o in ret for e in o["errors"])),
         "total_cost_usd":round(cost,2)}
    vp=os.path.join(ART,"claude_semantic_validation.json")
    prev=json.load(open(vp)) if os.path.exists(vp) else {}
    prev[phase]=val; json.dump(prev,open(vp,"w"),indent=2)
    with open(os.path.join(LOGD,"claude_semantic_preflight.txt"),"a") as fh:
        fh.write(json.dumps(val,indent=2)+"\n")
    print(json.dumps(val,indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
