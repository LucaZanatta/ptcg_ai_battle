"""c013 §15 — recombine the separately-continued components (Q2A/Q2B).

After continuation each component is evaluated on its own, then the three registered
recombinations are built: equal weight soup, equal logit ensemble, equal probability
ensemble. No weight tuning (§15).
"""
import json,os,sys
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c013_ensemble_policy as ep, c013_common as K
from cg import c013_eval_core as ec
C013=os.path.join(_REPO,"contracts","c013_fixed_deck_policy_combination_and_learnability")
ART=os.path.join(C013,"results","artifacts")

def final_ckpt(arm,seed):
    p=os.path.join(ART,"training",arm,f"seed{seed}","checkpoint_registry.json")
    if not os.path.exists(p): return None
    r=json.load(open(p))
    if not r: return None
    k=max(r,key=lambda x:int(x))
    return r[k]

def main():
    a=final_ckpt("Q2A",903); b=final_ckpt("Q2B",904)
    if not (a and b):
        json.dump({"error":"Q2 component checkpoints unavailable","recombinations":{}},
                  open(os.path.join(ART,"Q2_recombination_results.json"),"w"),indent=2)
        print("Q2 components unavailable"); return 0
    comps=[("Q2A_S622_continued",a),("Q2B_S633_continued",b)]
    paths=[os.path.join(_REPO,c[1]["checkpoint_path"]) for c in comps]
    shas=[c[1]["sha256"] for c in comps]
    ids=[c[0] for c in comps]
    out={"note":"§15 registered recombinations of the separately continued components. Equal "
                "weights only; no tuning after results.",
         "components":{i:{"checkpoint_path":m["checkpoint_path"],"sha256":m["sha256"],
                          "training_games":m["training_games"]} for i,(n,m) in zip(ids,comps)},
         "recombinations":{}}
    sdir=os.path.join(ART,"soups"); mdir=os.path.join(ART,"ensembles")
    os.makedirs(sdir,exist_ok=True); os.makedirs(mdir,exist_ok=True)
    sp=os.path.join(sdir,"Q2_SOUP_recombined.npz")
    ep.weight_soup(paths,sp)
    out["recombinations"]["Q2_SOUP_recombined"]={"candidate_type":"weight_soup",
        "checkpoint_path":os.path.relpath(sp,_REPO),"sha256":K.sha_file(sp),
        "component_ids":ids,"component_sha256":shas}
    for mode,tag in (("logit","Q2_LOGIT_recombined"),("prob","Q2_PROB_recombined")):
        mp_=os.path.join(mdir,f"{tag}.json")
        ec.write_manifest(mp_,mode,ids,[os.path.relpath(p,_REPO) for p in paths],shas)
        out["recombinations"][tag]={"candidate_type":"online_ensemble","ensemble_mode":mode,
            "checkpoint_path":os.path.relpath(mp_,_REPO),"sha256":K.sha_file(mp_),
            "component_ids":ids,"component_sha256":shas,
            "component_paths":[os.path.relpath(p,_REPO) for p in paths]}
    json.dump(out,open(os.path.join(ART,"Q2_recombination_results.json"),"w"),indent=2)
    # expose to the evaluator's registry
    creg=os.path.join(ART,"combination_registry.json")
    reg=json.load(open(creg))
    for cid,m in out["recombinations"].items():
        reg["combinations"][cid]={"candidate_id":cid,**m,"architecture_id":"v2a_trunk+value_head+stop_logit",
            "trainable":m["candidate_type"]=="weight_soup","deployable":True,
            "source_contract":"c013","source_evidence":"§15 Q2 recombination",
            "weights":"equal","n_components":len(ids),
            "checkpoint_sha256":m["sha256"]}
    json.dump(reg,open(creg,"w"),indent=2)
    print(json.dumps({"components":ids,"recombinations":list(out["recombinations"])},indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
