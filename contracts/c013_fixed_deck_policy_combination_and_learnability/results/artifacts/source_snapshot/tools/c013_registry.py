"""c013 AC-01/AC-03 — dependency + immutability verification and the frozen candidate and
combination registries (§7, §8). Registries are frozen BEFORE any combination is evaluated."""
import argparse,gzip,hashlib,json,os,platform,shutil,subprocess,sys
from collections import defaultdict
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
C013=os.path.join(_REPO,"contracts","c013_fixed_deck_policy_combination_and_learnability")
ART=os.path.join(C013,"results","artifacts"); LOGD=os.path.join(C013,"results","test_logs")
C011A=os.path.join(_REPO,"contracts","c011_fixed_deck_cuda_ppo_scale","results","artifacts")
C012A=os.path.join(_REPO,"contracts","c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification","results","artifacts")
IMMUT=["c005_teacher_import_submission_and_dataset","c006_distilled_policy_baseline",
       "c007_hybrid_teacher_residual_and_state_encoder_v2","c008_fixed_deck_teacher_anchored_rl",
       "c009_amendment_c008","c010_fixed_deck_rl_loop_v2","c011_fixed_deck_cuda_ppo_scale",
       "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification"]
ARCH="v2a_trunk+value_head+stop_logit"

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def machine():
    import torch
    o={"os":_first("/etc/os-release","PRETTY_NAME="),"python":platform.python_version(),
       "cpu":_cpu(),"cpu_threads":os.cpu_count(),"ram_gib":round(_mem("MemTotal")/1048576,1),
       "ram_available_gib":round(_mem("MemAvailable")/1048576,1),
       "disk_free_gib":round(shutil.disk_usage(_REPO).free/2**30,1),
       "torch":torch.__version__,"torch_cuda":torch.version.cuda,
       "cuda_available":bool(torch.cuda.is_available())}
    if torch.cuda.is_available():
        free,total=torch.cuda.mem_get_info()
        o.update({"gpu":torch.cuda.get_device_name(0),"vram_total_mib":round(total/2**20),
                  "vram_free_mib":round(free/2**20)})
    try:
        o["driver"]=subprocess.run(["nvidia-smi","--query-gpu=driver_version",
            "--format=csv,noheader"],capture_output=True,text=True,timeout=30).stdout.strip().splitlines()[0]
    except Exception: o["driver"]=None
    return o
def _first(p,pref):
    try:
        for l in open(p):
            if l.startswith(pref): return l.split("=",1)[1].strip().strip('"')
    except OSError: pass
def _cpu():
    try:
        for l in open("/proc/cpuinfo"):
            if l.startswith("model name"): return l.split(":",1)[1].strip()
    except OSError: pass
def _mem(k):
    try:
        for l in open("/proc/meminfo"):
            if l.startswith(k): return int(l.split()[1])
    except OSError: pass
    return 0

def resolve_candidates():
    """§7 — resolve every required candidate id/hash from the earlier registries, never a filename."""
    out={}
    c11=json.load(open(os.path.join(C011A,"evaluation_candidate_registry.json")))
    c12=json.load(open(os.path.join(C012A,"evaluation_candidate_registry.json")))
    inc=json.load(open(os.path.join(C012A,"frozen_incumbent_registry.json")))
    def add(cid,src,path,src_contract,evidence,ctype="single",comps=None,csha=None,trainable=True):
        ap=os.path.join(_REPO,path)
        out[cid]={"candidate_id":cid,"candidate_type":ctype,"component_ids":comps or [],
                  "component_sha256":csha or [],"checkpoint_path":path,
                  "checkpoint_sha256":sha(ap),"architecture_id":ARCH,
                  "trainable":trainable,"deployable":True,"source_contract":src_contract,
                  "source_evidence":evidence,"resolved_from":src}
    # c012 incumbent soup
    t=inc["TRAINING_INCUMBENT"]
    add("C012_SOUP_622_633","c012 frozen_incumbent_registry",t["checkpoint_path"],"c012",
        "c012 AC-05 TRUE_INCUMBENT",ctype="weight_soup",
        comps=["S622","S633"],
        csha=[c11["S_622_g39983"]["checkpoint_sha256"],c11["S_633_g30176"]["checkpoint_sha256"]])
    for cid,src in (("S611","S_611_g40127"),("S622","S_622_g39983"),("S633","S_633_g30176")):
        add(cid,"c011 evaluation_candidate_registry",c11[src]["checkpoint_path"],"c011",
            f"c011 final policy {src}")
    # c012 arm bests, resolved from c012's own decision artifact
    cd=json.load(open(os.path.join(C012A,"curriculum_decision.json")))
    sb=cd["seed_best"]
    for want,cid in (("P0_711","P0_711"),("P1_822","P1_822"),("P1_833","P1_833")):
        real=sb[want]["candidate"]
        add(cid,"c012 curriculum_decision.seed_best",c12[real]["checkpoint_path"],"c012",
            f"c012 best confirmed checkpoint for {want}: {real}")
    # historical incumbents
    for cid,src,reg,evidence in (("C010_INCUMBENT","C_522_g20220",c12,"c010/c011 incumbent"),
                                 ("C008_I0","I0_incumbent",c12,"c008 R1 incumbent")):
        if src in reg: add(cid,"c012 registry",reg[src]["checkpoint_path"],"historical",evidence)
    return out

def build_combinations(cands):
    """§8 registered families. No broad search; equal weights only; frozen before results."""
    import c013_ensemble_policy as ep
    from cg import c013_eval_core as ec
    sets=[["S611","S622"],["S611","S633"],["S622","S633"],["S611","S622","S633"],
          ["C012_SOUP_622_633","P0_711"],["C012_SOUP_622_633","P1_822"],
          ["C012_SOUP_622_633","P1_833"],
          ["C012_SOUP_622_633","P0_711","P1_822"],
          ["C012_SOUP_622_633","P0_711","P1_833"],
          ["C012_SOUP_622_633","P0_711","P1_822","P1_833"]]
    soup_sets=[["C012_SOUP_622_633","P0_711"],["C012_SOUP_622_633","P1_822"],
               ["C012_SOUP_622_633","P1_833"],["P0_711","P1_822"],["P0_711","P1_833"],
               ["P1_822","P1_833"],["C012_SOUP_622_633","P0_711","P1_822","P1_833"]]
    comb={}
    mdir=os.path.join(ART,"ensembles"); sdir=os.path.join(ART,"soups")
    os.makedirs(mdir,exist_ok=True); os.makedirs(sdir,exist_ok=True)
    for mode,tag in (("logit","LOGIT"),("prob","PROB")):
        for s in sets:
            cid=f"{tag}_"+"+".join(x.replace("C012_SOUP_622_633","SOUP") for x in s)
            paths=[cands[x]["checkpoint_path"] for x in s]
            shas=[cands[x]["checkpoint_sha256"] for x in s]
            mp_=os.path.join(mdir,f"{cid}.json")
            ec.write_manifest(mp_,mode,s,paths,shas)
            comb[cid]={"candidate_id":cid,"candidate_type":"online_ensemble",
                       "ensemble_mode":mode,"component_ids":s,"component_sha256":shas,
                       "component_paths":paths,
                       "checkpoint_path":os.path.relpath(mp_,_REPO),
                       "checkpoint_sha256":sha(mp_),"architecture_id":ARCH,
                       "trainable":False,"deployable":True,"source_contract":"c013",
                       "source_evidence":"§8.2/§8.3 registered equal-weight combination",
                       "weights":"equal","n_components":len(s)}
    for s in soup_sets:
        cid="SOUP13_"+"+".join(x.replace("C012_SOUP_622_633","SOUP") for x in s)
        outp=os.path.join(sdir,f"{cid}.npz")
        ep.weight_soup([os.path.join(_REPO,cands[x]["checkpoint_path"]) for x in s],outp)
        comb[cid]={"candidate_id":cid,"candidate_type":"weight_soup",
                   "component_ids":s,"component_sha256":[cands[x]["checkpoint_sha256"] for x in s],
                   "checkpoint_path":os.path.relpath(outp,_REPO),"checkpoint_sha256":sha(outp),
                   "architecture_id":ARCH,"trainable":True,"deployable":True,
                   "source_contract":"c013","source_evidence":"§8.4 registered equal soup",
                   "weights":"equal","n_components":len(s)}
    return comb

def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(ART,exist_ok=True); os.makedirs(LOGD,exist_ok=True)
    checks=[]
    def rec(n,ok,d=""): checks.append({"check":n,"ok":bool(ok),"detail":str(d)[:300]})
    mach=machine()
    imm={}
    for f in IMMUT:
        root=os.path.join(_REPO,"contracts",f); files={}
        for dp,_dn,fns in os.walk(root):
            for fn in fns:
                p=os.path.join(dp,fn); files[os.path.relpath(p,_REPO)]=sha(p)
        imm[f"{f.split('_')[0]}_files"]=files
    imm["folders"]=IMMUT; imm["counts"]={k:len(v) for k,v in imm.items() if k.endswith("_files")}
    json.dump(imm,open(os.path.join(ART,"immutability_verification.json"),"w"),indent=2)

    from cg import c009_eval as ce, c011_eval_core as cc
    from cg.teachers import make_fresh
    deck=make_fresh("dragapult",ce.SOURCES).deck; fp=ce.deck_fingerprint(deck)
    c10=json.load(open(os.path.join(_REPO,"contracts","c010_fixed_deck_rl_loop_v2","results",
                                    "artifacts","experiment_registry.json")))
    rec("frozen_deck_fingerprint_matches",fp==c10["frozen_deck_fingerprint"],fp)
    rec("deck_is_60_cards",len(deck)==60,len(deck))
    c11=json.load(open(os.path.join(C011A,"evaluation_candidate_registry.json")))
    rec("frozen_teacher_hash_matches",cc.teacher_source_sha256()==c11["T_teacher"]["checkpoint_sha256"])
    cands=resolve_candidates()
    bad=[c for c,m in cands.items() if not os.path.exists(os.path.join(_REPO,m["checkpoint_path"]))]
    rec("every_required_candidate_resolved_and_present",not bad,bad)
    req={"C012_SOUP_622_633","S611","S622","S633","P0_711","P1_822","P1_833"}
    rec("all_contract_required_candidates_registered",req<=set(cands),sorted(req-set(cands)))
    rec("historical_incumbents_registered",
        any(c.startswith("C010") or c.startswith("C008") for c in cands),
        [c for c in cands if c.startswith(("C010","C008"))])
    # c012 final panel reproduces from raw games (§3)
    from cg import noninf_stats as ns
    per=defaultdict(lambda: defaultdict(lambda: {0:[],1:[]}))
    for l in gzip.open(os.path.join(C012A,"evaluation_games.jsonl.gz"),"rt"):
        g=json.loads(l)
        if g["phase"]=="final" and g["score"] is not None:
            per[g["candidate_id"]][g["opponent_id"]][g["seat"]].append(g["score"])
    bas=json.load(open(os.path.join(C012A,"best_agent_selection.json")))
    mism=[]
    for cid,s in (bas.get("final_summaries") or {}).items():
        for opp,m in s["per_opponent"].items():
            v=per[cid][opp]
            if not (v[0] and v[1]): mism.append(f"{cid}|{opp}:missing"); continue
            if abs(ns.seat_balanced_point(v[0],v[1])-m["point"])>1e-9: mism.append(f"{cid}|{opp}")
    rec("c012_final_panel_reproduces_from_raw_games",not mism,mism[:4])
    for c in IMMUT:
        sp=os.path.join(_REPO,"contracts",c,"results","STATUS.json")
        if os.path.exists(sp):
            rec(f"{c.split('_')[0]}_status_pass",json.load(open(sp)).get("status")=="PASS")
    rec("cuda_available",mach["cuda_available"])
    rec("disk_free_ge_100gib",mach["disk_free_gib"]>=100,mach["disk_free_gib"])
    rec("vram_free_ge_8gib",(mach.get("vram_free_mib") or 0)>=8*1024,mach.get("vram_free_mib"))

    comb=build_combinations(cands)
    json.dump({"note":"§7 frozen candidate registry. Every id and hash resolved from the "
                      "earlier contracts' own registries, never from a filename.",
               "architecture_id":ARCH,"n_candidates":len(cands),"candidates":cands},
              open(os.path.join(ART,"candidate_registry.json"),"w"),indent=2)
    json.dump({"note":"§8 registered combination families, frozen BEFORE any combination "
                      "result exists. Equal weights only; no post-result tuning (§8.4).",
               "families":{"single":7,"online_logit":10,"online_probability":10,
                           "weight_soup":len([c for c in comb.values() if c['candidate_type']=='weight_soup'])},
               "n_combinations":len(comb),"combinations":comb},
              open(os.path.join(ART,"combination_registry.json"),"w"),indent=2)
    dep={"contract":"c013","all_ok":all(c["ok"] for c in checks),"n_checks":len(checks),
         "n_failed":sum(1 for c in checks if not c["ok"]),"frozen_deck_fingerprint":fp,
         "teacher_source_sha256":cc.teacher_source_sha256(),"machine":mach,
         "final_commits":{c:subprocess.run(["git","-C",_REPO,"log","-1","--format=%H","--",
             f"contracts/{c}"],capture_output=True,text=True).stdout.strip() or None for c in IMMUT},
         "checks":checks}
    json.dump(dep,open(os.path.join(ART,"dependency_verification.json"),"w"),indent=2)
    with open(os.path.join(LOGD,"dependency_verification.txt"),"w") as fh:
        fh.write("c013 AC-01 dependency / immutability\n\n")
        for c in checks: fh.write(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}  {c['detail']}\n")
        fh.write(f"\nimmutability baseline: {imm['counts']}\nmachine: {json.dumps(mach)}\n")
        fh.write(f"\nALL_OK = {dep['all_ok']}\n")
    with open(os.path.join(LOGD,"combination_registry.txt"),"w") as fh:
        fh.write(f"candidates: {len(cands)}\n")
        for c,m in sorted(cands.items()): fh.write(f"  {c:22s} {m['candidate_type']:14s} {m['checkpoint_sha256'][:12]}\n")
        fh.write(f"\ncombinations: {len(comb)}\n")
        for c,m in sorted(comb.items()): fh.write(f"  {c:34s} {m['candidate_type']:15s} n={m['n_components']} {m['checkpoint_sha256'][:12]}\n")
    print(json.dumps({"all_ok":dep["all_ok"],"n_checks":dep["n_checks"],"n_failed":dep["n_failed"],
                      "candidates":len(cands),"combinations":len(comb),
                      "by_type":{t:sum(1 for m in comb.values() if m['candidate_type']==t)
                                 for t in ("online_ensemble","weight_soup")}},indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
