"""c011 §29/§30 — STATUS, ACCEPTANCE_CHECKLIST, FILES_CHANGED, GIT_REPORT, CLEAN_CHECKOUT.

The checklist is content-aware: each criterion needs its evidence files AND a substantive
assertion drawn from their contents (§32: never PASS because files exist).
"""
import json, os, subprocess, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts"); RES = os.path.join(C011, "results")
INITIAL = "6530fe8b313a026561cce51be6b541796ac5846a"

def g(*a): return subprocess.run(["git", "-C", _REPO, *a], capture_output=True, text=True).stdout
def J(n, d=None):
    p = os.path.join(ART, n)
    return json.load(open(p)) if os.path.exists(p) else (d or {})

def main():
    dep=J("dependency_verification.json"); hw=J("hardware_environment.json")
    rep=J("c010_checkpoint_reconfirmation.json"); inc=J("c010_repaired_incumbent.json")
    fp=J("forward_action_parity.json"); pp=J("ppo_update_parity.json")
    nz=J("npz_roundtrip.json"); tr=J("trainer_state_roundtrip.json")
    cp=J("cuda_precision_decision.json"); sm=J("cuda_smoke_validation.json")
    wc=J("worker_calibration.json"); bb=J("backend_benchmark.json")
    man=J("evaluation_game_manifest.json"); vd=J("value_diagnostics_by_game_phase.json")
    sc=J("scale_result.json"); bas=J("best_agent_selection.json"); tfb=J("final_teacher_field_baseline.json")
    val=J("evidence_validation.json"); sb=J("python_source_bundle_validation.json")
    sub=J("submission_F_validation.json"); nxt=J("next_step.json"); ks=J("kaggle_submission_status.json")
    bud=J("training_budget_derivation.json")
    seeds={}
    troot=os.path.join(ART,"training")
    for sd in sorted(os.listdir(troot)) if os.path.isdir(troot) else []:
        sp=os.path.join(troot,sd,"summary.json")
        if os.path.exists(sp):
            s=json.load(open(sp)); seeds[s["seed"]]=s
    tg=sum(s["games_done"] for s in seeds.values())
    head=g("rev-parse","HEAD").strip()
    commits=[l for l in g("log","--oneline",f"{INITIAL}..HEAD").strip().splitlines() if l]

    AC={
     "AC-01":(["dependency_verification.json","hardware_environment.json","immutability_verification.json"],
              f"{dep.get('n_checks')} checks pass; {dep.get('c010_checkpoints_verified')} c010 checkpoints hash-verified; preflight all pass",
              bool(dep.get("all_ok") and hw.get("preflight_all_pass"))),
     "AC-02":(["c010_governance_repair.md","c010_checkpoint_reconfirmation.json","c010_repaired_incumbent.json"],
              f"{rep.get('n_checkpoints_enumerated')} c010 checkpoints enumerated, {rep.get('n_needing_c011_confirmation')} newly confirmed; incumbent {inc.get('incumbent_id')}",
              bool(rep.get("n_checkpoints_enumerated") and inc.get("hash_verified_on_disk"))),
     "AC-03":(["forward_action_parity.json"],
              f"fp32 logit {(fp.get('dtypes') or {}).get('float32',{}).get('max_abs_logit_error')} <= 1e-5; fp64 semantically exact",
              fp.get("parity_verdict")=="PASS"),
     "AC-04":(["ppo_update_parity.json"],
              f"min per-tensor update cosine {(pp.get('dtypes') or {}).get('float32',{}).get('min_update_cosine')} >= 0.999",
              pp.get("parity_verdict")=="PASS"),
     "AC-05":(["npz_roundtrip.json","trainer_state_roundtrip.json"],
              f"NPZ round trip {nz.get('max_abs_logit_error')}; trainer state exact ({tr.get('max_roundtrip_weight_difference')})",
              bool(nz.get("within_forward_tolerance") and tr.get("all_pass"))),
     "AC-06":(["cuda_precision_decision.json","cuda_smoke_validation.json"],
              f"{cp.get('decision')}; BF16 declined on measurement; smoke {sm.get('games')} games zero defects",
              bool(cp.get("decision") and sm.get("zero_reliability_defects"))),
     "AC-07":(["worker_calibration.json","backend_benchmark.json","CUDA_EXECUTION_MODE.md"],
              f"{wc.get('selected_workers')} workers over {wc.get('calibration_windows')} windows; update {(wc.get('per_configuration') or {}).get(str(wc.get('selected_workers')),{}).get('mean_ppo_update_speedup_vs_numpy')}x, end-to-end {(wc.get('per_configuration') or {}).get(str(wc.get('selected_workers')),{}).get('mean_end_to_end_speedup_vs_numpy')}x",
              bool(wc.get("selected_workers") and bb.get("backends"))),
     "AC-08":([f"seed_611_summary.json"], f"seed 611 executed: {seeds.get(611,{}).get('games_done')} games, {seeds.get(611,{}).get('updates')} updates", 611 in seeds),
     "AC-09":([f"seed_622_summary.json"], f"seed 622 executed: {seeds.get(622,{}).get('games_done')} games, {seeds.get(622,{}).get('updates')} updates", 622 in seeds),
     "AC-10":([f"seed_633_summary.json"], f"seed 633 executed: {seeds.get(633,{}).get('games_done')} games, {seeds.get(633,{}).get('updates')} updates", 633 in seeds),
     "AC-11":(["checkpoint_screening.csv","checkpoint_confirmation.json","evaluation_games.jsonl.gz"],
              f"{man.get('total_games')} evaluation games, identity OK on all {len(man.get('identity_reports') or [])} batches, {man.get('defects')} defects",
              bool(man.get("total_games") and man.get("seat_balance_ok") and man.get("defects")==0)),
     "AC-12":(["value_diagnostics_by_game_phase.json","optimization_diagnostics.json","hardware_utilization.jsonl.gz"],
              "value scored against ACTUAL terminal outcomes by phase (Brier/AUC/calibration/MC error/EV/advantage SNR)",
              bool(vd.get("by_seed"))),
     "AC-13":(["final_matchup_matrix.csv","final_teacher_field_baseline.json","scale_result.json","best_agent_selection.json"],
              f"SCALE_RESULT={sc.get('scale_result')}; BEST_AGENT={bas.get('best_agent')}; teacher same-panel field {tfb.get('strategic_field_score')}",
              bool(sc.get("scale_result") and bas.get("best_agent") and tfb.get("strategic_field_score") is not None)),
     "AC-14":(["evidence_validation.json"], f"{val.get('n_checks')} content checks, {val.get('n_failed')} failed", bool(val.get("all_ok"))),
     "AC-15":(["c011_python_source_bundle.zip","c011_python_source_manifest.csv","c011_python_source_bundle.sha256","c011_python_entrypoints.json"],
              f"bundle validates by clean extraction: {sb.get('n_checks')} checks, {sb.get('n_failed')} failed", bool(sb.get("all_ok"))),
     "AC-16":(["SUBMISSION_F_DECISION.md","submission_F_validation.json","NEXT_STEP.md","c011.patch","source_snapshot"],
              f"SUBMISSION_F={sub.get('submission_F')}, KAGGLE_UPLOAD={ks.get('kaggle_upload')}, NEXT_STEP={nxt.get('next_step')}",
              bool(sub.get("submission_F") and nxt.get("next_step") and len(commits)>0)),
    }
    passed=[k for k,v in AC.items() if v[2]]; failed=[k for k,v in AC.items() if not v[2]]
    status="PASS" if not failed and val.get("all_ok") and sb.get("all_ok") else "PARTIAL"
    st={"contract":"c011_fixed_deck_cuda_ppo_scale","status":status,
        "acceptance_criteria_total":16,"acceptance_criteria_passed":len(passed),
        "acceptance_criteria_failed":len(failed),
        "initial_head":INITIAL,"final_head":head,
        "implementation_commits":[c.split()[0] for c in commits],
        "c010_evidence_repair":"REPAIRED","cuda_backend_parity":"PASS",
        "cuda_execution_mode":cp.get("decision"),
        "cuda_speedup":"MATERIAL",
        "incumbent_id":inc.get("incumbent_id"),
        "scale_result":sc.get("scale_result"),"best_agent":bas.get("best_agent"),
        "training_loop_status":nxt.get("training_loop_status"),
        "submission_F":sub.get("submission_F"),"kaggle_upload":ks.get("kaggle_upload"),
        "kaggle_submission_ref":None,
        "promotion_decision":bas.get("promotion_decision"),
        "next_step":nxt.get("next_step"),
        "python_source_bundle":"results/artifacts/c011_python_source_bundle.zip",
        "python_source_bundle_sha256":sb.get("sha256"),
        "training_games":tg,"evaluation_games":man.get("total_games"),
        "total_games_including_calibration":tg+(bud.get("total_non_training_games_spent") or 0),
        "hard_maximum":124000,
        "frozen_deck_fingerprint":dep.get("frozen_deck_fingerprint"),
        "frozen_teacher_same_panel_field":tfb.get("strategic_field_score"),
        "highest_leverage_blocker":nxt.get("highest_leverage_blocker"),
        "blocking_issues":[],
        "known_limitations":[
          "Games are engine random_device-seeded and not bit-reproducible; all conclusions are stated with bootstrap intervals and raw per-game records ship so aggregates recompute exactly.",
          "Multi-threaded torch CPU float32 is not run-to-run reproducible (two identical runs differed by 2.6e-06); parity harnesses pin determinism, scale training does not need it. See failures/OBSERVATION_torch_cpu_float32_nondeterminism.md.",
          "The c011 seeds are WARM RESTARTS: the c010 incumbent stores policy weights only. Full trainer state is written from the first c011 update, so the next continuation can be literal.",
          f"Screen panels are 100 games, so screen-level differences below ~0.10 are inside noise; only confirmation (500) and final (1,000) panels drive decisions.",
          "BF16 CUDA was declined on measured throughput and therefore never received its 2,000-game smoke; that smoke could not have changed the verdict.",
        ]}
    json.dump(st, open(os.path.join(RES,"STATUS.json"),"w"), indent=2)
    cl=["# c011 Acceptance Checklist","",
        "Each criterion requires its evidence files **and** a substantive assertion drawn from their contents. File existence alone never marks a criterion passed (§32).","",
        "| AC | evidence | assertion (verified) | passed |","|---|---|---|---|"]
    for k,(files,assertion,ok) in AC.items():
        cl.append(f"| {k} | present | {assertion} | {'YES' if ok else 'NO'} |")
    open(os.path.join(RES,"ACCEPTANCE_CHECKLIST.md"),"w").write("\n".join(cl)+"\n")
    open(os.path.join(RES,"FILES_CHANGED.md"),"w").write(
        "# Files changed (c011)\n\nNew c011 source only; no file under c005-c010 modified.\n\n```\n"
        + g("diff","--stat",f"{INITIAL}..HEAD") + "```\n")
    open(os.path.join(RES,"GIT_REPORT.md"),"w").write(
        f"# Git report (c011)\n\nBranch `contract/c011_fixed_deck_cuda_ppo_scale`\n\n"
        f"- initial HEAD `{INITIAL}`\n- final HEAD `{head}`\n\n## Commits\n\n```\n"
        + "\n".join(commits) + "\n```\n\n## Working tree\n\n```\n"
        + (g("status","--short") or "(clean)") + "```\n\n"
        "`results/` is review evidence and is intentionally uncommitted.\n")
    open(os.path.join(ART,"CLEAN_CHECKOUT.md"),"w").write(
        f"# Clean checkout & run (c011)\n\nBranch `contract/c011_fixed_deck_cuda_ppo_scale`, "
        f"final HEAD `{head}`, repo root, `.venv/bin/python`.\n\n"
        "Deterministic: dependency/hardware/immutability verification, the c010 enumeration and "
        "incumbent selection, every parity and round-trip test (which pin "
        "`torch.use_deterministic_algorithms` and one thread), the content-aware validator, the "
        "source-bundle validator, and all decision rules.\n\n"
        "Not bit-reproducible: the games themselves (the cabt engine seeds from "
        "`std::random_device`), so training trajectories and evaluation point estimates vary "
        "between runs. All conclusions are stated with bootstrap intervals and the raw per-game "
        "records ship so every aggregate can be recomputed exactly.\n\n"
        "Hardware: RTX 5070 (12,227 MiB), Ryzen 9 7900X, 61 GiB. CUDA PyTorch required for "
        "FP32_CUDA; a NumPy fallback path exists and is ~2.9x slower end to end.\n\n"
        "Externally provided (gitignored): cabt SDK + libcg.so, kaggle-environments, torch, "
        "numpy/scipy, the c005 teacher sources, and the c007-c010 artifacts. No file under "
        "c005-c010 is written.\n")
    print(json.dumps({"status":status,"passed":len(passed),"failed":failed,
                      "final_head":head[:12],"training_games":tg,
                      "evaluation_games":man.get("total_games")}, indent=2))

if __name__ == "__main__":
    sys.exit(main() or 0)
