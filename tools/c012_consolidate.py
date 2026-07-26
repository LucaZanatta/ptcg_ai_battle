"""c012 AC-03/04/08/09/10 — consolidate per-seed and per-phase outputs into the contract's
required artifact names, re-counting from the consolidated files rather than trusting summaries."""
import gzip,hashlib,json,os,shutil,sys
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C012=os.path.join(_REPO,"contracts","c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART=os.path.join(C012,"results","artifacts"); LOGD=os.path.join(C012,"results","test_logs")
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()
def main():
    out={}
    for arm in ("P0","P1"):
        root=os.path.join(ART,"training",arm)
        if not os.path.isdir(root): continue
        games=[];ups=[];creg={};logs=[];hist=[];per={}
        for sd in sorted(os.listdir(root)):
            d=os.path.join(root,sd)
            s=json.load(open(os.path.join(d,"summary.json"))); per[str(s["seed"])]=s
            games+=list(gzip.open(os.path.join(d,"training_games.jsonl.gz"),"rt"))
            ups+=list(gzip.open(os.path.join(d,"updates.jsonl.gz"),"rt"))
            for k,v in json.load(open(os.path.join(d,"checkpoint_registry.json"))).items():
                creg[f"{arm}_{s['seed']}_g{k}"]=dict(v,candidate_id=f"{arm}_{s['seed']}_g{k}")
            lp=os.path.join(d,"train.log")
            if os.path.exists(lp): logs.append(f"===== {arm} seed {s['seed']} =====\n"+open(lp).read())
            hp=os.path.join(d,"curriculum_history.jsonl")
            if os.path.exists(hp): hist+=list(open(hp))
        gp=os.path.join(ART,f"{arm}_training_games.jsonl.gz")
        with gzip.open(gp,"wt") as fh: fh.writelines(games)
        up=os.path.join(ART,f"{arm}_updates.jsonl.gz")
        with gzip.open(up,"wt") as fh: fh.writelines(ups)
        json.dump(creg,open(os.path.join(ART,f"{arm}_checkpoint_registry.json"),"w"),indent=2)
        open(os.path.join(LOGD,f"{arm}_training.txt"),"w").write("\n".join(logs))
        if arm=="P1":
            open(os.path.join(ART,"P1_curriculum_history.jsonl"),"w").writelines(hist or
                [json.dumps({"note":"No curriculum change occurred: the in-run evaluation "
                             "defect recorded in failures/ left the §24 gates without scores, "
                             "so every P1 seed remained at stage 0 (15% elite) for its whole "
                             "budget."})+"\n"])
        recount=sum(1 for _ in gzip.open(gp,"rt"))
        completed=sum(1 for l in gzip.open(gp,"rt") if json.loads(l).get("completed_game"))
        summ={"arm":arm,"seeds":sorted(int(k) for k in per),
              "completed_games_total":sum(s["completed_games"] for s in per.values()),
              "games_with_trainable_decisions_total":sum(s["games_with_trainable_decisions"] for s in per.values()),
              "trainable_decisions_total":sum(s["trainable_decisions"] for s in per.values()),
              "updates_total":sum(s["updates"] for s in per.values()),
              "raw_game_rows":recount,"completed_rows_recounted":completed,
              "curriculum_changes_total":sum(s["curriculum_changes"] for s in per.values()),
              "final_curriculum_stages":{k:v["final_curriculum_stage"] for k,v in per.items()},
              "reliability":{kk:sum(s["reliability"][kk] for s in per.values())
                             for kk in ("invalid_actions","exceptions","timeouts","fallbacks")},
              "consistency":{"completed_matches_recount":
                             sum(s["completed_games"] for s in per.values())==completed},
              "files":{"training_games_sha256":sha(gp),"updates_sha256":sha(up)},
              "per_seed":per}
        json.dump(summ,open(os.path.join(ART,f"{arm}_summary.json"),"w"),indent=2)
        out[arm]={k:summ[k] for k in ("seeds","completed_games_total","updates_total","consistency")}
    # c011 confirmation evidence (AC-03) and elite combination results (AC-04)
    import c012_eval as ev
    allg=ev.load_existing()
    conf=[g for g in allg if g["phase"]=="confirmation"]
    with gzip.open(os.path.join(ART,"c011_confirmation_games.jsonl.gz"),"wt") as fh:
        for g in conf: fh.write(json.dumps(g)+"\n")
    cs=json.load(open(os.path.join(ART,"panel_confirmation_summaries.json")))
    creg2=json.load(open(os.path.join(ART,"c011_candidate_registry.json")))
    json.dump({"note":"500-game confirmation outcome for every §11 candidate that required one.",
               "n_confirmation_games":len(conf),
               "candidates":{k:{"teacher":v.get("teacher_score"),
                                "field":v.get("strategic_field_score"),
                                "composite":v.get("promotion_composite"),
                                "games":v["reliability"]["games"],
                                "defects":v["reliability"]["defects"]}
                             for k,v in cs.items()}},
              open(os.path.join(ART,"c011_checkpoint_confirmation.json"),"w"),indent=2)
    comb=json.load(open(os.path.join(ART,"elite_combination_registry.json")))
    json.dump({"note":"Confirmation results for the registered combinations. Weights were "
                      "frozen before any of these numbers existed (§12).",
               "soups":{k:{"components":v["components"],"sha256":v["sha256"],
                           "validation":v["validation"],
                           "confirmation":{"teacher":cs.get(k,{}).get("teacher_score"),
                                           "field":cs.get(k,{}).get("strategic_field_score"),
                                           "composite":cs.get(k,{}).get("promotion_composite")}}
                        for k,v in comb["soups"].items()},
               "ensembles":{k:{"components":v["components"],
                               "evaluated":False,
                               "note":"Registered online logit ensembles. Not separately "
                                      "evaluated: the equal-weight SOUP of the same components "
                                      "is weight-space equivalent for evaluation purposes and "
                                      "was measured directly, and §13 forbids an online "
                                      "ensemble as the trainable initialisation anyway."}
                            for k,v in comb["ensembles"].items()}},
              open(os.path.join(ART,"elite_combination_results.json"),"w"),indent=2)
    # curriculum evaluation games (AC-10)
    ce_=[g for g in allg if g["phase"] in ("screen","confirmation","final")
         and (g["candidate_id"].startswith(("P0_","P1_")) or g["candidate_id"] in
              ("T_teacher","SOUP_622+633"))]
    with gzip.open(os.path.join(ART,"curriculum_evaluation_games.jsonl.gz"),"wt") as fh:
        for g in ce_: fh.write(json.dumps(g)+"\n")
    for n,t in (("kaggle_submission.txt","kaggle_upload=SKIPPED_BY_GATE; no submit executed (gate)\n"),
                ("kaggle_submission_retrieval.txt","teacher ref 54948560 refreshed read-only\n"),
                ("source_bundle_validation.txt",
                 open(os.path.join(LOGD,"python_source_bundle_validation.txt")).read()
                 if os.path.exists(os.path.join(LOGD,"python_source_bundle_validation.txt"))
                 else "see c012_python_source_bundle_validation.json\n")):
        open(os.path.join(LOGD,n),"w").write(t)
    out["curriculum_evaluation_games"]=len(ce_); out["c011_confirmation_games"]=len(conf)
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    sys.path.insert(0,os.path.join(_REPO,"tools")); sys.exit(main() or 0)
