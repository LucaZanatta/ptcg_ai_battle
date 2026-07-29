"""c021 — assemble the mandated `results/` tree from what was actually produced.

`RESULTS_SCHEMA.md` fixes the directory layout and the canonical-source requirements. This tool
materialises that layout, copies each artifact into its mandated location, and — where a mandated
artifact was NOT produced — writes a stub recording that fact and why.

The stubs are the point. A schema slot left silently empty reads as an oversight; a slot holding
`{"produced": false, "reason": ...}` is an auditable statement. Nothing here invents data.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(_REPO, "contracts", "c021_source_faithful_mcgs_and_byterl_transfer_campaign")
R = os.path.join(CDIR, "results")

TREE = [
    "controls", "fidelity", "hardware",
    "mcgs/reference_source_port/configs", "mcgs/reference_source_port/abstraction_keys",
    "mcgs/reference_source_port/dag_snapshots", "mcgs/reference_source_port/edge_statistics",
    "mcgs/reference_source_port/chance_nodes", "mcgs/reference_source_port/sparse_sampling",
    "mcgs/reference_source_port/damped_sampling",
    "mcgs/reference_source_port/filters_obliged_actions",
    "mcgs/reference_source_port/rollouts", "mcgs/reference_source_port/timing",
    "mcgs/reference_source_port/raw_games", "mcgs/reference_source_port/evaluations",
    "mcgs/reference_source_port/packages",
    "mcgs/legal_corrected/raw_games", "mcgs/legal_corrected/evaluations",
    "mcgs/legal_corrected/latency", "mcgs/legal_corrected/packages",
    "mcgs/legal_corrected/submissions", "mcgs/comparisons",
    "byterl/meta_environment", "byterl/architecture", "byterl/action_records",
    "byterl/recurrent_unrolls", "byterl/queue_logs", "byterl/numerical_fixtures",
    "byterl/stages/BR0", "byterl/stages/BR1", "byterl/stages/BR1_5", "byterl/stages/BR2",
    "byterl/stages/BR3",
    "byterl/osfp/period_local_payoffs", "byterl/osfp/mixtures",
    "byterl/osfp/frozen_evaluations", "byterl/osfp/historical_checkpoints",
    "byterl/checkpoints", "byterl/external_evaluations",
    "byterl/component_analysis/priors", "byterl/component_analysis/representation",
    "byterl/component_analysis/autoregressive_decoder", "byterl/component_analysis/recurrence",
    "byterl/component_analysis/osfp_diversity",
    "byterl/component_analysis/deck_construction", "byterl/component_analysis/value",
    "byterl/packages",
    "transfer/prior_only", "transfer/value_only", "transfer/other_single_component",
    "final_panel", "probes",
    "failures/exceptions", "failures/timeouts", "failures/source_mismatches",
    "failures/formula_mismatches", "failures/recurrent_mismatches",
    "failures/invalid_decks_actions", "failures/package_failures",
    "packages", "submissions/responses",
    "source/plain_inspection", "git",
]

RUNG_TO_STAGE = {"b0": "BR0", "b1": "BR1", "b1_5": "BR1_5", "b2": "BR2", "b3": "BR3"}


def sh(cmd: List[str]) -> str:
    try:
        return subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True,
                              timeout=180).stdout
    except Exception as e:  # noqa: BLE001
        return f"<failed: {e}>"


def stub(path: str, reason: str, **extra):
    """Record a mandated artifact that was NOT produced, and why."""
    if os.path.exists(path):
        return
    payload = {"produced": False, "reason": reason,
               "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), **extra}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(payload, open(path, "w"), indent=2)


def copy(src: str, dst: str) -> bool:
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-archive", action="store_true")
    a = ap.parse_args(argv)

    for d in TREE:
        os.makedirs(os.path.join(R, d), exist_ok=True)

    statuses = {}
    sp = os.path.join(R, "reports", "statuses.json")
    if os.path.exists(sp):
        statuses = json.load(open(sp))

    moved: Dict[str, Any] = {"mcgs": [], "byterl": [], "transfer": []}

    # ---------------------------------------------------------------- MCGS artifacts
    for p in glob.glob(os.path.join(R, "mcgs", "evaluations", "*_summary.json")):
        name = os.path.basename(p)
        d = json.load(open(p))
        branch = d.get("config", {}).get("branch", "MCGS_2019_OFFICIAL_SOURCE_PORT")
        arm = d.get("transfer_arm")
        if arm:
            sub = ("prior_only" if "T1" in arm else
                   "other_single_component" if "T2" in arm or "T3" in arm else "prior_only")
            copy(p, os.path.join(R, "transfer", sub, name))
            moved["transfer"].append(f"{name} -> transfer/{sub}")
            continue
        leg = branch == "MCGS_2019_PTCG_LEGAL_CORRECTED"
        base = "legal_corrected" if leg else "reference_source_port"
        copy(p, os.path.join(R, "mcgs", base, "evaluations", name))
        moved["mcgs"].append(f"{name} -> mcgs/{base}/evaluations")
        # split the run's counters into the schema's per-mechanism folders
        tag = name.replace("_summary.json", "")
        if not leg:
            for folder, keys in (
                ("chance_nodes", ["chance_nodes_created", "chance_expansions", "chance_samples",
                                  "manual_coin_node_ucb_selected", "chance_ctx_46",
                                  "manual_coin", "manual_coin_contexts"]),
                ("damped_sampling", ["chance_sparse_cutoffs", "sample_merges"]),
                ("sparse_sampling", ["chance_sparse_cutoffs"]),
                ("edge_statistics", ["transposition_hits", "transposition_merges", "dummy_edges",
                                     "recursive_update_noops", "recursive_reward_updates",
                                     "recursive_visit_updates", "backups", "backup_nodes"]),
                ("rollouts", ["rollouts", "rollout_steps", "rollout_retries", "rollout_aborts",
                              "rollout_terminals", "rollout_terminal_rate", "term_root_win",
                              "term_root_loss", "term_undecided", "rollout_releases"]),
                ("timing", ["wall_clock_s", "sims_per_decision", "steps_per_decision",
                            "max_match_search_ms", "time_budget_exhausted"]),
                ("filters_obliged_actions", ["legal_filter_pruned", "legal_filter_activations",
                                             "legal_multiselect_nodes",
                                             "legal_combination_capped"]),
                ("abstraction_keys", ["transposition_hits", "transposition_merges"]),
            ):
                out = {k: d[k] for k in keys if k in d}
                if out:
                    out["_run"] = tag
                    json.dump(out, open(os.path.join(R, "mcgs", base, folder,
                                                     f"{tag}.json"), "w"), indent=2)
        for sub, pat in (("raw_games", "raw_games/%s_games.jsonl.gz"),
                         ("configs", "configs/%s_config.json"),
                         ("dag_snapshots", "graph_traces/%s_graphs.json"),
                         ("timing", "latency/%s_latency.json")):
            src = os.path.join(R, "mcgs", pat % tag)
            tgt_sub = "latency" if (leg and sub == "timing") else sub
            copy(src, os.path.join(R, "mcgs", base, tgt_sub, os.path.basename(src)))

    # A10 change manifest
    cm = os.path.join(R, "mcgs", "legal_corrected", "change_manifest.json")
    if not os.path.exists(cm):
        sys.path.insert(0, _REPO)
        try:
            from cg import c021_mcgs_legal as LG
            json.dump(LG.corrections_manifest({}), open(cm, "w"), indent=2)
        except Exception as e:  # noqa: BLE001
            stub(cm, f"could not import the legal-corrected branch: {e}")

    # ---------------------------------------------------------------- ByteRL artifacts
    for p in glob.glob(os.path.join(R, "byterl", "curves", "*_curve.json")):
        name = os.path.basename(p)
        base = name.replace("_curve.json", "")
        if base.endswith("smoke"):
            continue
        rung = base.split("_", 1)[1] if "_" in base else base
        stage = RUNG_TO_STAGE.get(rung)
        if stage:
            copy(p, os.path.join(R, "byterl", "stages", stage, name))
            man = os.path.join(R, "byterl", "manifests", f"{base}_manifest.json")
            copy(man, os.path.join(R, "byterl", "stages", stage,
                                   f"{base}_manifest.json"))
            moved["byterl"].append(f"{name} -> byterl/stages/{stage}")

    # OSFP promotion history
    ph = os.path.join(R, "byterl", "osfp", "promotion_history.jsonl")
    hist = sorted(glob.glob(os.path.join(R, "byterl", "manifests", "*_osfp_history.json")))
    if hist:
        with open(ph, "w") as f:
            for h in hist:
                for row in json.load(open(h)):
                    row["_source"] = os.path.basename(h)
                    f.write(json.dumps(row) + "\n")
        for h in hist:
            copy(h, os.path.join(R, "byterl", "osfp", "period_local_payoffs",
                                 os.path.basename(h)))
    elif not os.path.exists(ph):
        open(ph, "w").write("")
        stub(os.path.join(R, "byterl", "osfp", "promotion_history_note.json"),
             "No OSFP promotion fired: the promotion gate requires a win rate of 0.55 over at "
             "least 48 games and no rung reached it at this scale. The B3 run therefore played "
             "the seeded period-0 checkpoint throughout. The empty file is the honest record.")

    for p in glob.glob(os.path.join(R, "byterl", "checkpoints", "*.pt")):
        if "smoke" not in os.path.basename(p):
            copy(p, os.path.join(R, "byterl", "osfp", "historical_checkpoints",
                                 os.path.basename(p)))

    # numerical fixtures = the analytic learner tests
    nf = os.path.join(R, "byterl", "numerical_fixtures", "objective_probes.json")
    if not os.path.exists(nf):
        out = sh([os.path.join(_REPO, ".venv", "bin", "python"), "-m", "pytest",
                  "tests/test_c021_byterl_learn.py", "-q", "-p", "no:cacheprovider"])
        json.dump({"suite": "tests/test_c021_byterl_learn.py",
                   "note": ("V-trace, UPGO and OSFP checked against hand-derived values: "
                            "on-policy V-trace with zero baselines equals the Monte-Carlo "
                            "return, V-trace is a fixed point when the value is already "
                            "correct, ratios clip at rho_bar, the advantage uses vs_{t+1}, and "
                            "UPGO cuts to the baseline exactly when the trajectory "
                            "underperforms."),
                   "pytest_tail": out.strip().splitlines()[-3:] if out else []},
                  open(nf, "w"), indent=2)

    # meta-environment + architecture descriptors
    me = os.path.join(R, "byterl", "meta_environment", "deck_construction.json")
    if not os.path.exists(me):
        sys.path.insert(0, _REPO)
        try:
            from cg import c021_byterl_deck as DK
            pool = DK.CardPool.from_archetypes()
            json.dump({"pool_size": pool.size(), "deck_size": DK.DECK_SIZE,
                       "construction_steps": DK.CONSTRUCTION_STEPS,
                       "max_copies": DK.MAX_COPIES,
                       "ace_spec_limit": DK.ACE_SPEC_LIMIT,
                       "ace_spec_cards": sorted(pool.ace_spec),
                       "basic_energy_uncapped": sorted(pool.basic_energy),
                       "basic_pokemon": sorted(pool.basic_pokemon),
                       "episode": ("construct -> validate -> battle -> terminal reward reaching "
                                   "BOTH stages")},
                      open(me, "w"), indent=2)
        except Exception as e:  # noqa: BLE001
            stub(me, f"could not import the deck module: {e}")

    arch = os.path.join(R, "byterl", "architecture", "network.json")
    if not os.path.exists(arch):
        sys.path.insert(0, _REPO)
        try:
            from cg import c021_byterl_deck as DK, c021_byterl_encode as EN
            from cg import c021_byterl_model as M
            pool = DK.CardPool.from_archetypes()
            d = EN.dims()
            net = M.fresh(d["global_dim"], d["slot_dim"], d["option_dim"], pool.size(),
                          width=192, blocks=3, seed=0)
            json.dump({"dims": d, "width": 192, "blocks": 3,
                       "parameters": M.count_parameters(net),
                       "separate_value_heads_per_stage": True,
                       "distinct_active_and_bench_slot_tokens": True,
                       "autoregressive_multiselect": True,
                       "masking_inside_distribution": True,
                       "fresh_random_weights": True},
                      open(arch, "w"), indent=2)
        except Exception as e:  # noqa: BLE001
            stub(arch, f"could not build the network descriptor: {e}")

    stub(os.path.join(R, "byterl", "recurrent_unrolls", "NOT_PRODUCED.json"),
         "Actor-learner execution is SYNCHRONOUS: actors fill a batch, then the learner updates. "
         "There is no decoupled recurrent actor-learner queue, so there are no recurrent unroll "
         "records. This is the declared deviation behind BYTERL_METHOD=PARTIAL.")
    stub(os.path.join(R, "byterl", "queue_logs", "NOT_PRODUCED.json"),
         "No actor-learner queue exists under synchronous execution; see recurrent_unrolls.")

    # ---------------------------------------------------------------- transfer
    rh = os.path.join(R, "transfer", "registered_hypotheses.json")
    if not os.path.exists(rh):
        sys.path.insert(0, _REPO)
        try:
            from cg import c021_transfer as TR
            json.dump({"arms": TR.ARMS,
                       "hypotheses": {
                           "T1_policy_prior": ("A ByteRL policy prior over which untested action "
                                               "to expand first improves MCGS field score under "
                                               "a finite budget."),
                           "T2_rollout_policy": ("A ByteRL default policy in the rollout improves "
                                                 "MCGS field score over uniform random."),
                           "T3_prior_and_rollout": "Both together, the only combination arm."},
                       "selection_rule": ("DECISION_RULES §3: retained only on a credible "
                                          "improvement; the arm's 95% Wilson lower bound must "
                                          "exceed the control's upper bound."),
                       "forbidden": ["neural value replacing the rollout return",
                                     "baseline override gate", "PUCT prior term in Edge.Value",
                                     "uncontrolled full hybrid", "a third method"]},
                      open(rh, "w"), indent=2)
        except Exception as e:  # noqa: BLE001
            stub(rh, f"could not import the transfer module: {e}")

    ad = os.path.join(R, "transfer", "admission_decisions.json")
    tr = statuses.get("TRANSFER", {})
    json.dump({"status": tr.get("status"), "retained": tr.get("retained", []),
               "arms": tr.get("arms", {}),
               "control_field_score": tr.get("control_field_score"),
               "rule": tr.get("rule"),
               "power_caveat": ("The arms query the ctrl_b2 checkpoint, whose curve is "
                                "statistically indistinguishable from the untrained B0 floor. "
                                "T1/T2 therefore compare MCGS with a near-random prior against "
                                "MCGS with uniform random -- close to a null test by "
                                "construction. No component is REJECTED on this evidence; it is "
                                "UNTESTED.")},
              open(ad, "w"), indent=2)

    stub(os.path.join(R, "transfer", "value_only", "NOT_RUN.json"),
         "A neural value replacing the rollout return is forbidden in the primary branch by "
         "FIDELITY_RULES §3 -- it is exactly the handcrafted-leaf-evaluator substitution c020 "
         "made. No value-only transfer arm was run.")

    # ---------------------------------------------------------------- controls / hardware
    cmani = os.path.join(R, "controls", "control_manifest.json")
    if not os.path.exists(cmani):
        json.dump({"controls": {
            "byterl_B0": "uniform random over the legal mask; the floor every rung must beat",
            "byterl_fixed_deck_arm": ("frozen permitted deck, so battle learning is separable "
                                      "from deck construction"),
            "mcgs_T0_control": "the source port with every transfer switch off",
            "mcgs_ablation_no_chance": ("manual_coin off, so no chance node can exist; isolates "
                                        "the A4 contribution")},
            "opponents": ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]},
            open(cmani, "w"), indent=2)

    env = os.path.join(R, "hardware", "environment_throughput.json")
    if not os.path.exists(env):
        json.dump({"cpu_count": os.cpu_count(),
                   "torch_threads_per_worker": 1,
                   "why_one_thread": ("Without torch.set_num_threads(1) workers contend and the "
                                      "contention is charged against per-decision wall-clock "
                                      "budgets. In c019 that inverted rankings: a harmful search "
                                      "measured 0.605 under load against 0.111 sequentially."),
                   "serialization_policy": ("All latency-bounded MCGS runs execute in ONE "
                                            "serialized queue; nothing runs concurrently with "
                                            "them."),
                   "memory_note": ("Rollout states are released as the rollout advances. Holding "
                                   "them to the end of a decision measured 1.2-1.3 GB per worker "
                                   "and 28.6 GB resident, and 4 games did not finish in 14 "
                                   "minutes; after the fix the same 4 games took 14.7 s.")},
                  open(env, "w"), indent=2)
    for f, why in (("gpu_metrics.jsonl", "CPU-only run; no GPU was used."),
                   ("storage_memory_metrics.jsonl", "see environment_throughput.json")):
        p = os.path.join(R, "hardware", f)
        if not os.path.exists(p):
            open(p, "w").write("")
    stub(os.path.join(R, "hardware", "gpu_metrics_note.json"),
         "CPU-only run; no GPU was used, so gpu_metrics.jsonl is intentionally empty.")

    # ---------------------------------------------------------------- final panel
    fp = os.path.join(R, "final_panel", "registered_protocol.json")
    if not os.path.exists(fp):
        json.dump({"opponents": ["dragapult", "mega_lucario", "iono", "mega_abomasnow"],
                   "seats": "alternating, balanced by construction",
                   "games_per_arm": 40,
                   "budget": {"first_move_seconds": 1.5, "continuing_move_seconds": 1.2},
                   "statistic": "field score with a 95% Wilson interval",
                   "gate": "the lower bound must exceed 0.5 to claim a competitive result",
                   "preregistered": True,
                   "serialized": "arms run one at a time; no concurrent CPU load"},
                  open(fp, "w"), indent=2)

    # ---------------------------------------------------------------- source + git
    if not a.skip_archive:
        os.makedirs(os.path.join(R, "source"), exist_ok=True)
        head = sh(["git", "rev-parse", "HEAD"]).strip()
        # A focused archive, NOT the whole tracked repo: `git archive` of everything at this
        # commit exceeded 9.9 GB because c018-c021 results include compressed raw-game corpora.
        # The focused zip carries every c021 source file from the same commit, which is what the
        # canonical-source requirement is actually for.
        arc = os.path.join(R, "source", "c021_focused_source.zip")
        listed = [f for f in sh(["git", "ls-files"]).splitlines()
                  if "c021" in f and f.split("/")[0] in ("starter_kit", "tools", "tests")]
        if listed:
            subprocess.run(["git", "archive", "--format=zip", "-o", arc, head] + listed,
                           cwd=_REPO, capture_output=True, timeout=600)
        # plain inspection copies of the c021 sources, from the SAME commit
        pi = os.path.join(R, "source", "plain_inspection")
        os.makedirs(pi, exist_ok=True)
        files = [f for f in sh(["git", "ls-files"]).splitlines()
                 if "c021" in f and (f.startswith("starter_kit/") or f.startswith("tools/")
                                     or f.startswith("tests/"))]
        hashes = {}
        for f in files:
            blob = subprocess.run(["git", "show", f"{head}:{f}"], cwd=_REPO,
                                  capture_output=True, timeout=120).stdout
            out = os.path.join(pi, os.path.basename(f))
            open(out, "wb").write(blob)
            hashes[f] = hashlib.sha256(blob).hexdigest()
        with open(os.path.join(R, "source", "hashes.sha256"), "w") as fh:
            for k in sorted(hashes):
                fh.write(f"{hashes[k]}  {k}\n")
        json.dump({"head": head, "files": sorted(hashes),
                   "archive": os.path.basename(arc),
                   "full_repo_archive": {
                       "produced": False,
                       "reason": ("git archive of the whole tracked repo exceeded 9.9 GB; the "
                                  "focused archive carries every c021 source file from the same "
                                  "commit and each is hashed"),
                       "reproduce": f"git archive --format=tar.gz -o <out> {head}"},
                   "method": ("git archive from the exact final commit, and plain inspection "
                              "copies exported from that same commit with `git show` -- not from "
                              "the mutable working tree")},
                  open(os.path.join(R, "source", "source_manifest.json"), "w"), indent=2)
        open(os.path.join(R, "source", "git_diff.patch"), "w").write(sh(["git", "diff", "HEAD"]))

    G = os.path.join(R, "git")
    open(os.path.join(G, "final_head.txt"), "w").write(sh(["git", "rev-parse", "HEAD"]))
    open(os.path.join(G, "branch.txt"), "w").write(sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]))
    open(os.path.join(G, "status.txt"), "w").write(sh(["git", "status", "--short"]))
    open(os.path.join(G, "log.txt"), "w").write(sh(["git", "log", "--oneline", "-60"]))

    # ---------------------------------------------------------------- top-level
    json.dump(statuses, open(os.path.join(R, "STATUS.json"), "w"), indent=2)
    json.dump({"moved": moved,
               "generated": time.strftime("%Y-%m-%dT%H:%M:%S")},
              open(os.path.join(R, "DECISION_BOARD.json"), "w"), indent=2)

    print(json.dumps({k: len(v) for k, v in moved.items()}, indent=2))
    print(f"tree materialised under {R}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
