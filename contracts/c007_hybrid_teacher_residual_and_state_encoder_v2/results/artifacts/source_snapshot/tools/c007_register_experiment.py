"""c007 AC-02: freeze the full experiment BEFORE any dependent experiment (dataset
generation, training, improvement labels, evaluation). Consumes only PRE-registration
inputs already produced: AC-01 dependency hashes, the context-frequency census, the
State Encoder v2 schema, the instrumentation manifest, and the (already timed) model
config. Emits EXPERIMENT_REGISTRATION.md + experiment_registration.json.

No post-hoc architecture or threshold may become the winner (§6). One documented-defect
restart is the only allowed change after this freeze.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import card_vocab, policy_model_v2 as pm, state_encoder_v2 as enc  # noqa: E402

ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                   "results", "artifacts")


def _sha_json(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build():
    dep = json.load(open(os.path.join(ART, "dependency_verification.json")))
    census = json.load(open(os.path.join(ART, "context_frequency_census.json")))
    vocab = card_vocab.build_vocab()
    m = pm.ModelV2(seed=0, aux=True)
    pcount = m.param_count()

    # residual candidate pool ranked by census (frequency x depth); attack_choice_in_MAIN
    # is deliberately EXCLUDED (overriding whole MAIN turn-plans is the unrestricted
    # replacement §1 forbids and corrupts future teacher state, admission rule 8).
    ranked = sorted(census["candidates"].items(), key=lambda kv: -kv[1]["ge2_meaningful"])
    pool = [c for c, _ in ranked if c not in ("attack_choice_in_MAIN", "attack_target")]

    reg = {
        "contract": "c007_hybrid_teacher_residual_and_state_encoder_v2",
        "frozen_before_dependent_experiments": True,
        "dependencies": {
            "c005_final_head": dep["c005_final_head"],
            "c006_final_head": dep["c006_final_head"],
            "c007_initial_head": dep["c007_initial_head"],
            "frozen_teacher_main_sha256": dep["frozen_teacher_main_sha256"],
            "frozen_teacher_deck_sha256": dep["frozen_teacher_deck_sha256"],
            "teacher_id": dep["teacher_id"], "deck_id": dep["frozen_deck_id"],
            "teacher_submission_ref": dep["teacher_submission_ref"],
        },
        "instrumented_teacher": {
            "instrumented_main_sha256": _sha_json(os.path.join(ART, "instrumented_teacher", "main.py")),
            "parity_definition": {
                "replay": ">=15,000 ordered c005/c006 decisions; frozen==instrumented action identity, 0 exceptions",
                "live": "100 fresh cabt games, dual-call harness (compute both, assert equal, drive with instrumented)",
                "outcomes": "engine is random_device-seeded, so H0 vs T is (a) per-decision action identity (dual-call) "
                            "PLUS (b) statistical outcome equivalence over >=200 games, NOT cross-run identity",
            },
            "labels_are_training_targets_only": True,
        },
        "state_encoder_v2": {
            "schema_sha256": _sha_json(os.path.join(ART, "state_encoder_v2_schema.json")),
            "dims": enc.feature_dims(),
        },
        "card_semantics": {"vocab_size": vocab["vocab_size"], "feat_dim": vocab["feat_dim"],
                           "source_hash": vocab["source_hash"],
                           "unseen_card_policy": "deterministic features + zero-init id residual"},
        "model": {
            "family": "ModelV2 (pure-numpy, cg.policy_model_v2)",
            "config": m.cfg, "param_count": pcount,
            "param_band": [500000, 2000000], "hard_max": 3000000,
            "in_band": 500000 <= pcount <= 2000000,
            "variants": {"V2_A": "teacher-action head only (aux=False)",
                         "V2_B": "action head + privileged planning aux heads (aux=True)"},
            "aux_heads": ["plan_main_target(softmax)", "use_support(bce)", "value/outcome(bce)"],
            "aux_coef": {"plan": 0.3, "support": 0.3, "value": 0.3},
            "selection": "validation importance-weighted teacher agreement ONLY; test opened once",
        },
        "seeds": [101, 202, 303],
        "optimizer": {"name": "Adam", "lr": 0.0015, "betas": [0.9, 0.999],
                      "max_epochs": 22, "patience": 5, "batch_size": 256,
                      "early_stopping_metric": "validation importance_weighted_teacher_agreement",
                      "reproducibility": "OMP_NUM_THREADS=1 + fixed seeds"},
        "dataset": {
            "generator": "instrumented teacher plays both seats vs the strategic field; raw obs + "
                         "privileged plan labels + outcome + latency + lineage captured; v2 state derived offline",
            "targets": {"min_games": 600, "min_decisions": 50000},
            "opponents": ["mega_lucario", "mega_abomasnow", "iono", "dragapult (mirror)"],
            "engineering_control": "__control__ (DetControl) — included in data-gen and gauntlet, REPORTED SEPARATELY",
            "split": {"scheme": "whole-game 70/15/15", "seed": 70157, "stratify_by": ["opponent", "teacher_seat"],
                      "test_frozen": True, "no_leakage": True},
            "c006_test_preserved_as_historical_benchmark": True,
        },
        "residual_contexts": {
            "candidate_pool": pool,
            "primary": "dragapult_damage_counter",
            "admission_rule_all_required": [
                ">=300 c007 examples",
                ">=200 examples with two meaningful legal choices",
                "decoder semantics fully supported",
                "teacher/oracle state synchronization valid",
                "counterfactual evaluation stable",
                "H1 calibration acceptable (ECE <= 0.15 in-context)",
                "not primarily forced (forced fraction < 0.5)",
                "residual action does not corrupt future teacher state",
            ],
            "max_admitted": 3,
        },
        "counterfactual_protocol": {
            "state_cloning_capability": "engine search API (search_begin/step/end) verified to fork+rollout, "
                                        "but determinized + random_device-stochastic; search_begin_input is "
                                        "stripped from stored captures.",
            "primary_method": "controlled deterministic policy variants (§12 fallback): a variant alters ONE "
                              "semantic rule in an admitted context; A/B vs teacher in balanced full games; the "
                              "improvement claim is POLICY-LEVEL (global strength), never fabricated per-state labels.",
            "branch_and_rollout": "time-boxed 30-min capability probe recorded under results/artifacts; used at most "
                                  "as a per-state stability check, not as the primary improvement evidence.",
            "positive_label_gate": ["estimated advantage > registered minimum", "one-sided 90% LCB > 0",
                                    "instability acceptable", "no reliability defect"],
            "target_labels": 2000,
            "ambiguous_states_keep_teacher": True,
            "candidate_variants_damage_counter": [
                "V_plan_a: use plan_a.counter when plan_a.attack != 0 (main.py L278-284/L705 plan_a/plan_b mismatch)",
                "V_reset: reset AttackPlan.counter on the early-return path (stale class-attr, L55/L215-216)",
                "V_thresh: corrected HP-band threshold in DAMAGE_COUNTER_ANY (L709 reachability)",
                "V_greedy: greedy knockout-maximizing spread allocation",
            ],
        },
        "gates": {
            "override_confidence_min": 0.60,
            "ood_rule": "per-context: global-feature vector within [1st,99th] percentile envelope of that context's "
                        "training decisions AND legal-option count within training range; else abstain",
            "advantage_lcb_min": 0.0,
            "override_budget_per_game": 5,
            "override_budget_per_context_per_game": 3,
            "safety_veto": "illegal / decoder-unsupported / OOD / forced -> teacher default",
            "non_inferiority": {"metric": "seat-balanced win=1/draw=.5/loss=0 vs teacher",
                                "rule": "one-sided 95% lower bound (5th pct seat-balanced bootstrap) >= 0.47",
                                "orientation_games": 400, "extend_to": 800},
            "reproducible_improvement_any_of": [
                "one matchup >= +5pp with bootstrap P(improvement) >= 0.90",
                "global strength improvement, 90% bootstrap interval above zero (PRIMARY target)",
                "validated residual-context action-value improvement reproduced in a 2nd held-out batch, no full-game regression",
            ],
            "major_regression_blocks": "any matchup >= 7pp below teacher with >= 90% bootstrap probability",
        },
        "submission_rule": "SUBMISSION_C=SUBMIT iff BEST_HYBRID=H2_RESIDUAL (instrumentation valid + encoder accepted "
                           "+ >=1 residual context admitted + perfect reliability + non-inferiority LB>=0.47 + >=1 "
                           "reproducible improvement + no major regression + telemetry complete + package validation)",
        "kaggle_protocol": {"description": "c007 Submission C: hybrid residual <final_commit_short_sha>",
                            "dup_guard": "unique description + recorded archive sha256",
                            "poll": "every 30s, max 20 attempts; pending-after-window allowed; retain ref + refresh cmd",
                            "teacher_refresh_ref": "54948560"},
        "emergency_correction_policy": "one documented code-defect correction may fairly restart affected runs; "
                                       "otherwise no changes after freeze",
    }
    return reg


def to_md(reg):
    g = reg["gates"]
    lines = [
        "# c007 Experiment Registration (frozen before dependent experiments)", "",
        f"Teacher `{reg['dependencies']['teacher_id']}` | deck `{reg['dependencies']['deck_id']}` | "
        f"teacher ref {reg['dependencies']['teacher_submission_ref']}",
        f"c005 {reg['dependencies']['c005_final_head'][:12]} -> c006 {reg['dependencies']['c006_final_head'][:12]} "
        f"-> c007 init {reg['dependencies']['c007_initial_head'][:12]}", "",
        "## Model",
        f"- {reg['model']['family']}: {reg['model']['param_count']:,} params "
        f"(band {reg['model']['param_band']}, hard max {reg['model']['hard_max']:,}; in-band {reg['model']['in_band']})",
        f"- V2-A action-only; V2-B + privileged aux heads {reg['model']['aux_heads']} (coef {reg['model']['aux_coef']})",
        f"- seeds {reg['seeds']}; Adam lr {reg['optimizer']['lr']} max_epochs {reg['optimizer']['max_epochs']} "
        f"patience {reg['optimizer']['patience']}; select on validation iw-agreement only", "",
        "## State encoder v2",
        f"- dims {reg['state_encoder_v2']['dims']}", "",
        "## Dataset",
        f"- targets: >= {reg['dataset']['targets']['min_games']} games / "
        f">= {reg['dataset']['targets']['min_decisions']} decisions",
        f"- opponents {reg['dataset']['opponents']} + control ({reg['dataset']['engineering_control']})",
        f"- split {reg['dataset']['split']}", "",
        "## Residual contexts",
        f"- candidate pool: {reg['residual_contexts']['candidate_pool']}",
        f"- primary: {reg['residual_contexts']['primary']}; admit at most {reg['residual_contexts']['max_admitted']}",
        "- admission requires ALL: " + "; ".join(reg["residual_contexts"]["admission_rule_all_required"]), "",
        "## Counterfactual / improvement labels",
        f"- primary: {reg['counterfactual_protocol']['primary_method']}",
        f"- branch-and-rollout: {reg['counterfactual_protocol']['branch_and_rollout']}",
        f"- positive-label gate: {reg['counterfactual_protocol']['positive_label_gate']}",
        f"- damage-counter variants: {reg['counterfactual_protocol']['candidate_variants_damage_counter']}", "",
        "## Gates",
        f"- override: confidence >= {g['override_confidence_min']}, advantage LCB > {g['advantage_lcb_min']}, "
        f"budget {g['override_budget_per_game']}/game ({g['override_budget_per_context_per_game']}/context)",
        f"- OOD: {g['ood_rule']}",
        f"- non-inferiority: {g['non_inferiority']['rule']} ({g['non_inferiority']['orientation_games']} "
        f"orientation, extend to {g['non_inferiority']['extend_to']})",
        f"- reproducible improvement (any): {g['reproducible_improvement_any_of']}",
        f"- major regression blocks: {g['major_regression_blocks']}", "",
        f"## Submission\n- {reg['submission_rule']}", "",
        f"## Kaggle\n- {reg['kaggle_protocol']}", "",
        f"_{reg['emergency_correction_policy']}_",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--art-dir", default=ART)
    a = p.parse_args(argv)
    reg = build()
    json.dump(reg, open(os.path.join(a.art_dir, "experiment_registration.json"), "w"), indent=2)
    open(os.path.join(a.art_dir, "EXPERIMENT_REGISTRATION.md"), "w").write(to_md(reg))
    print("registered. param_count", reg["model"]["param_count"],
          "in_band", reg["model"]["in_band"])
    print("candidate pool:", reg["residual_contexts"]["candidate_pool"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
