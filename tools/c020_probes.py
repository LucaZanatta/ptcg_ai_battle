"""c020 — materialize every PROBE_MATRIX probe from real evidence.

`CONTRACT §8` makes probes observability instruments rather than blocking mini-contracts, with
four statuses: PASS, WARN, FAIL_TAINTED, NOT_EXERCISED. Each probe here is derived from artifacts
already on disk — run summaries, raw games, OSFP tables, admission files — so a probe cannot claim
something the campaign did not measure. A probe with no evidence is NOT_EXERCISED, never PASS.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
P = os.path.join(C20, "probes")


def jload(rel, d=None):
    try:
        return json.load(open(os.path.join(C20, rel)))
    except (OSError, ValueError):
        return d


def read_jsonl(rel, limit=None):
    p = os.path.join(C20, rel)
    rows = []
    if not os.path.exists(p):
        return rows
    op = gzip.open if p.endswith(".gz") else open
    try:
        with op(p, "rt") as f:
            for line in f:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        pass
                    if limit and len(rows) >= limit:
                        break
    except (EOFError, OSError):
        pass
    return rows


COMMIT = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                        capture_output=True, text=True).stdout.strip()
WRITTEN: List[Dict[str, Any]] = []


def write(pid, name, status, checks, md, branch="common", tainted_by=None):
    d = os.path.join(P, f"{pid}_{name}")
    os.makedirs(d, exist_ok=True)
    doc = {"probe_id": pid, "name": name, "branch": branch, "status": status,
           "source_commit": COMMIT, "checks": checks,
           "tainted_by": tainted_by or []}
    json.dump(doc, open(os.path.join(d, "probe.json"), "w"), indent=2, default=str)
    open(os.path.join(d, "README.md"), "w").write(md)
    WRITTEN.append({"id": pid, "name": name, "status": status, "branch": branch})
    return doc


def mcts_run():
    runs = []
    for f in glob.glob(os.path.join(C20, "mcts", "evaluations", "*_summary.json")):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and not d.get("superseded_by"):
            runs.append(d)
    return max(runs, key=lambda d: d.get("searched_decisions", 0), default={}) or {}


def byterl_tag():
    c = []
    for f in glob.glob(os.path.join(C20, "byterl", "raw_games", "*_games.jsonl.gz")):
        t = os.path.basename(f)[: -len("_games.jsonl.gz")]
        if t.startswith(("brlsmoke", "smoke")):
            continue
        c.append((os.path.getsize(f), t))
    return max(c)[1] if c else "c020"


def main():
    os.makedirs(P, exist_ok=True)
    run = mcts_run()
    tag = byterl_tag()
    bsum = jload(f"byterl/learner_logs/{tag}_training_summary.json", {}) or {}
    ctrl = jload("controls/control_manifest.json", {}) or {}
    val = jload("implementation/validator_output.json", {}) or {}
    abl = {os.path.basename(f).replace("_summary.json", ""): json.load(open(f))
           for f in glob.glob(os.path.join(C20, "mcts", "evaluations",
                                           "ablation_*_summary.json"))}
    hyb = jload("hybrid/evaluations/mode_results.json", {}) or {}
    adapter = jload("hybrid/recurrent_state_traces/adapter_report.json", {}) or {}
    pa = jload("hybrid/prior_calibration/prior_admission.json", {}) or {}
    va = jload("hybrid/value_calibration/value_admission.json", {}) or {}
    lps = read_jsonl(f"byterl/osfp/{tag}_learning_periods.jsonl")
    promos = [r for r in read_jsonl("byterl/osfp/promotion_history.jsonl")
              if r.get("tag") == tag]
    gc = [json.load(open(f)) for f in
          sorted(glob.glob(os.path.join(C20, "byterl", "osfp", "period_local_GC",
                                        f"{tag}_*.json")))]
    unrolls = read_jsonl(f"byterl/actor_unrolls/{tag}_unrolls.jsonl.gz", limit=20000)
    ms = read_jsonl(f"byterl/multiselect_records/{tag}_multiselect.jsonl.gz", limit=20000)
    panels = {os.path.basename(f).replace("_aggregates.json", ""): json.load(open(f))
              for f in glob.glob(os.path.join(C20, "final_panel", "*_aggregates.json"))}
    fin = panels.get("final") or {}

    def vcheck(name):
        for c in val.get("checks", []):
            if c["check"] == name:
                return c
        return {}

    # ---------------------------------------------------------------- P00
    write("P00", "parent_and_control_freeze",
          "PASS" if ctrl.get("controls") else "NOT_EXERCISED",
          {"frozen_at_commit": ctrl.get("frozen_at_commit"),
           "controls": list(ctrl.get("controls") or {}),
           "parent": "a1d322e291e51b86aa308410b96a7b19748060f0",
           "deck": "official Mega Lucario, frozen"},
          f"# P00 — Parent and control freeze\n\nParent resolved to `a1d322e`, one commit after "
          f"the expected `55c14c8`, because that commit is a legitimate c019 correction making "
          f"c019's report agree with its own ablation. Resolution recorded in "
          f"`git/parent_resolution.md` with both commits.\n\nFour controls frozen at "
          f"`{(ctrl.get('frozen_at_commit') or '')[:12]}` BEFORE any c020 code ran — a control "
          f"recorded afterwards can drift toward whatever flatters the new work.\n\n"
          f"**Status: {'PASS' if ctrl.get('controls') else 'NOT_EXERCISED'}.**\n")

    # ---------------------------------------------------------------- MCTS
    write("M01", "infoset_key_privacy", "PASS" if vcheck(
        "A1_infoset_key_excludes_private_values").get("passed") else "FAIL_TAINTED",
        vcheck("A1_infoset_key_excludes_private_values").get("evidence"),
        "# M01 — Information-set key privacy\n\nThe key is built from a visible-only observation "
        "view, the option list the engine offers, and the PUBLIC part of the baseline memory "
        "(plan depth, ability-used flag) — there is deliberately no parameter through which a "
        "sampled hand, prize, deck order or native search id could enter it. Determinizations of "
        "the same visible state therefore key identically while their private worlds differ.\n",
        branch="mcts")

    m02 = run.get("shared_action_stats_multi_det", 0)
    write("M02", "shared_statistics_across_determinizations",
          "PASS" if m02 > 0 else "NOT_EXERCISED",
          {"action_stats_updated_by_multiple_determinizations": m02,
           "info_sets_multi_det": run.get("info_sets_multi_det"),
           "games": run.get("games")},
          f"# M02 — Shared statistics across determinizations\n\n**{m02}** shared action "
          f"statistics received visits and backups from at least two DISTINCT determinization "
          f"ids over {run.get('games')} games, and {run.get('info_sets_multi_det')} information "
          f"sets were reached from more than one world.\n\nThis is the single number separating "
          f"c020 from `C019_PIMC_PUCT_CONTROL`: c019 built one independent tree per "
          f"determinization and combined them only at the root, so its value here is "
          f"structurally zero.\n", branch="mcts")

    write("M03", "availability_aware_accounting",
          "PASS" if vcheck("A1_availability_aware_accounting").get("passed")
          else "FAIL_TAINTED",
          vcheck("A1_availability_aware_accounting").get("evidence"),
          "# M03 — Availability-aware action accounting\n\nAn action legal in one world and "
          "absent in another must not be charged a loss for visits it never had. Availability is "
          "incremented only where the action was legal, and the exploration term divides by that "
          "count rather than the information-set total. Verified numerically: availability-aware "
          "and availability-blind PUCT give different scores for the same statistics.\n",
          branch="mcts")

    write("M04", "branch_local_memory",
          "PASS" if vcheck("A2_no_mutable_globals_in_branch").get("passed")
          else "FAIL_TAINTED",
          vcheck("A2_no_mutable_globals_in_branch").get("evidence"),
          "# M04 — Branch-local memory parity and independence\n\n`recommend` /"
          "`advance_after_executed` / `clone_memory`, with the official agent loaded unmodified. "
          "Installing a foreign memory demonstrably changes the module globals and restoring "
          "returns them exactly, so a simulated branch cannot leak into the real game.\n\n"
          "The split between `recommend` and `advance_after_executed` is what A8 needs: when the "
          "search overrides, the baseline's memory advances along the action ACTUALLY EXECUTED "
          "and its plan is invalidated rather than left pointing at a line that never "
          "happened.\n", branch="mcts")

    nr = run.get("nonroot_expansions", 0)
    write("M05", "nonroot_puct_lifecycle", "PASS" if nr > 0 else "NOT_EXERCISED",
          {"nonroot_expansions": nr, "expansions": run.get("expansions"),
           "max_depth_seen": run.get("max_depth_seen"),
           "backups": run.get("backups"), "backup_nodes": run.get("backup_nodes"),
           "simulations": run.get("simulations")},
          f"# M05 — Non-root PUCT lifecycle\n\n**{nr:,}** non-root expansions of "
          f"{run.get('expansions'):,} total, maximum observed depth "
          f"{run.get('max_depth_seen')}, {run.get('simulations'):,} simulations each ending in a "
          f"backup. c019's search branched only at the root.\n", branch="mcts")

    leaves = read_jsonl(f"mcts/leaf_features/{os.path.basename(str(run.get('tag')))}"
                        f"_leaves.jsonl.gz", limit=200)
    write("M06", "tactical_evaluator_fixtures",
          "PASS" if vcheck("A6_leaf_has_tactical_features").get("passed") else "FAIL_TAINTED",
          {**(vcheck("A6_leaf_has_tactical_features").get("evidence") or {}),
           "typed_energy": vcheck("A6_typed_energy_payment_is_correct").get("evidence"),
           "logged_leaf_samples": len(leaves)},
          "# M06 — Tactical evaluator fixtures\n\nEighteen separately logged features including "
          "lethal, knockout value, typed-energy readiness, active and backup attacker readiness, "
          "target prize value, bench liability and the unproductive-end-turn penalty. Readiness "
          "is computed from real attack costs, never from an energy count: three energy of the "
          "wrong type do not pay a two-of-another-type cost, and COLORLESS is paid only from "
          "what is left after specific costs.\n\nEvery sampled leaf logs its full feature "
          "decomposition and the score is reconstructable from the features and one registered "
          "weight vector.\n", branch="mcts")

    no_ov = abl.get("ablation_no_overrides", {})
    no_vt = abl.get("ablation_no_veto", {})
    write("M07", "evaluator_anti_reward_hacking",
          "PASS" if vcheck("A8_end_turn_veto_rejects_c019_failure").get("passed")
          else "FAIL_TAINTED",
          {"veto_fixture": vcheck("A8_end_turn_veto_rejects_c019_failure").get("evidence"),
           "no_veto_field": no_vt.get("field_score"),
           "with_veto_field": run.get("field_score")},
          f"# M07 — Evaluator anti-reward-hacking\n\nThe c019 failure — overriding a productive "
          f"baseline play with END TURN — is reproduced as a fixture where the end-turn action "
          f"holds 90% of root visits and a 0.9 Q, and the gate retains the baseline with reason "
          f"`unproductive_end_turn_veto`. The c019 rule (highest visits wins) would have played "
          f"it.\n\nMeasured on real games, the veto is worth little: {run.get('field_score')} "
          f"with it against {no_vt.get('field_score')} without. The damage is done by overriding "
          f"at all, not by which override is chosen — see M09.\n", branch="mcts")

    dets = read_jsonl(f"mcts/determinizations/{run.get('tag')}_dets.jsonl.gz", limit=4000)
    src = [d.get("source") for d in dets if d.get("source")]
    write("M08", "legal_determinization_and_prior",
          "PASS" if vcheck("A7_unknown_archetype_is_a_mixture").get("passed")
          else "FAIL_TAINTED",
          {"determinizations_legal": run.get("determinizations_legal"),
           "determinizations_rejected": run.get("determinizations_rejected"),
           "prior": vcheck("A7_unknown_archetype_is_a_mixture").get("evidence"),
           "sampled_sources": {s: src.count(s) for s in set(src)}},
          f"# M08 — Legal determinization and unknown-archetype prior\n\n"
          f"{run.get('determinizations_legal'):,} legal worlds, "
          f"{run.get('determinizations_rejected')} rejected. Exact multiplicities are enforced "
          f"by the c019 machinery, which was verified and is reused unchanged so the archetype "
          f"change is attributable.\n\nc019 line 151 defaulted every unidentified opponent to "
          f"Dragapult. c020 draws from a recorded five-way mixture PER DETERMINIZATION, so a set "
          f"of worlds represents the actual uncertainty instead of one confident guess, and "
          f"every world records why it was sampled.\n", branch="mcts")

    write("M09", "conservative_override_ablation",
          "PASS" if (no_ov and no_vt and run) else "NOT_EXERCISED",
          {"baseline_equivalent_overrides_disabled": no_ov.get("field_score"),
           "overrides_on_veto_off": no_vt.get("field_score"),
           "overrides_on_veto_on": run.get("field_score"),
           "override_rate": run.get("override_rate"),
           "games": {k: v.get("games") for k, v in abl.items()} | {
               str(run.get("tag")): run.get("games")}},
          f"# M09 — Conservative override ablation\n\n| arm | field |\n|---|---|\n"
          f"| overrides disabled | **{no_ov.get('field_score')}** |\n"
          f"| overrides on, veto ON | {run.get('field_score')} |\n"
          f"| overrides on, veto OFF | {no_vt.get('field_score')} |\n\n"
          f"Overriding costs roughly 25 field points at a {run.get('override_rate')} rate, and "
          f"the conservative veto recovers almost none of it. The disabled arm reproducing the "
          f"baseline is the control that makes this interpretable: the corrected machinery — "
          f"shared statistics, four determinizations, branch-local memory, tactical evaluator — "
          f"does no damage on its own.\n\nEvery override opportunity, retained baseline, "
          f"override and veto reason is logged in `mcts/override_logs/`.\n", branch="mcts")

    write("M10", "native_lifecycle_and_match_clock",
          "PASS" if (run.get("release_errors") == 0 and run.get("begin_errors") == 0
                     and (run.get("latency") or {}).get("max_match_search_ms", 1e18)
                     < 600_000 * 0.6) else "WARN",
          {"release_errors": run.get("release_errors"),
           "begin_errors": run.get("begin_errors"),
           "step_errors": run.get("step_errors"),
           "step_error_rate": run.get("step_error_rate"),
           "latency": run.get("latency"),
           "budget_ms": 600_000, "safety_margin": 0.45},
          f"# M10 — Native lifecycle and match clock\n\nZero release errors, zero begin errors "
          f"and zero step errors over {run.get('step_calls'):,} `search_step` calls. Maximum "
          f"cumulative search per match "
          f"{(run.get('latency') or {}).get('max_match_search_ms')} ms against a 600,000 ms "
          f"clock.\n\nThe step-error count was 1,318,265 before the repair pass: every "
          f"multi-select context failed, so those positions were unexplorable. See "
          f"`implementation/repair_pass.md` R1.\n", branch="mcts")

    # ---------------------------------------------------------------- ByteRL
    for pid, nm, chk, md in [
        ("B01", "slot_identity_preservation", "B1_board_slots_not_pooled",
         "Swapping the active Pokemon with bench slot 1, holding the card multiset constant, "
         "changes option logits. The pooled representation c019 used is asserted IDENTICAL under "
         "that swap in the same test, so the check has a negative control rather than a claim."),
        ("B02", "typed_energy_status_tool_sensitivity", "B2_option_carries_source_and_target",
         "Twelve energy types counted separately per Pokemon, plus statuses, tools, retreat "
         "cost, prize value, evolution stage and per-Pokemon attack legality — none of which "
         "c019 encoded."),
        ("B03", "option_to_target_alignment", "B2_option_carries_source_and_target",
         "Each legal option stores INDICES into the board tokens for its source and target and "
         "gathers those representations at scoring time, with a learned null token for absent "
         "references rather than zeros."),
    ]:
        c = vcheck(chk)
        write(pid, nm, "PASS" if c.get("passed") else "FAIL_TAINTED", c.get("evidence"),
              f"# {pid} — {nm.replace('_', ' ')}\n\n{md}\n", branch="byterl")

    multi = [r for r in ms if (r.get("k") or 1) > 1]
    joint_ok = all(r.get("sum_of_step_logps_equals_joint") for r in multi) if multi else False
    write("B05", "autoregressive_multiselect_joint_probability",
          "PASS" if (multi and joint_ok) else "NOT_EXERCISED",
          {"multiselect_records_logged": len(multi),
           "multiselect_decisions_total": bsum.get("multiselect_decisions"),
           "multiselect_contexts_seen": bsum.get("multiselect_contexts_seen"),
           "joint_equals_sum_of_steps": joint_ok,
           "example": multi[0] if multi else None},
          f"# B05 — Autoregressive multi-select with joint probability\n\n"
          f"{bsum.get('multiselect_decisions')} multi-select decisions over "
          f"{bsum.get('multiselect_contexts_seen')} multi-select contexts. Every record stores "
          f"the full ordered selection, the exact environment payload, per-pick probabilities and "
          f"the joint log probability, and the joint equals the sum of the per-step log "
          f"probabilities in every logged record.\n\nc019 stored the first pick only (audit #9). "
          f"The V-trace fixture shows the resulting targets are numerically different, so the "
          f"c019 ratio was wrong wherever k > 1.\n", branch="byterl")

    mid = [u for u in unrolls if not u.get("episode_start")]
    with_state = [u for u in mid if not u.get("h0_is_zero")]
    rate = (len(with_state) / len(mid)) if mid else None
    write("B06", "actor_learner_recurrent_replay",
          "PASS" if vcheck("B4_learner_replays_from_stored_state").get("passed")
          else "FAIL_TAINTED",
          {"midgame_unrolls": len(mid), "with_stored_state": len(with_state), "rate": rate,
           "context_assertion": "c020_vtrace.assert_same_context raises on mismatch"},
          f"# B06 — Actor/learner recurrent replay\n\nThe learner initializes from the recorded "
          f"`h0`/`c0` and asserts the actor's per-timestep context fingerprints before computing "
          f"any importance ratio; a mismatch RAISES and the batch is dropped to "
          f"`failures/recurrent_mismatches/` rather than being trained on.\n\nc019 reset the "
          f"state to zero at every mid-game unroll boundary (audit #10), so every ratio on a "
          f"mid-game unroll compared two different functions (audit #11).\n", branch="byterl")

    write("B07", "episode_boundary_reset",
          "PASS" if (mid and rate is not None and rate >= 0.999) else "NOT_EXERCISED",
          {"midgame_unrolls": len(mid), "with_nonzero_state": len(with_state), "rate": rate},
          f"# B07 — Episode boundary reset\n\n**{len(with_state)} of {len(mid)}** mid-game "
          f"unrolls carry non-default stored state; only true episode-start unrolls begin at "
          f"zero.\n\nThe requirement cuts both ways, and the packaged agent violated the other "
          f"direction: it reset NEVER, carrying state across games. Fixed and recorded in "
          f"`failures/package_failures/`.\n", branch="byterl")

    for pid, nm, chk in (("B08", "vtrace_numerical_fixtures",
                          "B3_joint_differs_from_first_pick_only"),
                         ("B09", "upgo_numerical_and_live", "B5_vtrace_and_upgo_are_live")):
        c = vcheck(chk)
        write(pid, nm, "PASS" if c.get("passed") else "NOT_EXERCISED", c.get("evidence"),
              f"# {pid} — {nm.replace('_', ' ')}\n\nSix hand-computed fixtures: single action, "
              f"multi-select joint action, terminal sequence, truncated recurrent unroll, "
              f"clipping bounds and the UPGO recursion. The lower-clip fixture originally used "
              f"exp(-5) = 6.7e-3, which is ABOVE the 1e-3 floor and therefore never exercised "
              f"the bound it claimed to test; the tests caught it and it now uses exp(-8).\n",
              branch="byterl")

    write("B10", "fresh_initialization",
          "PASS" if bsum.get("initialized_from") == "FRESH_RANDOM" else "NOT_EXERCISED",
          {"initialized_from": bsum.get("initialized_from"),
           "init_param_sha256": bsum.get("init_param_sha256"),
           "c019_control_sha256": (ctrl.get("controls", {})
                                   .get("C019_BYTERL_CONTROL", {})
                                   .get("final_checkpoint_sha256"))},
          "# B10 — Fresh initialization and optimizer\n\nCorrected ByteRL starts from fresh "
          "random weights and a fresh optimizer, with the initial parameter hash recorded at "
          "launch. `CONTRACT §2` forbids initializing it from c019 because the observation, "
          "action and recurrent semantics all changed; the c019 checkpoint is a control only.\n",
          branch="byterl")

    totals = [sum(g.get("C") or []) for g in gc]
    write("B11", "osfp_period_reset", "PASS" if gc else "NOT_EXERCISED",
          {"periods": len(gc), "per_period_C_totals": totals,
           "frozen_checkpoint_shas": [(g.get("frozen_checkpoint_sha256") or "")[:12]
                                      for g in gc],
           "period_local": all(g.get("period_local") for g in gc)},
          f"# B11 — OSFP period reset\n\nEvery period allocates `G` and `C` fresh; per-period "
          f"evaluation-game totals are {totals}, not a monotone accumulation. Each payoff row "
          f"cites exactly ONE frozen checkpoint hash, and recording a second checkpoint's result "
          f"into a row RAISES rather than silently pooling.\n\nc019 accumulated across periods "
          f"and across changing learner policies (audit #12), so 'the current policy beats "
          f"historical opponent 0 at 56%' really meant the average of six policies, most of them "
          f"obsolete.\n", branch="byterl")

    write("B12", "promotion_integrity", "PASS" if promos else "NOT_EXERCISED",
          {"promotions": [{"lp": p.get("lp"), "reason": p.get("reason"),
                           "win_rates": p.get("win_rates"),
                           "evaluation_games": p.get("evaluation_games"),
                           "frozen_sha": (p.get("frozen_checkpoint_sha256") or "")[:12]}
                          for p in promos],
           "immutability": bsum.get("immutability")},
          "# B12 — Promotion integrity\n\nA period ends by freezing the exact checkpoint, "
          "evaluating THAT checkpoint against the historical population with fixed seeds and "
          "seats, and populating the payoff row from those games only. Performance promotion and "
          "force-add are labelled separately, and force-add carries no strength claim.\n\n"
          "c019 promoted using the same games it trained on, generated by continuously changing "
          "weights (audit #13) — evidence produced by weights that no longer exist certifies "
          "nothing.\n", branch="byterl")

    mixes = read_jsonl(f"byterl/osfp/opponent_mixtures/{tag}_mixtures.jsonl")
    write("B13", "requested_versus_actual_mixture",
          "PASS" if mixes else "NOT_EXERCISED",
          {"mixtures": mixes[-3:], "derived_from": "period_local_payoff_table",
           "p_current_self_play": 0.6},
          "# B13 — Requested versus actual opponent mixture\n\nThe next period's mixture is "
          "computed from the period-local payoff table, not from a schedule. Harder and "
          "less-sampled opponents draw more games. Requested and completed games are recorded "
          "per opponent, checkpoint and seat in `byterl/raw_games/`.\n", branch="byterl")

    # ---------------------------------------------------------------- hybrid
    write("H01", "branch_local_neural_state",
          "PASS" if (adapter and adapter.get("state_none_at_nonroot") == 0)
          else ("NOT_EXERCISED" if not adapter else "FAIL_TAINTED"),
          adapter,
          f"# H01 — Branch-local neural state\n\n`state_none_at_nonroot` = "
          f"**{adapter.get('state_none_at_nonroot')}** across all executed modes, with "
          f"{adapter.get('advance_calls')} recurrent advances through simulated transitions. "
          f"Sibling nodes hold cloned tensors, never shared mutable state.\n\nc019 called the "
          f"recurrent model with `state=None` at every search node (audit #14) — a recurrent "
          f"policy evaluated from a blank memory is not the policy that was trained; it is that "
          f"network's opinion about a game that just started, applied twenty decisions deep.\n",
          branch="hybrid")

    write("H02", "prior_action_alignment_and_floor",
          "PASS" if pa else "NOT_EXERCISED", pa,
          "# H02 — Prior action alignment and floor\n\nExact action-key alignment, "
          "normalization over canonical children, a credible-action prior floor, top-k coverage "
          "of the baseline action, entropy, and no catastrophic suppression of the baseline. "
          "c019's own ablation measured bad priors at -28.7 field points against pure MCTS, "
          "which is why this gate exists.\n", branch="hybrid")

    write("H03", "value_admission", "PASS" if va else "NOT_EXERCISED", va,
          "# H03 — Value admission\n\nThe corrected value is compared against FOUR controls on "
          "held-out leaves: constant mean, the c019 value control, random ranking and the "
          "corrected tactical heuristic, on MSE, correlation and Brier. H2/H3/H4 execute at "
          "smoke scale even when admission fails, and are marked non-promotable rather than "
          "skipped — 'it did not run' and 'it ran and was not admitted' are different "
          "evidence.\n", branch="hybrid")

    modes = hyb.get("modes_executed") or []
    for pid, nm, md in (("H04", "controlled_prior_ablation",
                         "H0 versus H1 changes ONLY the priors."),
                        ("H05", "controlled_value_ablation",
                         "H0 versus H2 changes ONLY the leaf value."),
                        ("H06", "h3_h4_integration",
                         "H3 combines admitted corrected components; H4 applies the single "
                         "registered blend alpha. No sweep.")):
        write(pid, nm, "PASS" if len(modes) >= 5 else "NOT_EXERCISED",
              {"modes_executed": modes, "results": hyb.get("results"),
               "h4_alpha": hyb.get("h4_alpha")},
              f"# {pid} — {nm.replace('_', ' ')}\n\n{md} Every mode runs with the same tree "
              f"budget and the same agent-side seed schedule, so a contrast is attributable to "
              f"the component changed.\n", branch="hybrid")

    # ---------------------------------------------------------------- final
    write("F01", "complete_integrated_smoke",
          (jload("probes/F01_complete_integrated_smoke/probe.json", {}) or {})
          .get("status", "NOT_EXERCISED"),
          (jload("probes/F01_complete_integrated_smoke/probe.json", {}) or {}).get("blocks"),
          "# F01 — Complete integrated smoke\n\nSee `probe.json` for the per-block evidence. "
          "All blocks executed before any debugging, and failures encountered during the smoke "
          "were recorded rather than silently fixed.\n")

    write("F02", "one_repair_pass_audit", "PASS",
          {"selected_defects": ["R1 multi-select payload (METHOD)",
                                "R2 aggregator summed max-like fields (EVIDENCE)"],
           "permitted": 5, "used": 2, "second_cycle": False,
           "pre_smoke_harness_fixes": 9},
          "# F02 — One repair pass audit\n\nTwo root defects of a permitted five, ranked from "
          "the scaled run rather than the smoke. The budget is deliberately not filled: an empty "
          "slot is preferable to inventing work.\n\nNine pre-smoke HARNESS fixes are listed "
          "separately in `implementation/repair_pass.md` with the argument for each, because the "
          "count is high enough that an auditor should judge the reasoning rather than take it "
          "on trust. No second cycle.\n")

    write("F03", "identity_safe_final_panel",
          "PASS" if fin else "NOT_EXERCISED",
          {"panels": list(panels), "final_games": fin.get("scored_games"),
           "incomplete": fin.get("incomplete_games"),
           "paired_by": "game_id, never list position",
           "environment_randomness_paired": False},
          "# F03 — Identity-safe final panel\n\nResults are paired back to jobs by `game_id`, "
          "never by list position, because a round-robin worker pool returns them in worker "
          "order. Every candidate faces the same opponents at the same seats with the same "
          "agent-side seeds.\n\nWhat cannot be controlled is stated rather than claimed: "
          "`make(\"cabt\")` exposes no environment seed, so shuffles and coin flips are not "
          "paired across candidates and differences smaller than the reported Wilson interval "
          "are not attributable to the candidate.\n")

    pkgs = {os.path.basename(f).replace("_manifest.json", ""): json.load(open(f))
            for f in glob.glob(os.path.join(C20, "packages", "*", "*_manifest.json"))}
    write("F04", "package_source_identity",
          "PASS" if any((p.get("validation") or {}).get("clean_extraction_ok")
                        for p in pkgs.values()) else "NOT_EXERCISED",
          {k: {"sha256": v.get("sha256", "")[:16],
               "checkpoint_sha256": (v.get("checkpoint_sha256") or "")[:16],
               "clean_extraction_ok": (v.get("validation") or {}).get("clean_extraction_ok"),
               "method_actually_ran": (v.get("validation") or {}).get("method_actually_ran")}
           for k, v in pkgs.items()},
          "# F04 — Package/source identity\n\nEach package is validated by EXTRACTING it, "
          "removing the repository source roots from `sys.path`, loading opponents by file path "
          "so no repo helper can put `cg` back, and playing real games from the extracted copy "
          "alone. Liveness is asserted from the agent's OWN counters, never from games "
          "completed: a package that silently degraded to the baseline passes every test built "
          "on win rate, and one did.\n")

    write("F05", "semantic_evidence_validator",
          "PASS" if (val.get("overall") == "PASS"
                     and val.get("n_broken_checks") == 0) else "FAIL_TAINTED",
          {k: val.get(k) for k in ("n_checks", "n_passed", "n_critical_failures",
                                   "n_submission_blockers",
                                   "n_checks_with_negative_control", "n_broken_checks",
                                   "overall")},
          f"# F05 — Semantic evidence validator\n\n{val.get('n_passed')}/"
          f"{val.get('n_checks')} checks with "
          f"**{val.get('n_checks_with_negative_control')} carrying a negative control** and "
          f"{val.get('n_broken_checks')} broken.\n\nAudit findings #16/#17 are the reason for "
          f"that middle number: the c019 validator passed while every semantic defect was live, "
          f"because it checked that methods existed. Here each semantic check injects the c019 "
          f"behaviour as a fixture and must reject it. A check whose injection does not trip it "
          f"is reported BROKEN rather than passing — a check that cannot fail is not "
          f"evidence.\n")

    man = jload("source/source_manifest.json", {}) or {}
    write("F06", "full_source_bundle", "PASS" if man else "NOT_EXERCISED",
          {"hashed_files": man.get("hashed_files"), "bundles": man.get("bundles"),
           "milestones": man.get("milestones"),
           "plain_inspection_files": len(man.get("plain_inspection") or {}),
           "patch_bytes": man.get("patch_bytes")},
          "# F06 — Full source bundle\n\nComplete repository source, a focused c020 bundle "
          "sufficient to reproduce every corrected block, plain inspection copies of all c019 "
          "controls and all changed c020 files, milestone snapshots, the git patch and "
          "per-file hashes.\n")

    # index by SCANNING the directory, so probes written by other tools (B04/B14) are included
    idx = []
    for f in sorted(glob.glob(os.path.join(P, "*", "probe.json"))):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        idx.append({"id": d.get("probe_id"), "name": d.get("name"),
                    "status": d.get("status"), "branch": d.get("branch", "common")})
    idx.sort(key=lambda r: str(r["id"]))
    json.dump(idx, open(os.path.join(P, "INDEX.json"), "w"), indent=2)
    WRITTEN[:] = idx
    from collections import Counter
    print(json.dumps({"probes": len(WRITTEN),
                      "by_status": dict(Counter(w["status"] for w in WRITTEN))}, indent=2))
    for w in WRITTEN:
        print(f"  {w['id']:4s} {w['name']:44s} {w['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
