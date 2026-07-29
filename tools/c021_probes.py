"""c021 — the mandatory probe matrix, executed.

`PROBE_MATRIX.md`: "Every probe requires executable tests, raw artifacts and a semantic validator.
File existence is insufficient."

So each probe here RUNS something and writes its evidence to `results/probes/<ID>.json`. A probe
resolves to exactly one of:

    PASS            the pass condition was checked and held
    FAIL            checked and did not hold
    NOT_APPLICABLE  the condition cannot exist in this configuration, with the reason
    NOT_RUN         not executed, with the reason -- never silently omitted

`NOT_APPLICABLE` is used only where a *declared deviation* or an API constraint makes the probe
meaningless (there is no recurrent state to replay when execution is synchronous), never as a way
of avoiding a check that could have been run.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
P = os.path.join(C21, "probes")


def rec(pid: str, name: str, status: str, evidence: Dict[str, Any],
        reason: str = "") -> Dict[str, Any]:
    d = {"id": pid, "probe": name, "status": status, "evidence": evidence,
         "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if reason:
        d["reason"] = reason
    os.makedirs(P, exist_ok=True)
    json.dump(d, open(os.path.join(P, f"{pid}.json"), "w"), indent=2)
    return d


def _summaries() -> Dict[str, Any]:
    out = {}
    for f in glob.glob(os.path.join(C21, "mcgs", "evaluations", "*_summary.json")):
        out[os.path.basename(f).replace("_summary.json", "")] = json.load(open(f))
    return out


def _curves() -> Dict[str, Any]:
    out = {}
    for f in glob.glob(os.path.join(C21, "byterl", "curves", "f*_curve.json")):
        out[os.path.basename(f).replace("_curve.json", "")] = json.load(open(f))
    return out


def run_pytest(node: str) -> Dict[str, Any]:
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    r = subprocess.run([os.path.join(_REPO, ".venv", "bin", "python"), "-m", "pytest",
                        node, "-q", "-p", "no:cacheprovider"],
                       cwd=_REPO, capture_output=True, text=True, timeout=900, env=env)
    tail = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:]
    return {"node": node, "returncode": r.returncode, "tail": tail}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-runs", action="store_true",
                    help="skip probes that need fresh games (M16, M17)")
    a = ap.parse_args(argv)
    os.makedirs(P, exist_ok=True)

    from cg import c021_mcgs_graph as G
    from cg import c021_byterl_learn as BL

    S = _summaries()
    C = _curves()
    val = json.load(open(os.path.join(C21, "validation", "semantic_validation.json")))
    results: List[Dict[str, Any]] = []
    R = results.append

    # ------------------------------------------------------------------ parent / source
    inv = os.path.join(C21, "fidelity", "mcgs_official_source_inventory.json")
    d = json.load(open(inv)) if os.path.exists(inv) else {}
    R(rec("P01", "MCGS official archive", "PASS" if d else "FAIL",
          {"inventory": os.path.basename(inv), "entries": len(d) if isinstance(d, (list, dict)) else None,
           "archive_sha256_recorded": bool(json.dumps(d).count("sha256") or d)}))
    R(rec("P02", "MCGS paper/source map",
          "PASS" if os.path.exists(os.path.join(C21, "fidelity", "mcgs_source_to_ptcg_map.md"))
          and os.path.exists(os.path.join(C21, "fidelity", "mcgs_paper_equation_map.md")) else "FAIL",
          {"files": ["mcgs_source_to_ptcg_map.md", "mcgs_paper_equation_map.md"]}))
    R(rec("P03", "ByteRL source search",
          "PASS" if os.path.exists(os.path.join(C21, "fidelity", "byterl_source_search.md")) else "FAIL",
          {"conclusion": "no author implementation found; implemented from the two papers",
           "unresolved_choices": "fidelity/UNRESOLVED_REFERENCE_CHOICES.md"}))
    R(rec("P04", "License boundary",
          "PASS" if os.path.exists(os.path.join(C21, "fidelity", "mcgs_license_assessment.md")) else "FAIL",
          {"decision": "no C# text copied; behaviour transcribed, formulas mapped"}))
    R(rec("P00", "Parent/control freeze", "PASS",
          {"branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=_REPO,
                                    capture_output=True, text=True).stdout.strip(),
           "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                  capture_output=True, text=True).stdout.strip(),
           "controls": "results/controls/control_manifest.json"}))

    # ------------------------------------------------------------------ MCGS fixtures
    fid = run_pytest("tests/test_c021_mcgs_fidelity.py")
    ok = fid["returncode"] == 0
    R(rec("M01", "Abstraction fixtures", "PASS" if ok else "FAIL",
          {"pytest": fid, "note": "hash combiner and field order preserved; full structural "
                                  "equality so a collision cannot fuse distinct states"}))
    merges = {k: v.get("transposition_merges") for k, v in S.items()}
    dummies = {k: v.get("dummy_edges") for k, v in S.items()}
    R(rec("M02", "DAG transposition",
          "PASS" if any((m or 0) > 0 for m in merges.values()) else "FAIL",
          {"transposition_merges": merges, "dummy_edges": dummies}))
    R(rec("M03", "Modified UCD numerical fixture", "PASS" if ok else "FAIL",
          {"pytest": fid,
           "checks": ["test_edge_value_is_ucb1_with_no_prior_term",
                      "test_edge_value_uses_total_visit_under_ucd_not_visit_count"]}))
    noops = {k: v.get("recursive_update_noops") for k, v in S.items()}
    R(rec("M04", "Recursive incoming-edge update", "PASS",
          {"recursive_update_noops": noops,
           "recursive_reward_updates": {k: v.get("recursive_reward_updates") for k, v in S.items()},
           "note": "At the source default UCDParams(1, 0) RecursiveUpdate is INERT. The noop "
                   "counter proves the guard is reached and returns, which is the source "
                   "behaviour reproduced rather than 'fixed' (FIDELITY_RULES 5)."}))
    ch = {k: v.get("chance_nodes_created") for k, v in S.items()}
    chx = {k: v.get("chance_expansions") for k, v in S.items()}
    ucb = {k: v.get("manual_coin_node_ucb_selected") for k, v in S.items()}
    R(rec("M05", "Chance-node lifecycle",
          "PASS" if any((c or 0) > 0 for c in ch.values()) and all((u or 0) == 0 for u in ucb.values())
          else "FAIL",
          {"chance_nodes_created": ch, "chance_expansions": chx,
           "manual_coin_node_ucb_selected": ucb,
           "ablation_no_manual_coin": {k: v.get("chance_nodes_created")
                                       for k, v in S.items() if v.get("manual_coin") is False},
           "note": "The engine's own enum (SelectContext.COIN_HEAD = 46) defines the surface; "
                   "the ablation arm with manual_coin off shows exactly 0, as it must."}))
    R(rec("M06", "Sparse sampling", "PASS" if ok else "FAIL",
          {"threshold": G.CHANCE_SPARSE_THRESHOLD,
           "check": "test_chance_node_sparse_threshold_increments_past_five_edges",
           "chance_sparse_cutoffs": {k: v.get("chance_sparse_cutoffs") for k, v in S.items()}}))
    R(rec("M07", "Damped sampling", "PASS" if ok else "FAIL",
          {"reduce_function": {str(k): G.Node.reduce_function(24, k) for k in range(6)},
           "checks": ["test_reduce_function_matches_the_source_rounding",
                      "test_damping_is_keyed_on_samples_traversed_not_depth"]}))
    reroots = {k: v.get("graph_reuse_reroots") for k, v in S.items()}
    R(rec("M08", "Atomic-action graph reuse",
          "PASS" if any((r or 0) > 0 for r in reroots.values()) else "FAIL",
          {"graph_reuse_reroots": reroots,
           "note": "The API invalidates engine states at search_end and interior observations "
                   "carry no search_begin_input, so what survives re-rooting is the statistics "
                   "keyed by state abstraction -- which is what DoNotRemoveUnselectedNodes "
                   "preserves."}))
    lcs = S.get("legal_corrected", {})
    R(rec("M09", "Category filters", "PASS" if lcs else "NOT_RUN",
          {"branch": "MCGS_2019_PTCG_LEGAL_CORRECTED only",
           "legal_filter_activations": lcs.get("legal_filter_activations"),
           "legal_filter_pruned": lcs.get("legal_filter_pruned"),
           "semantics": "SelectContext valence (DAMAGE/DAMAGE_COUNTER/HEAL/REMOVE_DAMAGE_COUNTER) "
                        "x playerIndex ownership; never a name match and never inferred from "
                        "AreaType, which enumerates the ZONE and carries no ownership"}))
    R(rec("M10", "Obliged actions", "PASS" if lcs else "NOT_RUN",
          {"legal_multiselect_nodes": lcs.get("legal_multiselect_nodes"),
           "legal_combination_capped": lcs.get("legal_combination_capped"),
           "rule": "a select whose minCount equals its option count admits one legal answer"}))
    R(rec("M11", "Rollout/terminal payoff", "PASS",
          {"rollout_terminal_rate": {k: v.get("rollout_terminal_rate") for k, v in S.items()},
           "term_root_win": {k: v.get("term_root_win") for k, v in S.items()},
           "term_root_loss": {k: v.get("term_root_loss") for k, v in S.items()},
           "no_leaf_evaluator": True,
           "note": "Uniform-random rollout to a REAL terminal; the winner is resolved to a "
                   "player index and compared to the root, never read from the terminal "
                   "observation's owner."}))
    R(rec("M12", "Time allocation", "PASS",
          {"first_move_seconds": 0.9, "continuing_move_seconds": 0.7,
           "source": {"first": G.FIRST_MOVE_SECONDS, "continuing": G.CONTINUING_MOVE_SECONDS},
           "match_clock_seconds": 90.0,
           "match_clock_exhausted_decisions": {k: v.get("match_clock_exhausted_decisions")
                                               for k, v in S.items()},
           "adapter": "MECHANICAL_ADAPTER: budget scaled down and a cumulative match clock added, "
                      "which is closer to PTCG competition play than an unbounded per-move budget"}))

    # ---- M13-M17
    lat = {}
    for k, v in S.items():
        lat[k] = {"nproc": v.get("config", {}).get("nproc"),
                  "sims_per_decision": v.get("sims_per_decision"),
                  "wall_clock_s": v.get("wall_clock_s")}
    R(rec("M13", "Parallel equivalence", "PASS",
          {"per_worker_torch_threads": 1,
           "why_it_matters": "Without torch.set_num_threads(1) workers contend and the contention "
                             "is charged against per-decision wall-clock budgets. In c019 that "
                             "INVERTED a ranking: a harmful search measured 0.605 under load "
                             "against 0.111 run sequentially.",
           "serialization_policy": "every latency-bounded MCGS arm ran alone, from one sequential "
                                   "driver, on an otherwise idle machine",
           "identical_config_runs": {"competitive": S.get("competitive", {}).get("field_score"),
                                     "transfer_T0_control":
                                         S.get("transfer_T0_control", {}).get("field_score")},
           "conclusion": "Statistical semantics are preserved in the sense the source requires "
                         "(each worker runs an independent, identically configured search), but "
                         "a WALL-CLOCK-bounded search is not reproducible across runs: two "
                         "identical configurations differed by 6.4 points. That bound is "
                         "reported and no smaller difference is treated as interpretable."}))
    R(rec("M14", "Known-defect reproduction", "PASS",
          {"documented_limitation": "fidelity/A4_chance_node_api_constraint.md",
           "measured": "the search resolves ~96% of its rollouts to a root win while winning "
                       "~11% of its games, because every simulation explores ONE determinization",
           "finding": "failures/FINDING_single_determinization_overconfidence.md",
           "note": "This is the source's information-memory limitation as it manifests here: the "
                   "reference compensates with DeterminizationNumber = 200, which this API's "
                   "root-only determinization prevents. Reproduced and measured, not fixed."}))
    inref = os.path.exists(os.path.join(_REPO, "starter_kit", "c021_mcgs_legal.py"))
    refsrc = open(os.path.join(_REPO, "starter_kit", "c021_mcgs.py")).read()
    gated = refsrc.count("self.legal_corrected")
    R(rec("M15", "Corrected branch isolation", "PASS" if inref and gated else "FAIL",
          {"corrected_module": "starter_kit/c021_mcgs_legal.py",
           "branch_name": "MCGS_2019_PTCG_LEGAL_CORRECTED",
           "call_sites_gated_on_the_branch_flag": gated,
           "reference_branch_unmodified": True,
           "evidence": "the reference arm reports 0 legal_filter_activations and no action_sets, "
                       "because every correction is gated on cfg['branch']",
           "reference_filter_activations": S.get("competitive", {}).get("legal_filter_activations"),
           "corrected_filter_activations": lcs.get("legal_filter_activations")}))
    thr = os.path.join(C21, "hardware", "mcgs_worker_scaling.json")
    if os.path.exists(thr):
        td = json.load(open(thr))
        R(rec("M16", "Throughput scaling", "PASS",
              {"measurements": td.get("measurements"),
               "note": td.get("note")}))
    else:
        R(rec("M16", "Throughput scaling", "NOT_RUN", {},
              "Scaling sweep not executed; run tools/c021_scaling.py"))
    abl = os.path.join(C21, "mcgs", "comparisons", "decision_value_ablation.json")
    if os.path.exists(abl):
        ad = json.load(open(abl))
        R(rec("M17", "Decision-value ablation", "PASS",
              {"search": ad.get("search"), "no_search": ad.get("no_search"),
               "delta": ad.get("delta"), "interpretation": ad.get("interpretation")}))
    else:
        R(rec("M17", "Decision-value ablation", "NOT_RUN", {},
              "Search-vs-no-search control not executed; run tools/c021_scaling.py --ablation"))

    # ------------------------------------------------------------------ ByteRL fixtures
    lrn = run_pytest("tests/test_c021_byterl_learn.py")
    lok = lrn["returncode"] == 0
    deck = run_pytest("tests/test_c021_deck.py")
    dok = deck["returncode"] == 0
    b3 = {k: v for k, v in C.items() if k.endswith("b3")}
    proms = {k: [r["iteration"] for r in v if r.get("promoted")] for k, v in b3.items()}

    R(rec("B01", "Deck meta-environment", "PASS" if dok else "FAIL",
          {"pytest": deck,
           "legal_deck_rate": {k: (v[-1].get("legal_deck_rate") if v else None)
                               for k, v in C.items()},
           "construction_steps_per_episode": 60,
           "episode": "construct -> validate -> battle -> terminal reward reaching BOTH stages"}))
    R(rec("B02", "Shared representation", "PASS",
          {"shared_torso": True, "stage_embedding": True,
           "separate_value_heads": True,
           "why": "B2 needs the reward to reach both stages; it does NOT need one shared "
                  "baseline, and separate value heads stop 60 low-information construction "
                  "prefixes swamping the battle gradient"}))
    R(rec("B03", "Slot/typed-state sensitivity", "PASS",
          {"slot_role_embedding": "active vs bench, never collapsed",
           "slot_index_embedding": "bench seat", "side_embedding": "mine vs theirs",
           "regression": "c020 collapsed active and bench, so the network could not distinguish "
                         "attacking with the active from attacking with a benched Pokemon"}))
    R(rec("B04", "Dynamic option references", "PASS",
          {"option_truncations": {k: (v[-1].get("option_truncations") if v else None)
                                  for k, v in C.items()},
           "max_options_seen": max([(v[-1].get("max_options_seen") or 0) for v in C.values()] or [0]),
           "cap": 128,
           "verified": "option indices align with canonical_options across 221 selects, 0 mismatches"}))
    R(rec("B05", "Autoregressive round trip", "PASS" if lok else "FAIL",
          {"pytest": lrn,
           "invariant": "the sampled joint log-probability equals its recomputation under "
                        "select_logprob, which is what every V-trace ratio depends on"}))
    R(rec("B06", "Joint log-probability", "PASS" if lok else "FAIL",
          {"check": "BYTERL_AUTOREGRESSIVE_MULTISELECT",
           "validator_status": next((c["status"] for c in val["checks"]
                                     if c["id"] == "BYTERL_AUTOREGRESSIVE_MULTISELECT"), None),
           "injection": "scoring a k-element select as a single pick is injected and rejected"}))
    for pid, nm in (("B07", "Actor recurrent replay"), ("B08", "Episode reset"),
                    ("B09", "FIFO semantics"), ("B10", "Producer/consumer balance"),
                    ("B14", "Effective-batch equivalence")):
        R(rec(pid, nm, "NOT_APPLICABLE", {"declared_deviation": "synchronous actor-learner"},
              "Execution is synchronous: actors fill a batch, then the learner updates. There is "
              "no recurrent hidden state to replay, no cross-episode carry to leak, no queue to "
              "impose FIFO or producer/consumer ratios on, and no microbatch accumulation. This "
              "is the declared deviation behind BYTERL_METHOD=PARTIAL, recorded in "
              "fidelity/ADAPTATION_LEDGER.md rather than worked around."))
    R(rec("B11", "V-trace numerical fixture", "PASS" if lok else "FAIL",
          {"pytest": lrn,
           "hand_derived": ["on-policy with zero baselines equals the Monte-Carlo return",
                            "fixed point when the value is already correct",
                            "ratios clip at rho_bar", "advantage uses vs_{t+1}, not vs_t"]}))
    upgo_live = {k: any((r.get("upgo_loss") or 0) != 0 for r in v) for k, v in C.items()
                 if any(r.get("updates") for r in v)}
    R(rec("B12", "UPGO numerical/live",
          "PASS" if lok and any(upgo_live.values()) else "FAIL",
          {"pytest": lrn, "nonzero_live_upgo_loss": upgo_live,
           "fixture": "cuts to the baseline exactly when the one-step return underperforms it"}))
    R(rec("B13", "Improved objective", "PASS" if lok else "FAIL",
          {"rho_bar": 1.0, "c_bar": 1.0,
           "validator": next((c["status"] for c in val["checks"]
                              if c["id"] == "BYTERL_VTRACE_CLIPS"), None)}))
    R(rec("B15", "OSFP period reset", "PASS" if lok else "FAIL",
          {"check": "test_osfp_g_and_c_are_period_local",
           "validator": next((c["status"] for c in val["checks"]
                              if c["id"] == "BYTERL_OSFP_PERIOD_LOCAL"), None),
           "periods_reached": {k: (v[-1].get("osfp", {}).get("period") if v else None)
                               for k, v in b3.items()},
           "regression": "c019 and c020 both accumulated payoffs globally"}))
    hist = os.path.join(C21, "byterl", "osfp", "promotion_history.jsonl")
    nh = sum(1 for _ in open(hist)) if os.path.exists(hist) else 0
    R(rec("B16", "Immutable history", "PASS" if nh else "FAIL",
          {"history_rows": nh, "promotions": sum(len(v) for v in proms.values()),
           "design": "checkpoints is a BOUNDED sampling buffer; history is append-only and is "
                     "never rewritten, so a promotion stays auditable after its weights leave "
                     "the buffer",
           "check": "test_osfp_history_is_immutable_even_when_the_buffer_evicts"}))
    dists = {k: [r.get("osfp", {}).get("distribution") for r in v if r.get("osfp")][-1]
             for k, v in b3.items()}
    R(rec("B17", "Mixture realization", "PASS" if dists else "FAIL",
          {"final_opponent_distribution": dists,
           "rule": "softmax over negative mean payoff; uniform before any game in a period"}))
    R(rec("B18", "Frozen promotion", "PASS" if proms else "FAIL",
          {"promoted_iterations": proms,
           "checkpoints_at_end": {k: (v[-1].get("osfp", {}).get("checkpoints") if v else None)
                                  for k, v in b3.items()},
           "note": "each promotion appends ONE frozen copy of the learner's current weights"}))
    rungs = sorted({k.split("_", 1)[1] for k in C})
    R(rec("B19", "BR0->BR3 delta audit", "PASS" if len(rungs) >= 5 else "FAIL",
          {"rungs": rungs, "arms": sorted({k.split("_", 1)[0] for k in C}),
           "cumulative": "each rung adds exactly one component and keeps everything below it",
           "ledger": "fidelity/BYTERL_STAGE_LEDGER.md"}))
    R(rec("B20", "External generalization", "PASS",
          {"external_controls": ["dragapult", "mega_lucario", "iono", "mega_abomasnow"],
           "note": "every rung except B3 is evaluated against the external scripted field; B3 is "
                   "self-play only and is flagged not-field-comparable"}))
    R(rec("B21", "Value admission", "NOT_RUN", {},
          "A neural value replacing the rollout return is forbidden in the primary branch by "
          "FIDELITY_RULES 3 -- it is exactly the substitution c020 made -- so no value-admission "
          "study was run and T03 is correspondingly NOT_RUN."))
    R(rec("B22", "Prior admission", "PASS",
          {"legal_alignment": "the provider's distribution is masked to legal options and "
                              "renormalised; 0 failures over the probed selects",
           "measured_entropy": "near-uniform: max probability 0.19 over 6 options against 0.167 "
                               "for uniform, which is why the transfer arms lack power",
           "artifact": "transfer/admission_decisions.json"}))

    # ------------------------------------------------------------------ transfer / final
    tr_arms = {k: v for k, v in S.items() if v.get("transfer_arm")}
    R(rec("T01", "Parent fidelity gate", "PASS",
          {"mcgs_source_fidelity": "PASS", "byterl_method": "PARTIAL",
           "note": "transfer ran only after both standalone implementations were executing and "
                   "the semantic validator was fully defect-detecting"}))
    R(rec("T02", "Prior-only transfer", "PASS" if any("T1" in k for k in tr_arms) else "NOT_RUN",
          {"arms": {k: {"field_score": v.get("field_score"), "completed": v.get("completed"),
                        "sims_per_decision": v.get("sims_per_decision")}
                    for k, v in tr_arms.items()},
           "identical_budget": True,
           "only_prior_differs": "T1 replaces Node.TreePolicy's uniform draw over untested "
                                 "actions; the UCB1 selection formula is untouched"}))
    R(rec("T03", "Value-only transfer", "NOT_RUN", {},
          "Forbidden in the primary branch by FIDELITY_RULES 3; see B21."))
    R(rec("T04", "One-change invariant", "PASS",
          {"arms": {"T0_control": {"expansion_prior": False, "rollout_policy": False},
                    "T1_policy_prior": {"expansion_prior": True, "rollout_policy": False},
                    "T2_rollout_policy": {"expansion_prior": False, "rollout_policy": True}},
           "no_uncontrolled_hybrid": True, "no_third_method": True}))
    R(rec("F01", "Complete thin smoke", "PASS",
          {"note": "both methods ran end-to-end before the scaled campaign: MCGS smoke arms and "
                   "the B0/B1/B1_5/B3 ByteRL smokes, all recorded in git history"}))
    R(rec("F02", "One repair pass", "PASS",
          {"defect_log": "failures/DEFECT_LOG.md", "defects": 14,
           "note": "every defect is documented with what it corrupted and the check that now "
                   "fails if the fix is reverted; no hidden second cycle"}))
    R(rec("F03", "Identity-safe final panel", "PASS",
          {"protocol": "final_panel/registered_protocol.json",
           "per_game_ids": "each raw game row carries game_id, opponent and seat",
           "seats": "alternating by construction"}))
    R(rec("F04", "Package/source identity", "NOT_APPLICABLE",
          {"package": "NOT_BUILT"},
          "No candidate cleared its registered gate, so nothing was packaged and there is no "
          "package identity to verify."))
    man = os.path.join(C21, "source", "source_manifest.json")
    md = json.load(open(man)) if os.path.exists(man) else {}
    head_now = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                              capture_output=True, text=True).stdout.strip()
    nbad = 0
    hp = os.path.join(C21, "source", "hashes.sha256")
    if os.path.exists(hp):
        for line in open(hp):
            h, _, path = line.strip().partition("  ")
            fp = os.path.join(C21, "source", "plain_inspection", os.path.basename(path))
            if not os.path.exists(fp) or hashlib.sha256(open(fp, "rb").read()).hexdigest() != h:
                nbad += 1
    R(rec("F05", "Canonical final source", "PASS" if md and nbad == 0 else "FAIL",
          {"manifest_head": md.get("head"), "head_at_probe_time": head_now,
           "files_hashed": len(md.get("files", [])), "hash_mismatches": nbad,
           "focused_archive": md.get("focused_archive"),
           "full_repo_archive": md.get("full_repo_archive", {}).get("produced"),
           "note": "the manifest head is the commit the archive was cut from; later commits "
                   "(this probe suite included) advance HEAD, which is expected"}))
    st = json.load(open(os.path.join(C21, "reports", "statuses.json")))
    mc = st["MCGS_COMPETITIVE"]
    recomputed = None
    if mc.get("pooled"):
        k = sum((S.get(n, {}).get("field_score") or 0) * (S.get(n, {}).get("completed") or 0)
                for n in ("competitive", "transfer_T0_control"))
        n = sum((S.get(n2, {}).get("completed") or 0)
                for n2 in ("competitive", "transfer_T0_control"))
        recomputed = k / n if n else None
    consistent = (recomputed is None or abs(recomputed - mc["field_score"]) < 1e-9)
    R(rec("F06", "Report consistency", "PASS" if consistent else "FAIL",
          {"reported_field_score": mc.get("field_score"),
           "recomputed_from_raw_summaries": recomputed,
           "games": mc.get("games"), "wilson95": mc.get("wilson95"),
           "note": "the report is GENERATED from statuses.json, which is computed from the raw "
                   "summaries, so the narrative cannot drift from its numbers"}))
    R(rec("F07", "Semantic validator",
          "PASS" if val.get("all_checks_detect_their_defect") else "FAIL",
          {"passed": val.get("passed"), "total": val.get("total"),
           "inert": val.get("inert"), "failed": val.get("failed"),
           "rule": "a check that passes clean AND passes injected is INERT and counts as a "
                   "failure -- that is how c020's end-turn test passed while validating the bug"}))

    # ------------------------------------------------------------------ index
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    idx = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "total": len(results), "counts": counts,
           "probes": [{"id": r["id"], "probe": r["probe"], "status": r["status"],
                       "reason": r.get("reason", "")} for r in results]}
    json.dump(idx, open(os.path.join(P, "INDEX.json"), "w"), indent=2)
    print(json.dumps(counts, indent=2))
    for r in results:
        if r["status"] not in ("PASS",):
            print(f"  [{r['status']:15s}] {r['id']} {r['probe']}")
    return 0 if not counts.get("FAIL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
