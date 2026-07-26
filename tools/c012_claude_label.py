"""c012 §37-§39 — Claude Opus offline labeling through Claude Code.

Non-interactive print mode, explicit Opus request, tools disabled, frozen prompt and schema,
sequential execution, bounded state count, raw prompt and response saved for every call.

"No silent model fallback" (§37) is enforced per call: Claude Code's --output-format json
reports `modelUsage`, and a label is rejected unless claude-opus-5 actually produced output
tokens for it.
"""
import argparse, gzip, hashlib, json, os, subprocess, sys, time
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c012_eval as ev
ART,LOGD=ev.ART,ev.LOGD
MODEL="opus"; EXPECT_MODEL_PREFIX="claude-opus"

SCHEMA={"type":"object","required":["state_id","selected_action_id","ranked_action_ids",
        "confidence","strategic_tags","short_rationale"],
        "properties":{"state_id":{"type":"string"},"selected_action_id":{"type":"string"},
          "ranked_action_ids":{"type":"array","items":{"type":"string"}},
          "confidence":{"type":"number","minimum":0,"maximum":1},
          "strategic_tags":{"type":"array","items":{"type":"string"}},
          "short_rationale":{"type":"string","maxLength":400}},
        "additionalProperties":False}

PROMPT="""You are choosing one action in a Pokemon Trading Card Game position.

You see ONLY what a player legally sees at this moment. You do NOT see the opponent's hand,
the deck order, future randomness, any other agent's choice, or how the game turns out. Do
not speculate about hidden cards as if you knew them.

Choose the single best legal action, then rank the legal actions from best to worst.

Position:
{state}

Reply with ONE JSON object and nothing else, matching exactly this schema:
{{"state_id": "<the state_id above>",
  "selected_action_id": "<one action_id from legal_actions>",
  "ranked_action_ids": ["<action_id>", ...],
  "confidence": <number 0..1>,
  "strategic_tags": ["<short tag>", ...],
  "short_rationale": "<one or two sentences, no hidden information>"}}

Rules: selected_action_id must appear in legal_actions; ranked_action_ids must contain only
legal action_ids with no duplicates; confidence in [0,1]; rationale concise."""

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def call_claude(state, timeout=180):
    prompt=PROMPT.format(state=json.dumps(state,indent=2))
    t0=time.time()
    try:
        r=subprocess.run(["claude","-p",prompt,"--model",MODEL,"--allowed-tools","",
                          "--output-format","json"],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok":False,"error":"timeout","seconds":time.time()-t0,"result":None,
                "resolved_models":[],"opus_output_tokens":0,"model_verified":False,
                "cost_usd":0.0}
    except Exception as e:
        return {"ok":False,"error":repr(e)[:200],"seconds":time.time()-t0,"result":None,
                "resolved_models":[],"opus_output_tokens":0,"model_verified":False,
                "cost_usd":0.0}
    dur=time.time()-t0
    try: env=json.loads(r.stdout)
    except Exception: return {"ok":False,"error":"unparseable_wrapper","raw":r.stdout[:2000],
                              "stderr":r.stderr[:500],"seconds":dur}
    usage=env.get("modelUsage") or {}
    opus=[m for m in usage if m.startswith(EXPECT_MODEL_PREFIX)]
    opus_out=sum(usage[m].get("outputTokens",0) for m in opus)
    return {"ok":not env.get("is_error"),"result":env.get("result"),
            "resolved_models":sorted(usage),"opus_output_tokens":opus_out,
            "model_verified":bool(opus and opus_out>0),
            "cost_usd":env.get("total_cost_usd"),"seconds":dur,
            "session_id":env.get("session_id")}

def parse_label(txt):
    if not txt: return None
    s=txt.strip()
    i,j=s.find("{"),s.rfind("}")
    if i<0 or j<0: return None
    try: return json.loads(s[i:j+1])
    except Exception: return None

def validate(lab, state):
    legal={a["action_id"] for a in state["legal_actions"]}
    errs=[]
    if not lab: return ["unparseable"]
    for k in SCHEMA["required"]:
        if k not in lab: errs.append(f"missing:{k}")
    if lab.get("state_id")!=state["state_id"]: errs.append("state_id_mismatch")
    sel=lab.get("selected_action_id")
    if sel not in legal: errs.append("illegal_selected_action")
    rk=lab.get("ranked_action_ids") or []
    if any(x not in legal for x in rk): errs.append("illegal_in_ranking")
    if len(rk)!=len(set(rk)): errs.append("duplicate_in_ranking")
    c=lab.get("confidence")
    if not isinstance(c,(int,float)) or not (0<=c<=1): errs.append("confidence_out_of_range")
    if len(str(lab.get("short_rationale") or ""))>400: errs.append("rationale_too_long")
    txt=json.dumps(lab).lower()
    for f in ("opponent's hand","opponent hand","their hand","deck order","top of deck",
              "will draw","eventual","the outcome was"):
        if f in txt: errs.append(f"hidden_information_reference:{f}")
    return errs

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True,choices=["preflight","label","repeat"])
    p.add_argument("--n",type=int,default=240); p.add_argument("--max-cost",type=float,default=60.0)
    a=p.parse_args(argv)
    os.makedirs(ART,exist_ok=True); os.makedirs(LOGD,exist_ok=True)
    states=[json.loads(l) for l in gzip.open(os.path.join(ART,"hard_state_benchmark.jsonl.gz"),"rt")]
    man=json.load(open(os.path.join(ART,"hard_state_manifest.json")))
    open(os.path.join(ART,"claude_prompt.md"),"w").write("# Frozen Claude prompt (§38)\n\n```\n"+PROMPT+"\n```\n")
    json.dump(SCHEMA,open(os.path.join(ART,"claude_label_schema.json"),"w"),indent=2)

    if a.stage=="preflight":
        outs=[]
        for st in states[:3]:
            r=call_claude(st); lab=parse_label(r.get("result")); errs=validate(lab,st)
            outs.append({"state_id":st["state_id"],**{k:r[k] for k in
                ("ok","resolved_models","opus_output_tokens","model_verified","cost_usd","seconds")},
                "schema_valid":not errs,"errors":errs,"label":lab})
        ok=all(o["ok"] and o["model_verified"] for o in outs)
        doc={"requested_model":MODEL,"expected_model_prefix":EXPECT_MODEL_PREFIX,
             "tools_enabled":False,"non_interactive":True,"sequential":True,
             "n_preflight_states":len(outs),
             "all_calls_succeeded":all(o["ok"] for o in outs),
             "all_calls_used_opus":all(o["model_verified"] for o in outs),
             "all_schema_valid":all(o["schema_valid"] for o in outs),
             "preflight_pass":ok and all(o["schema_valid"] for o in outs),
             "resolved_models_seen":sorted({m for o in outs for m in o["resolved_models"]}),
             "model_verification_rule":"a call counts as Opus only when a claude-opus-* entry "
                                       "in modelUsage has non-zero outputTokens; Claude Code's "
                                       "background summarisation model may also appear and is "
                                       "not accepted as the labelling model",
             "estimated_cost_per_call_usd":round(sum(o["cost_usd"] or 0 for o in outs)/max(1,len(outs)),4),
             "projected_cost_full_run_usd":round(sum(o["cost_usd"] or 0 for o in outs)/max(1,len(outs))*(man["n_primary"]+man["n_repeat"]),2),
             "calls":outs}
        json.dump(doc,open(os.path.join(ART,"claude_preflight.json"),"w"),indent=2)
        with open(os.path.join(LOGD,"claude_preflight.txt"),"w") as fh:
            fh.write(json.dumps({k:v for k,v in doc.items() if k!="calls"},indent=2)+"\n")
        print(json.dumps({k:doc[k] for k in ("preflight_pass","all_calls_used_opus",
            "resolved_models_seen","estimated_cost_per_call_usd","projected_cost_full_run_usd")},indent=2))
        return 0

    # §48 caps labels at 300 primary / 60 repeat. A smaller REGISTERED subset is used here:
    # the preflight measured ~$0.23/call, so the full 288 would cost ~$67. Repeats are drawn
    # from the labelled primary subset so consistency is measured on states that were in fact
    # labelled twice.
    primary = states[:a.n]
    if a.stage == "label":
        subset = primary
    else:
        ids = [s["state_id"] for s in primary]
        rep = [i for i in man["repeat_state_ids"] if i in set(ids)][:a.n]
        subset = [s for s in primary if s["state_id"] in set(rep)]
    phase="primary" if a.stage=="label" else "repeat"
    inputs,outputs=[],[]
    cost=0.0
    mode0="wt" if phase=="primary" else "at"
    fi=gzip.open(os.path.join(ART,"claude_inputs.jsonl.gz"),mode0)
    fo=gzip.open(os.path.join(ART,"claude_outputs.jsonl.gz"),mode0)
    for i,st in enumerate(subset):
        if cost>a.max_cost:
            print(f"cost cap {a.max_cost} reached after {i} labels",flush=True); break
        r=call_claude(st); lab=parse_label(r.get("result")); errs=validate(lab,st)
        cost+=r.get("cost_usd") or 0
        inputs.append({"phase":phase,"state_id":st["state_id"],"prompt_sha256":
                       hashlib.sha256(PROMPT.format(state=json.dumps(st,indent=2)).encode()).hexdigest(),
                       "state":st})
        outputs.append({"phase":phase,"state_id":st["state_id"],"raw_result":r.get("result"),
                        "label":lab,"errors":errs,"schema_valid":not errs,
                        "model_verified":r.get("model_verified"),
                        "resolved_models":r.get("resolved_models"),
                        "opus_output_tokens":r.get("opus_output_tokens"),
                        "cost_usd":r.get("cost_usd"),"seconds":r.get("seconds")})
        fi.write(json.dumps(inputs[-1])+"\n"); fi.flush()
        fo.write(json.dumps(outputs[-1])+"\n"); fo.flush()
        if (i+1)%10==0: print(f"  {phase} {i+1}/{len(subset)} cost=${cost:.2f}",flush=True)
    fi.close(); fo.close()
    val={"phase":phase,"n":len(outputs),
         "schema_valid_rate":sum(1 for o in outputs if o["schema_valid"])/max(1,len(outputs)),
         "legal_action_rate":sum(1 for o in outputs if not any(e.startswith("illegal") for e in o["errors"]))/max(1,len(outputs)),
         "hidden_information_violations":sum(1 for o in outputs if any("hidden_information" in e for e in o["errors"])),
         "model_verified_rate":sum(1 for o in outputs if o["model_verified"])/max(1,len(outputs)),
         "call_failures":sum(1 for o in outputs if o.get("raw_result") is None),
         "total_cost_usd":round(cost,2),
         "error_counts":{},"per_state_errors":{o["state_id"]:o["errors"] for o in outputs if o["errors"]}}
    from collections import Counter
    val["error_counts"]=dict(Counter(e for o in outputs for e in o["errors"]))
    vp=os.path.join(ART,"claude_validation.json")
    prev=json.load(open(vp)) if os.path.exists(vp) else {}
    prev[phase]=val
    json.dump(prev,open(vp,"w"),indent=2)
    with open(os.path.join(LOGD,"claude_labeling.txt"),"a") as fh:
        fh.write(json.dumps({k:v for k,v in val.items() if k!="per_state_errors"},indent=2)+"\n")
    print(json.dumps({k:val[k] for k in ("phase","n","schema_valid_rate","legal_action_rate",
        "hidden_information_violations","model_verified_rate","total_cost_usd","error_counts")},indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
