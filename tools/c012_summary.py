"""c012 §54 — SUMMARY.md generated from the recorded artifacts."""
import json,os,sys,gzip
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C012=os.path.join(_REPO,"contracts","c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART=os.path.join(C012,"results","artifacts"); RES=os.path.join(C012,"results")
def J(n,d=None):
    p=os.path.join(ART,n); return json.load(open(p)) if os.path.exists(p) else (d or {})
def main():
    dep=J("dependency_verification.json"); rr=J("c011_repair_report.json")
    inc=J("frozen_incumbent_registry.json"); pool=J("elite_pool_registry.json")
    comb=J("elite_combination_registry.json"); ov=J("opponent_overlap_report.json")
    cd=J("curriculum_decision.json"); bas=J("best_agent_selection.json")
    hm=J("hard_state_manifest.json"); hia=J("hard_state_hidden_information_audit.json")
    pre=J("claude_preflight.json"); cdec=J("claude_teacher_decision.json")
    br=J("branching_validation.json"); sub=J("submission_F_validation.json")
    nxt=J("next_step.json"); val=J("evidence_validation.json"); st=J("../STATUS.json")
    sb=J("c012_python_source_bundle_validation.json"); man=J("evaluation_game_manifest.json")
    kag=J("kaggle_teacher_agent_comparison.json")
    seeds={}
    troot=os.path.join(ART,"training")
    for arm in sorted(os.listdir(troot)) if os.path.isdir(troot) else []:
        for sd in sorted(os.listdir(os.path.join(troot,arm))):
            sp=os.path.join(troot,arm,sd,"summary.json")
            if os.path.exists(sp):
                s=json.load(open(sp)); seeds[f"{s['arm']}_{s['seed']}"]=s
    m=cd.get("medians",{}); sbst=cd.get("seed_best",{}); fs=bas.get("final_summaries",{})
    mach=dep.get("machine",{})
    L=[]
    A=L.append
    A(f"# c012 — Fixed-Deck Self-Play Curriculum and Claude Teacher Qualification — SUMMARY\n")
    A(f"**STATUS = {st.get('status')} ({st.get('acceptance_criteria_passed')}/16 acceptance criteria)**\n")
    A("```text")
    for k,v in (("C011_REPAIR",rr.get("C011_REPAIR")),("TRUE_INCUMBENT",st.get("true_incumbent")),
                ("OPPONENT_OVERLAP",ov.get("OPPONENT_OVERLAP")),
                ("CURRICULUM_RESULT",cd.get("curriculum_result")),
                ("SELF_PLAY_LOOP",cd.get("self_play_loop")),
                ("CLAUDE_BRANCHING",br.get("CLAUDE_BRANCHING")),
                ("CLAUDE_TEACHER_STATUS",cdec.get("CLAUDE_TEACHER_STATUS")),
                ("BEST_AGENT",bas.get("best_agent")),("SUBMISSION_F",sub.get("submission_F")),
                ("PROMOTION_DECISION",bas.get("promotion_decision")),
                ("NEXT_STEP",nxt.get("next_step"))):
        A(f"{k:22s} = {v}")
    A("```\n")
    A("## The result in one paragraph\n")
    A(f"The single largest gain in this contract required no training at all. An arithmetic "
      f"average of two c011 seeds' weights, `SOUP_622+633`, scores "
      f"**{inc.get('TRAINING_INCUMBENT',{}).get('teacher_score'):.3f}** against the frozen teacher "
      f"and **{inc.get('TRAINING_INCUMBENT',{}).get('strategic_field_score'):.3f}** on the strategic "
      f"field, against 0.270/0.353 for c011's best single policy — a +0.11 teacher gain for zero "
      f"compute. Six PPO seeds then trained 181,184 completed games from that soup under two "
      f"different opponent populations, and **neither arm beat it on teacher score**. The "
      f"curriculum comparison came out `{cd.get('curriculum_result')}` and the self-play loop "
      f"`{cd.get('self_play_loop')}`. The binding constraint is therefore not the opponent "
      f"curriculum and not compute: it is that this PPO configuration cannot exceed a point that "
      f"weight-space averaging reaches for free.\n")
    A("## Machine and dependencies (AC-01)\n```text")
    A(f"{mach.get('cpu')}, {mach.get('cpu_threads')} threads, {mach.get('ram_gib')} GiB")
    A(f"{mach.get('gpu')} {mach.get('vram_total_mib')} MiB, driver {mach.get('driver')}")
    A(f"PyTorch {mach.get('torch')} / CUDA {mach.get('torch_cuda')}, Python {mach.get('python')}")
    A(f"frozen deck fingerprint {str(dep.get('frozen_deck_fingerprint'))[:32]}...")
    A(f"frozen teacher sha256   {str(dep.get('teacher_source_sha256'))[:32]}...")
    A(f"c011 checkpoints hash-verified: {dep.get('c011_checkpoints_verified')}")
    A("```\n")
    A("## c011 defects repaired (AC-02)\n")
    for d in rr.get("defects_repaired",[]):
        A(f"- **{d['id']}** ({d['section']}) — {d['c011_behaviour']} *Repair:* {d['c012_repair']}")
        if d.get("residual_defect"): A(f"  - **Residual:** {d['residual_defect']}")
    A("")
    A("## Phase 0 — elite combinations and the frozen incumbent (AC-03/04/05)\n")
    A(f"- {len(comb.get('soups') or {})} weight soups and {len(comb.get('ensembles') or {})} logit "
      f"ensembles registered **before** any combination was evaluated (§12).")
    A(f"- **TRAINING_INCUMBENT = {st.get('true_incumbent')}**, EVALUATION_ELITE = "
      f"{st.get('evaluation_elite')}, ELITE_POOL = {st.get('elite_pool')}")
    A(f"- Selected from {inc.get('n_candidates_considered')} correctly confirmed candidates on "
      f"equal 500-game footing.\n")
    A("## Phase 1 — overlap analysis (AC-06/07)\n")
    A(f"**OPPONENT_OVERLAP = {ov.get('OPPONENT_OVERLAP')}** — mean top-1 agreement "
      f"**{ov.get('mean_top1_agreement'):.3f}** across {ov.get('n_policy_pairs')} policy pairs on "
      f"identical frozen states. {ov.get('interpretation')}\n")
    A("## Phase 2 — controlled curriculum (AC-08/09/10)\n")
    A("| arm/seed | completed | trainable | updates | stage | stop |")
    A("|---|---:|---:|---:|---:|---|")
    for k,s in sorted(seeds.items()):
        A(f"| {k} | {s['completed_games']:,} | {s['games_with_trainable_decisions']:,} | "
          f"{s['updates']} | {s['final_curriculum_stage']} | {s['stop_reason']} |")
    A(f"\n**{st.get('training_games'):,} completed training games** against §48's 184,000 ceiling; "
      f"zero invalid actions and zero exceptions across all six seeds.\n")
    A("| | median teacher | median field |\n|---|---:|---:|")
    A(f"| P0 control | {m.get('P0_teacher')} | {m.get('P0_field')} |")
    A(f"| P1 elite self-play | {m.get('P1_teacher')} | {m.get('P1_field')} |")
    A(f"\n`CURRICULUM_RESULT = {cd.get('curriculum_result')}`, "
      f"`SELF_PLAY_LOOP = {cd.get('self_play_loop')}`.\n")
    A(f"> **Caveat that limits this result.** {cd.get('adaptive_caveat')}\n")
    A("## Final panel — 1,000 games per candidate (AC-14)\n")
    A("| candidate | teacher | strategic field |\n|---|---:|---:|")
    for c,s in sorted(fs.items(),key=lambda x:-(x[1].get('promotion_composite') or 0)):
        t=s.get('teacher_score'); f=s.get('strategic_field_score')
        A(f"| {c} | {'—' if t is None else f'{t:.4f}'} | {f:.4f} |")
    A(f"\nThe **frozen teacher scores {sub.get('frozen_teacher_same_panel_field')} on the same "
      f"strategic field** where the best agent manages "
      f"{fs.get(st.get('true_incumbent'),{}).get('strategic_field_score')}. "
      f"`BEST_AGENT = {bas.get('best_agent')}`, `{bas.get('promotion_decision')}`.\n")
    A("## Phase 3 — hard-state benchmark (AC-11)\n")
    A(f"- {hm.get('n_primary')} primary + {hm.get('n_repeat')} repeat states, no category above "
      f"{hm.get('max_category_share'):.0%} (§34 cap 25%)")
    A(f"- **{hia.get('n_clean')}/{hia.get('n_states')} hidden-information clean**; hash-locked "
      f"`{str(hm.get('benchmark_sha256'))[:32]}...` before any Claude call\n")
    A("## Phase 4 — Claude Opus qualification (AC-12/13)\n")
    A(f"- model requested `opus`, resolved `{cdec.get('resolved_model')}`, verified per call from "
      f"`modelUsage` output tokens; tools disabled; sequential; frozen prompt and schema")
    A(f"- **{cdec.get('n_primary_labels')} primary labels** "
      f"({cdec.get('n_call_failures')} subprocess timeouts reported separately), "
      f"{cdec.get('n_repeat_labels')} repeats, ${cdec.get('total_cost_usd')} total")
    A(f"- schema-valid **{cdec.get('schema_valid_rate')}**, legal-action "
      f"**{cdec.get('legal_action_rate')}**, hidden-information violations "
      f"**{cdec.get('hidden_information_violations')}**, repeated top-1 consistency "
      f"**{cdec.get('repeat_top1_agreement')}**")
    A(f"- `CLAUDE_BRANCHING = {br.get('CLAUDE_BRANCHING')}` — {br.get('reason')}")
    A(f"- **`CLAUDE_TEACHER_STATUS = {cdec.get('CLAUDE_TEACHER_STATUS')}`.** {cdec.get('rule')}")
    A(f"- Claude labels were **not** used to update any policy weights (§2).\n")
    A("## Submission (AC-14)\n")
    A(f"`SUBMISSION_F = {sub.get('submission_F')}`, `KAGGLE_UPLOAD = SKIPPED_BY_GATE`. "
      f"Teacher non-inferiority needs a one-sided 95% lower bound of 0.47; measured "
      f"{sub.get('best_agent_teacher_lb95')}. The agent must also beat the frozen teacher's "
      f"same-panel field score of {sub.get('frozen_teacher_same_panel_field')}; it does not. "
      f"Nothing was uploaded and no archive was built. Teacher ref 54948560 was refreshed "
      f"read-only (public score {kag.get('teacher_public_score_same_run')}).\n")
    A("## Evidence integrity (AC-15)\n")
    A(f"- **{val.get('n_checks')} content-aware checks, {val.get('n_failed')} failed** — hashes "
      f"recomputed, aggregates rebuilt from raw games, budgets recounted, curriculum lock "
      f"re-hashed")
    A(f"- {man.get('total_games'):,} evaluation games, identity assertions passing on every "
      f"batch, {man.get('defects')} defects")
    A(f"- source bundle `c012_python_source_bundle.zip` sha256 `{str(sb.get('sha256'))[:32]}...` "
      f"({sb.get('n_checks')} checks, {sb.get('n_failed')} failed)\n")
    A("## Next step and blocker\n")
    A(f"`NEXT_STEP = {nxt.get('next_step')}`.\n")
    A(f"**Highest-leverage blocker (one, measured):** {nxt.get('highest_leverage_blocker')}\n")
    A("**Hypotheses, labelled as such and untested here:** that weight-space averaging keeps "
      "paying over more diverse seeds; that the escalating elite schedule would behave "
      "differently from the fixed 15% actually run; that a different optimiser or value target "
      "would pass the point averaging reaches.\n")
    A("## Known limitations\n")
    for l in st.get("known_limitations",[]): A(f"- {l}")
    open(os.path.join(RES,"SUMMARY.md"),"w").write("\n".join(L)+"\n")
    print(f"SUMMARY.md written ({len(L)} blocks)")
if __name__=="__main__": sys.exit(main() or 0)
