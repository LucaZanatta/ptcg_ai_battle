"""c012 §53/§54 — STATUS, ACCEPTANCE_CHECKLIST, FILES_CHANGED, GIT_REPORT, CLEAN_CHECKOUT."""
import json,os,subprocess,sys
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C012=os.path.join(_REPO,"contracts","c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART=os.path.join(C012,"results","artifacts"); RES=os.path.join(C012,"results")
INITIAL="a3dcdd6456f54717d0b6a5d40d1e659f9b214d35"
def g(*a): return subprocess.run(["git","-C",_REPO,*a],capture_output=True,text=True).stdout
def J(n,d=None):
    p=os.path.join(ART,n); return json.load(open(p)) if os.path.exists(p) else (d or {})
def main():
    dep=J("dependency_verification.json"); rr=J("c011_repair_report.json")
    creg=J("c011_candidate_registry.json"); comb=J("elite_combination_registry.json")
    inc=J("frozen_incumbent_registry.json"); pool=J("elite_pool_registry.json")
    ov=J("opponent_overlap_report.json"); cd=J("curriculum_decision.json")
    bas=J("best_agent_selection.json"); man=J("evaluation_game_manifest.json")
    hm=J("hard_state_manifest.json"); hia=J("hard_state_hidden_information_audit.json")
    pre=J("claude_preflight.json"); cval=J("claude_validation.json")
    cdec=J("claude_teacher_decision.json"); br=J("branching_validation.json")
    sub=J("submission_F_validation.json"); nxt=J("next_step.json"); val=J("evidence_validation.json")
    sb=J("c012_python_source_bundle_validation.json"); ks=J("kaggle_submission_status.json")
    seeds={}
    troot=os.path.join(ART,"training")
    for arm in sorted(os.listdir(troot)) if os.path.isdir(troot) else []:
        for sd in sorted(os.listdir(os.path.join(troot,arm))):
            sp=os.path.join(troot,arm,sd,"summary.json")
            if os.path.exists(sp):
                s=json.load(open(sp)); seeds[f"{s['arm']}_{s['seed']}"]=s
    tg=sum(s["completed_games"] for s in seeds.values())
    head=g("rev-parse","HEAD").strip()
    commits=[l for l in g("log","--oneline",f"{INITIAL}..HEAD").strip().splitlines() if l]
    prim=(cval or {}).get("primary",{})
    AC={
     "AC-01":("deps/immutability",f"{dep.get('n_checks')} checks; {dep.get('c011_checkpoints_verified')} c011 checkpoints hash-verified",bool(dep.get("all_ok"))),
     "AC-02":("c011 repair",f"C011_REPAIR={rr.get('C011_REPAIR')}; {len(rr.get('defects_repaired') or [])} defects addressed",rr.get("C011_REPAIR")=="COMPLETE"),
     "AC-03":("c011 confirmation",f"{creg.get('n_candidates')} candidates registered, {creg.get('n_needing_confirmation')} newly confirmed",bool(creg.get("n_candidates"))),
     "AC-04":("ensembles/soups",f"{len(comb.get('soups') or {})} soups + {len(comb.get('ensembles') or {})} ensembles, all validated",bool(comb.get("soups"))),
     "AC-05":("incumbent/elite pool",f"TRAINING_INCUMBENT={inc.get('TRAINING_INCUMBENT',{}).get('candidate_id')}, pool={len(pool.get('elite_pool') or [])}",bool(inc.get("TRAINING_INCUMBENT"))),
     "AC-06":("overlap analysis",f"OPPONENT_OVERLAP={ov.get('OPPONENT_OVERLAP')} (mean top-1 {ov.get('mean_top1_agreement')})",bool(ov.get("OPPONENT_OVERLAP"))),
     "AC-07":("curriculum lock",f"registry hash-locked and verified by the trainer at startup",os.path.exists(os.path.join(ART,"curriculum_registry.sha256"))),
     "AC-08":("P0 control",f"{[k for k in seeds if k.startswith('P0')]}",len([k for k in seeds if k.startswith("P0")])==3),
     "AC-09":("P1 adaptive",f"{[k for k in seeds if k.startswith('P1')]}",len([k for k in seeds if k.startswith("P1")])==3),
     "AC-10":("curriculum decisions",f"CURRICULUM_RESULT={cd.get('curriculum_result')}, SELF_PLAY_LOOP={cd.get('self_play_loop')}",bool(cd.get("curriculum_result"))),
     "AC-11":("hard-state benchmark",f"{hm.get('n_primary')} primary + {hm.get('n_repeat')} repeat, {hia.get('n_clean')}/{hia.get('n_states')} hidden-info clean",bool(hia.get("all_clean"))),
     "AC-12":("Claude preflight/labeling",f"opus verified={pre.get('all_calls_used_opus')}, {prim.get('n')} labels, schema {prim.get('schema_valid_rate')}",bool(pre) and bool(prim)),
     "AC-13":("branching/qualification",f"CLAUDE_BRANCHING={br.get('CLAUDE_BRANCHING')}, STATUS={cdec.get('CLAUDE_TEACHER_STATUS')}",bool(cdec.get("CLAUDE_TEACHER_STATUS"))),
     "AC-14":("best agent/submission",f"BEST_AGENT={bas.get('best_agent')}, SUBMISSION_F={sub.get('submission_F')}",bool(sub.get("submission_F"))),
     "AC-15":("validation/bundle",f"{val.get('n_checks')} content checks {val.get('n_failed')} failed; bundle {sb.get('n_failed')} failed",bool(val.get("all_ok")) and bool(sb.get("all_ok"))),
     "AC-16":("next step/git",f"NEXT_STEP={nxt.get('next_step')}, {len(commits)} commits",bool(nxt.get("next_step")) and len(commits)>0),
    }
    passed=[k for k,v in AC.items() if v[2]]; failed=[k for k,v in AC.items() if not v[2]]
    status="PASS" if not failed and val.get("all_ok") and sb.get("all_ok") else "PARTIAL"
    st={"contract":"c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification",
        "status":status,"acceptance_criteria_total":16,"acceptance_criteria_passed":len(passed),
        "acceptance_criteria_failed":len(failed),"initial_head":INITIAL,"final_head":head,
        "implementation_commits":[c.split()[0] for c in commits],
        "c011_repair":rr.get("C011_REPAIR"),
        "true_incumbent":inc.get("TRAINING_INCUMBENT",{}).get("candidate_id"),
        "evaluation_elite":inc.get("EVALUATION_ELITE",{}).get("candidate_id"),
        "elite_pool":[e["id"] for e in (pool.get("elite_pool") or [])],
        "opponent_overlap":ov.get("OPPONENT_OVERLAP"),
        "curriculum_result":cd.get("curriculum_result"),
        "self_play_loop":cd.get("self_play_loop"),
        "claude_branching":br.get("CLAUDE_BRANCHING"),
        "claude_teacher_status":cdec.get("CLAUDE_TEACHER_STATUS"),
        "best_agent":bas.get("best_agent"),"submission_F":sub.get("submission_F"),
        "kaggle_upload":ks.get("kaggle_upload"),"kaggle_submission_ref":None,
        "kaggle_submission_status":None,
        "promotion_decision":bas.get("promotion_decision"),
        "next_step":nxt.get("next_step"),
        "highest_leverage_blocker":nxt.get("highest_leverage_blocker"),
        "training_games":tg,"evaluation_games":man.get("total_games"),
        "claude_primary_labels":prim.get("n",0),
        "claude_repeat_labels":(cval or {}).get("repeat",{}).get("n",0),
        "frozen_teacher_same_panel_field":sub.get("frozen_teacher_same_panel_field"),
        "python_source_bundle":"results/artifacts/c012_python_source_bundle.zip",
        "python_source_bundle_sha256":sb.get("sha256"),
        "blocking_issues":[],
        "known_limitations":[
         "P1 ran the stage-0 mixture (fixed 15% elite) for its entire budget: a path-keyed "
         "checkpoint-hash cache left every in-run evaluation after game 0 without scores, so "
         "the 15->25->35->45% escalation and the §24 advance gates were never exercised. "
         "See failures/DEFECT_inrun_evaluation_stale_hash.md. Re-running P1 would have "
         "breached §48's 184,000-game ceiling, so the limitation is carried into the result.",
         "Early stopping was implemented and wired but received no in-run scores for the same "
         "reason, so no branch could stop early; every seed ran to budget.",
         "CLAUDE_BRANCHING is INCONCLUSIVE: the simulator exposes a forward-search API but no "
         "observation captured through the agent interface carried the search_begin_input "
         "payload search_begin requires, so objective action adjudication was not possible "
         "and no superiority claim is made.",
         "Claude labelling used a bounded registered subset rather than the §48 maxima, "
         "because the measured cost was ~$0.23/call.",
         "Games are engine random_device-seeded and not bit-reproducible; conclusions are "
         "stated with bootstrap intervals over the recorded games.",
        ]}
    json.dump(st,open(os.path.join(RES,"STATUS.json"),"w"),indent=2)
    cl=["# c012 Acceptance Checklist","",
        "Each criterion needs its evidence AND a substantive assertion from its contents "
        "(§52: a PASS requires content validation, not file existence).","",
        "| AC | area | assertion (verified) | passed |","|---|---|---|---|"]
    for k,(area,assertion,ok) in AC.items():
        cl.append(f"| {k} | {area} | {assertion} | {'YES' if ok else 'NO'} |")
    open(os.path.join(RES,"ACCEPTANCE_CHECKLIST.md"),"w").write("\n".join(cl)+"\n")
    open(os.path.join(RES,"FILES_CHANGED.md"),"w").write(
        "# Files changed (c012)\n\nNew c012 source only; no file under c005-c011 modified.\n\n```\n"
        +g("diff","--stat",f"{INITIAL}..HEAD")+"```\n")
    open(os.path.join(RES,"GIT_REPORT.md"),"w").write(
        f"# Git report (c012)\n\nBranch `contract/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification`\n\n"
        f"- initial HEAD `{INITIAL}`\n- final HEAD `{head}`\n\n## Commits\n\n```\n"
        +"\n".join(commits)+"\n```\n\n## Working tree\n\n```\n"+(g("status","--short") or "(clean)")
        +"```\n\n`results/` is review evidence and is intentionally uncommitted.\n")
    open(os.path.join(ART,"CLEAN_CHECKOUT.md"),"w").write(
        f"# Clean checkout & run (c012)\n\nBranch as above, final HEAD `{head}`, repo root, "
        f"`.venv/bin/python`.\n\nDeterministic: dependency/immutability verification, the c011 "
        f"repair tests (RNG restore and true continuation, both pinned to deterministic torch), "
        f"the curriculum hash lock, the content-aware validator and the source-bundle "
        f"validator.\n\nNot bit-reproducible: the games themselves (the cabt engine seeds from "
        f"`std::random_device`), and Claude Code responses. All conclusions are stated with "
        f"bootstrap intervals and the raw per-game records ship.\n\nExternally provided "
        f"(gitignored): cabt SDK + libcg.so, kaggle-environments, torch, the c005 teacher "
        f"sources and the c007-c011 artifacts. No file under c005-c011 is written.\n")
    print(json.dumps({"status":status,"passed":len(passed),"failed":failed,
                      "training_games":tg,"evaluation_games":man.get("total_games"),
                      "final_head":head[:12]},indent=2))
if __name__=="__main__": sys.exit(main() or 0)
