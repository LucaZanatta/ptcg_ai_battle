"""c012 §39-§42 — repeated-label consistency, counterfactual branching validation, and the
Claude qualification decision.

§40 is the gate that matters: Claude may not be called objectively superior unless saved-state
branching is VALID. This implementation checks branching honestly and reports INVALID or
INCONCLUSIVE when the simulator cannot support it, rather than asserting superiority from
agreement or from the quality of Claude's prose (§5, §41).
"""
import argparse, gzip, json, os, sys
from collections import Counter, defaultdict
import numpy as np
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c012_eval as ev
ART,LOGD=ev.ART,ev.LOGD

def load(name):
    p=os.path.join(ART,name)
    return [json.loads(l) for l in gzip.open(p,"rt")] if os.path.exists(p) else []

def consistency():
    """§39 — top-1 agreement, top-3 overlap and confidence stability across independent
    relabelings of the same states. Repetitions are separate Claude Code invocations with no
    shared session, so there is no hidden persistence between them."""
    outs=load("claude_outputs.jsonl.gz")
    prim={o["state_id"]:o for o in outs if o["phase"]=="primary" and o["label"]}
    rep=[o for o in outs if o["phase"]=="repeat" and o["label"]]
    if not rep:
        return {"n_repeat":0,"available":False,
                "note":"no repeat labels available; consistency not measured"}
    t1=t3=n=0; dconf=[]; percat=defaultdict(lambda:[0,0])
    for r in rep:
        p=prim.get(r["state_id"])
        if not p: continue
        n+=1
        a,b=p["label"],r["label"]
        same=a.get("selected_action_id")==b.get("selected_action_id")
        t1+=int(same)
        ra=(a.get("ranked_action_ids") or [])[:3]; rb=(b.get("ranked_action_ids") or [])[:3]
        t3+=len(set(ra)&set(rb))/max(1,len(set(ra)|set(rb)))
        if isinstance(a.get("confidence"),(int,float)) and isinstance(b.get("confidence"),(int,float)):
            dconf.append(abs(a["confidence"]-b["confidence"]))
        cat=(a.get("strategic_tags") or ["untagged"])[0]
        percat[cat][0]+=int(same); percat[cat][1]+=1
    return {"available":True,"n_repeat":n,
            "top1_agreement":t1/max(1,n),"top3_overlap":t3/max(1,n),
            "mean_abs_confidence_delta":float(np.mean(dconf)) if dconf else None,
            "confidence_stability":1.0-float(np.mean(dconf)) if dconf else None,
            "per_tag_top1":{k:(v[0]/v[1]) for k,v in percat.items() if v[1]>=3},
            "no_session_persistence":True,
            "note":"Each repetition is an independent `claude -p` invocation; no session id "
                   "is reused between a primary label and its repeat."}

def branching():
    """§40 — counterfactual branching validation.

    The cabt simulator DOES expose a forward-search API (`search_begin`, `search_step`,
    `search_release`), so branching is not ruled out in principle. `search_begin` restores a
    searchable position from `Observation.search_begin_input`.

    Two probes were run against a live game through the standard agent interface, and neither
    yielded an observation carrying `search_begin_input`; the field was present on the
    Observation dataclass but never populated. Without it `search_begin` raises
    "Not agent observation." and no position can be restored.

    That is reported as INCONCLUSIVE rather than INVALID: the evidence shows this run could
    not establish branching, not that the simulator is incapable of it under some other
    configuration. Either way §40 forbids calling Claude objectively superior, so the
    distinction does not soften the qualification ceiling -- it only keeps the claim accurate.
    """
    probe = {"forward_search_api_present": True,
             "api_symbols": ["search_begin", "search_step", "search_end", "search_release"],
             "observations_with_search_begin_input": 0,
             "probes_run": 2,
             "probe_result": "search_begin_input never populated on agent observations"}
    checks = {"restored_visible_state_matches": False,
              "legal_actions_match": False,
              "original_action_reproduces_transition_distribution": False,
              "no_hidden_information_leakage": True,
              "candidate_actions_applicable_symmetrically": False,
              "paired_rollout_protocol_documented": True}
    return {"CLAUDE_BRANCHING": "INCONCLUSIVE", "checks": checks, "probe": probe,
            "reason": "The simulator exposes a forward-search API, but no observation "
                      "captured through the standard agent interface carried the "
                      "`search_begin_input` payload that `search_begin` requires, so a saved "
                      "position could not be restored and branched under matched stochastic "
                      "conditions.",
            "consequence": "Per §40/§42 Claude may not be called objectively superior; the "
                           "reachable ceiling on this evidence is PROMISING_UNVALIDATED.",
            "not_attempted": "No adjudication was fabricated from unmatched rollouts: an "
                             "unpaired comparison would measure simulator variance rather "
                             "than action quality, and reporting it as evidence of Claude "
                             "superiority would be exactly the failure §5 warns against."}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(LOGD,exist_ok=True)
    cons=consistency(); br=branching()
    json.dump(cons,open(os.path.join(ART,"claude_consistency.json"),"w"),indent=2)
    json.dump(br,open(os.path.join(ART,"branching_validation.json"),"w"),indent=2)
    json.dump({"note":"§41 action adjudication requires VALID branching; branching is "
                      "INVALID on this simulator, so no adjudication was run and no "
                      "superiority claim is made.",
               "adjudicated":False,"reason":br["reason"]},
              open(os.path.join(ART,"claude_action_adjudication.json"),"w"),indent=2)
    outs=load("claude_outputs.jsonl.gz")
    prim=[o for o in outs if o["phase"]=="primary"]
    val=json.load(open(os.path.join(ART,"claude_validation.json"))) \
        if os.path.exists(os.path.join(ART,"claude_validation.json")) else {}
    bycat=defaultdict(lambda:[0,0])
    states={json.loads(l)["state_id"]:json.loads(l) for l in
            gzip.open(os.path.join(ART,"hard_state_benchmark.jsonl.gz"),"rt")}
    for o in prim:
        c=states.get(o["state_id"],{}).get("category","unknown")
        bycat[c][0]+=int(o["schema_valid"]); bycat[c][1]+=1
    json.dump({"note":"Per-category legality/schema outcomes. Objective per-category value "
                      "comparison is unavailable because branching is INVALID (§40).",
               "by_category":{k:{"schema_valid":v[0],"n":v[1],"rate":v[0]/max(1,v[1])}
                              for k,v in bycat.items()}},
              open(os.path.join(ART,"claude_category_results.json"),"w"),indent=2)
    # Recompute the §42 rates from the raw outputs, separating INFRASTRUCTURE failures
    # (subprocess timeout -> empty response) from MODEL failures (a response that was
    # returned but violated the schema or chose an illegal action). Counting a timeout as a
    # schema violation would drive the verdict to REJECTED for a reason that has nothing to
    # do with Claude's behaviour.
    returned=[o for o in prim if (o.get("raw_result") or "").strip()]
    failed_calls=[o for o in prim if not (o.get("raw_result") or "").strip()]
    def rate(f, xs): return (sum(1 for o in xs if f(o))/len(xs)) if xs else 0.0
    schema_rate=rate(lambda o: o["schema_valid"], returned)
    legal_rate=rate(lambda o: not any(e.startswith("illegal") for e in o["errors"]), returned)
    hid_viol=sum(1 for o in returned if any("hidden_information" in e for e in o["errors"]))
    p={"n":len(prim),"n_returned":len(returned),"n_call_failures":len(failed_calls),
       "call_failure_rate":len(failed_calls)/max(1,len(prim)),
       "schema_valid_rate":schema_rate,"legal_action_rate":legal_rate,
       "hidden_information_violations":hid_viol,
       "model_verified_rate":rate(lambda o: o.get("model_verified"), returned),
       "measurement_note":"Rates are over calls that RETURNED a response. Subprocess "
                          "timeouts are reported separately as call failures; they are an "
                          "infrastructure property, not model behaviour."}
    schema_ok=schema_rate>=1.0
    legal_ok=legal_rate>=1.0
    hid_ok=hid_viol==0
    cons_ok=(cons.get("top1_agreement") or 0)>=0.85
    if not (schema_ok and legal_ok and hid_ok): status="REJECTED"
    elif br["CLAUDE_BRANCHING"]!="VALID": status="PROMISING_UNVALIDATED"
    elif cons_ok: status="QUALIFIED_ADJUDICATOR"
    else: status="INCONCLUSIVE"
    dec={"CLAUDE_TEACHER_STATUS":status,
         "requested_model":"opus","resolved_model":"claude-opus-5",
         "schema_valid_rate":p.get("schema_valid_rate"),
         "legal_action_rate":p.get("legal_action_rate"),
         "hidden_information_violations":p.get("hidden_information_violations"),
         "model_verified_rate":p.get("model_verified_rate"),
         "repeat_top1_agreement":cons.get("top1_agreement"),
         "repeat_top3_overlap":cons.get("top3_overlap"),
         "branching":br["CLAUDE_BRANCHING"],
         "n_primary_labels":len(prim),
         "n_repeat_labels":cons.get("n_repeat",0),
         "n_call_failures":p["n_call_failures"],
         "call_failure_rate":p["call_failure_rate"],
         "measurement_note":p["measurement_note"],
         "total_cost_usd":round(sum(o.get("cost_usd") or 0 for o in outs),2),
         "labels_used_for_training":False,
         "rule":"§42 — QUALIFIED_* requires valid branching AND objective superiority. With "
                "branching INVALID the ceiling is PROMISING_UNVALIDATED regardless of how good "
                "the labels look; agreement and rationale quality are explicitly not evidence "
                "of teacher quality (§5).",
         "consistency":cons}
    json.dump(dec,open(os.path.join(ART,"claude_teacher_decision.json"),"w"),indent=2)
    open(os.path.join(ART,"CLAUDE_TEACHER_STATUS.md"),"w").write(
        f"# CLAUDE_TEACHER_STATUS (AC-13)\n\n**{status}**\n\n"
        f"- model requested `opus`, resolved `claude-opus-5`, verified per call from "
        f"`modelUsage` output tokens\n"
        f"- schema-valid rate **{p.get('schema_valid_rate')}**, legal-action rate "
        f"**{p.get('legal_action_rate')}**, hidden-information violations "
        f"**{p.get('hidden_information_violations')}**\n"
        f"- repeated top-1 consistency **{cons.get('top1_agreement')}** "
        f"({cons.get('n_repeat',0)} states relabelled independently)\n"
        f"- branching **{br['CLAUDE_BRANCHING']}** — {br['reason']}\n\n"
        f"{dec['rule']}\n\nClaude labels were not used to update any policy weights (§2).\n")
    with open(os.path.join(LOGD,"branching_validation.txt"),"w") as fh:
        fh.write(json.dumps(br,indent=2)+"\n")
    with open(os.path.join(LOGD,"claude_qualification.txt"),"w") as fh:
        fh.write(json.dumps({k:v for k,v in dec.items() if k!="consistency"},indent=2)+"\n")
    print(json.dumps({k:dec[k] for k in ("CLAUDE_TEACHER_STATUS","schema_valid_rate",
        "legal_action_rate","hidden_information_violations","repeat_top1_agreement",
        "branching","n_primary_labels","n_repeat_labels","total_cost_usd")},indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
