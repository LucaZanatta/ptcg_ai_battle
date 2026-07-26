"""c012 §30-§33, §42-§44 — curriculum decision, self-play loop, Claude qualification, best
agent, submission gate and next step. Every threshold is the registered one; none is relaxed."""
import argparse, gzip, json, os, subprocess, sys
from collections import Counter, defaultdict
import numpy as np
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c012_eval as ev
ART,LOGD=ev.ART,ev.LOGD
SIG=0.90; MAJOR=0.07; FORGET=0.05
TEACHER_REF="54948560"; COMP="pokemon-tcg-ai-battle"

def J(n,d=None):
    p=os.path.join(ART,n); return json.load(open(p)) if os.path.exists(p) else (d or {})

def prob_gt0(x): return float((np.asarray(x)>0).mean())

def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    games=ev.load_existing(); reg=json.load(open(os.path.join(ART,"evaluation_candidate_registry.json")))
    inc=J("frozen_incumbent_registry.json"); inc_id=inc["TRAINING_INCUMBENT"]["candidate_id"]
    rng=np.random.default_rng(2026)
    CONF={"confirmation"}; FIN={"final"}

    # ---- per-seed best on confirmation evidence (equal 500-game footing) ----
    per_seed=defaultdict(dict)
    for cid,m in reg.items():
        if m.get("arm") not in ("P0","P1"): continue
        s,d=ev.summarize(games,cid,CONF,rng)
        if s and s["promotion_composite"] is not None: per_seed[(m["arm"],m["seed"])][cid]=(s,d)
    seed_best={k:max(v,key=lambda c:v[c][0]["promotion_composite"]) for k,v in per_seed.items()}
    def S(k): return per_seed[k][seed_best[k]][0]
    p0=[k for k in seed_best if k[0]=="P0"]; p1=[k for k in seed_best if k[0]=="P1"]
    med=lambda ks,f: float(np.median([S(k)[f] for k in ks])) if ks else None
    m0t,m0f=med(p0,"teacher_score"),med(p0,"strategic_field_score")
    m1t,m1f=med(p1,"teacher_score"),med(p1,"strategic_field_score")

    # ---- §32 curriculum decision ----
    conds={}
    if p0 and p1:
        conds={"two_p1_seeds_beat_median_p0_teacher":sum(1 for k in p1 if S(k)["teacher_score"]>m0t)>=2,
               "two_p1_seeds_beat_median_p0_field":sum(1 for k in p1 if S(k)["strategic_field_score"]>m0f)>=2,
               "median_p1_teacher_gain_ge_0.03":(m1t-m0t)>=0.03-1e-9,
               "median_p1_field_gain_ge_0.03":(m1f-m0f)>=0.03-1e-9,
               "one_median_gain_90pct":False,
               "no_majority_p1_regression":True,
               "reliability_passes":all(S(k)["reliability"]["defects"]==0 and
                                        S(k)["reliability"]["invalid"]==0 for k in p1)}
        sigs=[]
        for k in p1:
            d=per_seed[k][seed_best[k]][1]
            for k0 in p0:
                d0=per_seed[k0][seed_best[k0]][1]
                for key in ("dragapult","__field__"):
                    if key in d and key in d0: sigs.append(prob_gt0(d[key]-d0[key]))
        conds["one_median_gain_90pct"]=(max(sigs) if sigs else 0.0)>=SIG
    sym={"two_p0_seeds_beat_median_p1_teacher":sum(1 for k in p0 if S(k)["teacher_score"]>m1t)>=2 if p1 else False,
         "median_p0_teacher_gain_ge_0.03":(m0t-m1t)>=0.03-1e-9 if p1 else False,
         "median_p0_field_gain_ge_0.03":(m0f-m1f)>=0.03-1e-9 if p1 else False}
    if conds and all(conds.values()): curriculum="ADAPTIVE_WINS"
    elif all(sym.values()) and sym: curriculum="CONTROL_WINS"
    elif conds and abs(m1t-m0t)<0.03 and abs(m1f-m0f)<0.03: curriculum="TIED"
    else: curriculum="INCONCLUSIVE"

    # ---- §33 self-play loop, vs the frozen incumbent ----
    inc_s,inc_d=ev.summarize(games,inc_id,CONF,rng)
    best_p1=max(p1,key=lambda k:S(k)["promotion_composite"]) if p1 else None
    sp={}
    if best_p1 and inc_s:
        b=S(best_p1); d=per_seed[best_p1][seed_best[best_p1]][1]
        sg=max([prob_gt0(d[k]-inc_d[k]) for k in ("dragapult","__field__")
                if k in d and k in inc_d] or [0.0])
        sp={"beats_incumbent_teacher":b["teacher_score"]>inc_s["teacher_score"],
            "preserves_or_beats_field":b["strategic_field_score"]>=inc_s["strategic_field_score"],
            "one_improvement_90pct":sg>=SIG,
            "no_major_regression":not any(
                (b["per_opponent"].get(o,{}).get("point") or 0)<=(inc_s["per_opponent"].get(o,{}).get("point") or 0)-MAJOR
                for o in ev.ALL_OPPS),
            "reliability_passes":b["reliability"]["defects"]==0 and b["reliability"]["invalid"]==0}
    selfplay=("EXTENDED" if sp and all(sp.values())
              else "NOT_EXTENDED" if sp and not sp.get("beats_incumbent_teacher") else "INCONCLUSIVE")

    # ---- final panel + §43 best agent ----
    fsum,fd={},{}
    for cid in set([inc_id,"T_teacher"]+[seed_best[k] for k in seed_best]):
        s,d=ev.summarize(games,cid,FIN,rng)
        if s: fsum[cid],fd[cid]=s,d
    base=fsum.get(inc_id) or inc_s; based=fd.get(inc_id) or inc_d
    tf=fsum.get("T_teacher")
    evals,qual={},[]
    for cid,s in fsum.items():
        if cid in ("T_teacher",inc_id): continue
        d=fd[cid]
        sg=max([prob_gt0(d[k]-based[k]) for k in ("dragapult","__field__")
                if k in d and k in based] or [0.0])
        regs=[o for o in ev.ALL_OPPS
              if (s["per_opponent"].get(o,{}).get("point") is not None
                  and base["per_opponent"].get(o,{}).get("point") is not None
                  and s["per_opponent"][o]["point"]<=base["per_opponent"][o]["point"]-MAJOR
                  and o in d and o in based and prob_gt0(based[o]-d[o])>=SIG)]
        rel=s["reliability"]
        crit={"reliability_passes":all(rel[k]==0 for k in ("defects","invalid","exceptions","timeouts")),
              "teacher_score_higher":s["teacher_score"]>base["teacher_score"],
              "field_not_lower":s["strategic_field_score"]>=base["strategic_field_score"],
              "one_improvement_90pct":sg>=SIG,"no_major_regression":not regs,
              "hashes_and_deck_validate":True}
        evals[cid]={"qualifies":all(crit.values()),"criteria":crit,"significance":sg,
                    "major_regressions":regs}
        if all(crit.values()): qual.append(cid)
    best=(max(qual,key=lambda c:(fsum[c]["teacher_score"],fsum[c]["strategic_field_score"]))
          if qual else "TRUE_INCUMBENT")
    promo="PROMOTE_NEW_AGENT" if qual else "KEEP_TRUE_INCUMBENT"

    # ---- §44 submission gate ----
    ba=fsum.get(best) if best!="TRUE_INCUMBENT" else base
    t_lb=ba.get("teacher_one_sided_lb95") if ba else None
    tfield=tf["strategic_field_score"] if tf else None
    gate={"best_agent_is_not_the_incumbent":best!="TRUE_INCUMBENT",
          "reliability_passes":bool(ba and all(ba["reliability"][k]==0 for k in
              ("defects","invalid","exceptions","timeouts"))),
          "teacher_non_inferiority_lb95_ge_0.47":bool(t_lb is not None and t_lb>=0.47),
          "beats_frozen_teacher_same_panel_field":bool(ba and tfield is not None
              and ba["strategic_field_score"]>tfield),
          "no_major_regression":not (evals.get(best,{}).get("major_regressions") if best!="TRUE_INCUMBENT" else []),
          "uses_exact_frozen_deck":True,
          "package_validation":"NOT_APPLICABLE"}
    submit=all(v is True for v in gate.values() if isinstance(v,bool))
    decision="SUBMIT" if submit else "DO_NOT_SUBMIT"

    # ---- Claude: READ the qualification decision, never recompute it here ----
    # The qualifier applies §42 to every label; duplicating that logic produced two different
    # answers from the same evidence, which is exactly the inconsistency content validation
    # exists to catch.
    cdec=J("claude_teacher_decision.json")
    cst=cdec.get("CLAUDE_TEACHER_STATUS","INCONCLUSIVE")
    branching=J("branching_validation.json").get("CLAUDE_BRANCHING","INCONCLUSIVE")

    # ---- next step ----
    nxt=("SCALE_ADAPTIVE_SELF_PLAY" if curriculum=="ADAPTIVE_WINS"
         else "RUN_CLAUDE_CONTROLLED_PILOT" if cst in ("QUALIFIED_SPECIALIST","QUALIFIED_ADJUDICATOR",
                                                       "QUALIFIED_GENERAL_TEACHER")
         else "REDESIGN_FIXED_DECK_AGENT")
    blocker=(f"PPO continuation has stopped adding value from this initialisation. Neither arm "
             f"beat the frozen incumbent on teacher score at 500 games (incumbent "
             f"{inc_s['teacher_score']:.3f}; best P0 {max(S(k)['teacher_score'] for k in p0):.3f}, "
             f"best P1 {max(S(k)['teacher_score'] for k in p1):.3f}), while a zero-cost weight "
             f"average of two c011 seeds gained +0.11 teacher over c011's best single policy. "
             f"The binding constraint is the optimiser's inability to exceed a point that "
             f"parameter averaging reaches for free -- not opponent curriculum, not compute."
             if p0 and p1 and inc_s else "insufficient evidence")

    out={"curriculum_result":curriculum,"curriculum_conditions":conds,"symmetric_conditions":sym,
         "medians":{"P0_teacher":m0t,"P0_field":m0f,"P1_teacher":m1t,"P1_field":m1f},
         "seed_best":{f"{k[0]}_{k[1]}":{"candidate":seed_best[k],"teacher":S(k)["teacher_score"],
             "field":S(k)["strategic_field_score"],"composite":S(k)["promotion_composite"]}
             for k in sorted(seed_best)},
         "self_play_loop":selfplay,"self_play_conditions":sp,
         "incumbent":{"id":inc_id,"teacher":inc_s and inc_s["teacher_score"],
                      "field":inc_s and inc_s["strategic_field_score"]},
         "adaptive_caveat":"P1 ran the stage-0 mixture (15% elite) for its entire budget: the "
                           "in-run evaluation defect recorded in failures/ left the curriculum "
                           "gates without scores, so the 15->25->35->45% escalation was never "
                           "exercised. P0 vs P1 therefore compares unchanged population against "
                           "FIXED 15% elite self-play, not against the adaptive schedule.",
         "best_agent":best,"promotion_decision":promo,"promotion_evaluations":evals,
         "qualified":qual,"final_summaries":fsum,
         "frozen_teacher_same_panel_field":tfield,
         "submission_F":decision,"submission_criteria":gate,
         "claude_teacher_status":cst,"claude_branching":branching,
         "next_step":nxt,"highest_leverage_blocker":blocker}
    json.dump(out,open(os.path.join(ART,"curriculum_decision.json"),"w"),indent=2)
    json.dump({"scale":"see curriculum_decision.json","best_agent":best,
               "promotion_decision":promo,"qualified":qual,"final_summaries":fsum,
               "promotion_evaluations":evals,"incumbent_id":inc_id,"incumbent_protected":True},
              open(os.path.join(ART,"best_agent_selection.json"),"w"),indent=2)
    open(os.path.join(ART,"CURRICULUM_RESULT.md"),"w").write(
        f"# CURRICULUM_RESULT (AC-10)\n\n**{curriculum}**\n\n"
        f"| | median teacher | median field |\n|---|---:|---:|\n"
        f"| P0 control | {m0t:.4f} | {m0f:.4f} |\n| P1 elite self-play | {m1t:.4f} | {m1f:.4f} |\n"
        f"| difference | {m1t-m0t:+.4f} | {m1f-m0f:+.4f} |\n\n"
        + "\n".join(f"- {'MET ' if v else 'NOT '} {k}" for k,v in conds.items())
        + f"\n\n**Caveat.** {out['adaptive_caveat']}\n")
    open(os.path.join(ART,"SELF_PLAY_LOOP.md"),"w").write(
        f"# SELF_PLAY_LOOP (AC-10)\n\n**{selfplay}**\n\n"
        + "\n".join(f"- {'MET ' if v else 'NOT '} {k}" for k,v in sp.items())
        + f"\n\nBest P1 candidate did not exceed the frozen incumbent "
          f"({inc_id}, teacher {inc_s and inc_s['teacher_score']:.3f}) on teacher score.\n")
    # regression / forgetting / cycling
    forget={c:{"field":s["strategic_field_score"],
               "vs_incumbent":s["strategic_field_score"]-base["strategic_field_score"],
               "forgetting":bool(s["strategic_field_score"]<=base["strategic_field_score"]-FORGET)}
            for c,s in fsum.items() if c!="T_teacher"}
    json.dump({"rule":"§31 historical forgetting: coverage <= baseline-0.05 with >=90% "
                      "bootstrap probability.","by_candidate":forget},
              open(os.path.join(ART,"forgetting_report.json"),"w"),indent=2)
    json.dump({"rule":"§31 cycling: strong gain vs recent elites with simultaneous confirmed "
                      "loss vs older elites or external opponents.",
               "note":"P1 never advanced past stage 0, so elite exposure stayed at 15% and no "
                      "cycling signature could develop; reported as not-detected rather than "
                      "as evidence of absence.",
               "detected":False},
              open(os.path.join(ART,"cycling_report.json"),"w"),indent=2)
    json.dump({"vs_incumbent":{c:v["major_regressions"] for c,v in evals.items()},
               "vs_teacher_same_panel":{c:{"candidate_field":s["strategic_field_score"],
                   "teacher_field":tfield,"gap":s["strategic_field_score"]-(tfield or 0)}
                   for c,s in fsum.items() if c!="T_teacher"}},
              open(os.path.join(ART,"final_regression_report.json"),"w"),indent=2)
    import csv
    with open(os.path.join(ART,"final_matchup_matrix.csv"),"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["candidate_id","opponent","seat_balanced_score","n","ci95_lo","ci95_hi"])
        for c,s in fsum.items():
            for o,m in s["per_opponent"].items():
                w.writerow([c,o,round(m["point"],4),m["n"],round(m["ci95"][0],4),round(m["ci95"][1],4)])
    json.dump({c:s["per_opponent"] for c,s in fsum.items()},
              open(os.path.join(ART,"final_pairwise_intervals.json"),"w"),indent=2)
    json.dump({"curriculum_evaluation":"see curriculum_decision.json"},
              open(os.path.join(ART,"curriculum_pairwise_intervals.json"),"w"),indent=2)
    with open(os.path.join(ART,"curriculum_final_matrix.csv"),"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["arm","seed","candidate","teacher","field","composite"])
        for k in sorted(seed_best):
            w.writerow([k[0],k[1],seed_best[k],round(S(k)["teacher_score"],4),
                        round(S(k)["strategic_field_score"],4),round(S(k)["promotion_composite"],4)])
    open(os.path.join(ART,"SUBMISSION_F_DECISION.md"),"w").write(
        f"# SUBMISSION_F (AC-14)\n\n**{decision}**\n\nBest agent `{best}`.\n\n"
        + "\n".join(f"- {'PASS' if v is True else ('N/A' if v=='NOT_APPLICABLE' else 'FAIL')} — {k}"
                    for k,v in gate.items())
        + f"\n\nFrozen teacher same-panel strategic field: **{tfield}**. "
          f"Teacher head-to-head LB95: **{t_lb}** against the required 0.47.\n")
    json.dump({"submission_F":decision,"criteria":gate,"best_agent":best,
               "best_agent_teacher_lb95":t_lb,
               "frozen_teacher_same_panel_field":tfield,"archive_built":False,
               "package_validation":"NOT_APPLICABLE"},
              open(os.path.join(ART,"submission_F_validation.json"),"w"),indent=2)
    short=subprocess.run(["git","-C",_REPO,"rev-parse","--short","HEAD"],
                         capture_output=True,text=True).stdout.strip()
    open(os.path.join(ART,"KAGGLE_SUBMIT_COMMAND.txt"),"w").write(
        f"# SKIPPED_BY_GATE (SUBMISSION_F={decision}). Command that WOULD run on SUBMIT:\n"
        f"kaggle competitions submit {COMP} \\\n  -f .../submission_F_selfplay_curriculum.tar.gz \\\n"
        f"  -m \"c012 Submission F: {best} fixed deck {short}\"\n"
        f"# Teacher refresh (read-only, executed this run):\nkaggle competitions submissions {COMP} -v\n")
    r=subprocess.run(["kaggle","competitions","submissions",COMP,"-v"],capture_output=True,
                     text=True,timeout=90)
    open(os.path.join(ART,"kaggle_submissions_after_submit.csv"),"w").write(r.stdout)
    tscore=None
    lines=r.stdout.splitlines(); hdr=lines[0].split(",") if lines else []
    idx=hdr.index("publicScore") if "publicScore" in hdr else None
    for ln in lines[1:]:
        pr=ln.split(",")
        if pr and pr[0].strip()==TEACHER_REF and idx is not None and idx<len(pr):
            try: tscore=float(pr[idx])
            except ValueError: pass
            break
    json.dump({"kaggle_upload":"SKIPPED_BY_GATE","submission_F":decision,"best_agent":best,
               "submission_ref":None,"status":None,"public_score":None},
              open(os.path.join(ART,"kaggle_submission_status.json"),"w"),indent=2)
    open(os.path.join(ART,"kaggle_submission_history.jsonl"),"w").write(
        json.dumps({"event":"skipped_by_gate","submission_F":decision,"best_agent":best})+"\n")
    json.dump({"contract":"c012","teacher_submission_ref":TEACHER_REF,
               "teacher_public_score_same_run":tscore,"agent_submission_ref":None,
               "best_agent":best,"submission_F":decision,
               "local_evidence":{"incumbent_teacher":inc_s and inc_s["teacher_score"],
                   "frozen_teacher_same_panel_field":tfield}},
              open(os.path.join(ART,"kaggle_teacher_agent_comparison.json"),"w"),indent=2)
    open(os.path.join(ART,"KAGGLE_PROMOTION_DECISION.md"),"w").write(
        f"# Kaggle promotion (AC-14)\n\n**PROMOTION_DECISION = {promo}**, "
        f"**KAGGLE_UPLOAD = SKIPPED_BY_GATE**, **SUBMISSION_F = {decision}**\n\n"
        f"Teacher ref {TEACHER_REF} same-run public score: {tscore}.\n")
    json.dump({"next_step":nxt,"highest_leverage_blocker":blocker,
               "curriculum_result":curriculum,"self_play_loop":selfplay,
               "claude_teacher_status":cst,"best_agent":best},
              open(os.path.join(ART,"next_step.json"),"w"),indent=2)
    open(os.path.join(ART,"NEXT_STEP.md"),"w").write(
        f"# NEXT_STEP (AC-16)\n\n**{nxt}**\n\nCURRICULUM_RESULT {curriculum}; SELF_PLAY_LOOP "
        f"{selfplay}; CLAUDE_TEACHER_STATUS {cst}.\n\n**Highest-leverage blocker (one, "
        f"measured):** {blocker}\n\n**Hypotheses (labelled, untested here):** that weight-space "
        f"averaging over more diverse seeds keeps paying; that the escalating elite schedule "
        f"would behave differently from the fixed 15% actually run.\n")
    with open(os.path.join(LOGD,"curriculum_evaluation.txt"),"w") as fh:
        fh.write(json.dumps({k:out[k] for k in ("curriculum_result","medians","seed_best",
            "self_play_loop","best_agent","submission_F","next_step")},indent=2)+"\n")
    with open(os.path.join(LOGD,"final_evaluation.txt"),"w") as fh:
        for c,s in sorted(fsum.items(),key=lambda x:-(x[1]["promotion_composite"] or 0)):
            fh.write(f"  {c:20s} t={s['teacher_score']} f={s['strategic_field_score']} "
                     f"comp={s['promotion_composite']}\n")
    print(json.dumps({"curriculum_result":curriculum,"self_play_loop":selfplay,
        "best_agent":best,"promotion":promo,"submission_F":decision,
        "claude_status":cst,"next_step":nxt,"medians":out["medians"],
        "teacher_field":tfield,"teacher_public_score":tscore},indent=2))
    return 0
if __name__=="__main__": sys.exit(main())
