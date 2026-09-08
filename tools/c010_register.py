"""c010 AC-02/AC-03: register the protected baselines and the three arms.

Resolves the exact c008 R1 PPO recipe from the c008 artifacts AND the c008 implementation
source (both hashed for provenance), registers B0/I0/T as protected, and emits a configuration
diff proving Arms A and B equal exact R1 while Arm C differs in exactly the three registered
values. Everything is frozen before any training runs.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C = {k: os.path.join(_REPO, "contracts", v) for k, v in {
    "c005": "c005_teacher_import_submission_and_dataset",
    "c007": "c007_hybrid_teacher_residual_and_state_encoder_v2",
    "c008": "c008_fixed_deck_teacher_anchored_rl",
    "c009": "c009_amendment_c008",
    "c010": "c010_fixed_deck_rl_loop_v2"}.items()}
ART = {k: os.path.join(v, "results", "artifacts") for k, v in C.items()}

ARM_C_CHANGES = {"learning_rate": 3e-5, "rollout_game_target": 256,
                 "min_trainable_decisions": 32768}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def resolve_exact_r1():
    """Resolve the exact c008 R1 configuration from c008's registration AND implementation."""
    c8 = json.load(open(os.path.join(ART["c008"], "experiment_registration.json")))
    ppo = c8["ppo"]
    src = os.path.join(_REPO, "tools", "train_rl.py")
    src_txt = open(src).read()
    # the c008 implementation collects while (games < target) OR (decisions < min):
    # i.e. it continues until BOTH thresholds are satisfied -- exactly c010 §9's rule.
    impl_rule_ok = 'while n_games < PPO_CFG["target_games"] or n_dec < PPO_CFG["min_decisions"]:' in src_txt
    recipe = {
        "gamma": ppo["gamma"], "gae_lambda": ppo["gae_lambda"], "clip": ppo["clip"],
        "value_coef": ppo["value_coef"],
        "entropy_coef_start": ppo["entropy_coef"]["start"],
        "entropy_coef_end": ppo["entropy_coef"]["end"],
        "entropy_schedule": ppo["entropy_coef"]["schedule"],
        "max_grad_norm": ppo["max_grad_norm"], "epochs": ppo["epochs_per_rollout"],
        "optimizer": ppo["optimizer"], "learning_rate": ppo["lr"]["R1"],
        "weight_decay": ppo["weight_decay"],
        "rollout_game_target": ppo["target_rollout_games"],
        "min_trainable_decisions": ppo["min_trainable_decisions_per_update"],
        "minibatch": ppo["minibatch"],
        "advantage_normalization": ppo["advantage_normalization"],
        "value_clipping": ppo["value_clipping"],
        "rollout_rule": "continue collecting until BOTH the game target and the trainable-decision "
                        "minimum are reached (c010 §9); verified present in the c008 implementation",
    }
    provenance = {
        "c008_registration": os.path.relpath(
            os.path.join(ART["c008"], "experiment_registration.json"), _REPO),
        "c008_registration_sha256": sha(os.path.join(ART["c008"], "experiment_registration.json")),
        "c008_implementation": "tools/train_rl.py",
        "c008_implementation_sha256": sha(src),
        "implementation_matches_both_thresholds_rule": impl_rule_ok,
        "reused_modules": {m: sha(os.path.join(_REPO, "starter_kit", m + ".py"))
                           for m in ("ppo", "rl_policy", "rl_env")},
    }
    return recipe, provenance


def build():
    dep = json.load(open(os.path.join(ART["c010"], "dependency_verification.json")))
    creg = json.load(open(os.path.join(ART["c009"], "candidate_checkpoint_registry.json")))
    b0, i0 = creg["B0_v2a"], creg[dep["I0"]["candidate_id"]]
    baselines = dep["c010_registered_baselines"]

    registry = {
        "B0": {"candidate_id": "B0_v2a", "role": "untouched supervised initialization",
               "checkpoint_path": b0["checkpoint_path"], "checkpoint_sha256": b0["checkpoint_sha256"],
               "kind": "rl_ckpt_from_v2a", "training_games": 0, "protected": True,
               "c010_teacher_score": baselines["B0"]["teacher"],
               "c010_field_score": baselines["B0"]["field"],
               "source": "c007 selected V2-A"},
        "I0": {"candidate_id": dep["I0"]["candidate_id"], "role": "protected incumbent",
               "checkpoint_path": i0["checkpoint_path"], "checkpoint_sha256": i0["checkpoint_sha256"],
               "kind": "rl_ckpt", "training_games": i0["training_games"], "protected": True,
               "c010_teacher_score": baselines["I0"]["teacher"],
               "c010_field_score": baselines["I0"]["field"],
               "source": "c008 R1 seed 101 validation-selected checkpoint, resolved through c009"},
        "T": {"candidate_id": "T_teacher", "role": "frozen rule teacher (reference/opponent)",
              "checkpoint_path": os.path.relpath(
                  os.path.join(ART["c005"], "frozen_teacher", "main.py"), _REPO),
              "checkpoint_sha256": dep["frozen_teacher_main_sha256"],
              "kind": "frozen_teacher", "protected": True},
        "_metric_definitions": {
            "teacher_score": "balanced match-point rate vs T (win 1 / draw 0.5 / loss 0)",
            "strategic_field_score": "average balanced score vs Mega Lucario, Iono, Mega Abomasnow "
                                     "(c010 §17; the Dragapult mirror is NOT in the field)",
            "promotion_composite": "0.55*teacher + 0.15*lucario + 0.15*iono + 0.15*abomasnow",
            "note": "c010 §1 and inputs quote the c009 field values (0.1525 / 0.2550), which averaged "
                    "FOUR opponents including the mirror. Under c010 §17's registered three-opponent "
                    "metric the same c009 raw games give B0 0.1533 and I0 0.2900; c010 uses the §17 "
                    "values for every gate so the incumbent's bar is not silently lowered.",
        },
    }

    recipe, provenance = resolve_exact_r1()
    arm_c = dict(recipe); arm_c.update(ARM_C_CHANGES)
    ctx = json.load(open(os.path.join(C["c010"], "inputs", "c010_context.json")))

    experiment = {
        "contract": "c010_fixed_deck_rl_loop_v2",
        "frozen_before_training": True,
        "frozen_deck_id": dep["frozen_deck_id"],
        "frozen_deck_fingerprint": dep["frozen_deck_fingerprint"],
        "chain_final_heads": dep["chain_final_heads"],
        "exact_r1_recipe": recipe, "exact_r1_provenance": provenance,
        "environment": {
            "reused_from": "c008/c009 validated environment and action decoder",
            "step": "one trainable step per non-forced selection; forced decisions bypass policy loss",
            "masking": "legal-action masking; illegal options have exactly zero probability",
            "multi_select": "sequential masked-without-replacement log-prob sums; variable "
                            "cardinality uses the registered STOP decoder",
            "unsupported_forms": "explicit defect, never silent teacher fallback",
            "reward": {"win": 1, "draw": 0, "loss": -1, "intermediate": 0},
        },
        "population": {
            "with_lagged": {"teacher": 0.35, "mega_lucario": 0.20, "iono": 0.20,
                            "lagged_selfplay": 0.15, "control": 0.10},
            "before_lagged": "15% redistributed proportionally across teacher/lucario/iono "
                             "(0.42 / 0.24 / 0.24), control 0.10",
            "seats": "~50/50, sampled per game and recorded",
            "lagged_rule": "snapshot every 5,000 games after 5,000; keep 3 most recent; sample "
                           "uniformly; never the current mutable parameters",
            "abomasnow": "EVALUATION ONLY — never a training opponent",
            "identical_across_arms": True,
        },
        "arms": {
            "A": {"purpose": "exact reproducibility from B0", "initialization": "B0",
                  "recipe": "exact_r1", "ppo": recipe, "seeds": [311, 322, 333],
                  "max_games_per_seed": 12000, "planned_minimum_per_seed": 10000,
                  "evaluation_points": [0, 2500, 5000, 7500, 10000, 12000],
                  "early_stop": ["reliability failure", "checkpoint corruption",
                                 "two confirmed catastrophic regressions", "global compute safety limit"],
                  "note": "a weak small screen alone may NOT terminate a reproducibility seed early"},
            "B": {"purpose": "exact continuation from I0", "initialization": "I0",
                  "recipe": "exact_r1", "ppo": recipe, "seeds": [411, 422, 433],
                  "max_games_per_seed": 7500,
                  "evaluation_points": [0, 2500, 5000, 7500],
                  "early_stop": ["two consecutive confirmation evaluations with teacher AND field "
                                 ">=5pp below I0 at >=90% probability of genuine regression"]},
            "C": {"purpose": "minimally stabilized continuation from I0", "initialization": "I0",
                  "recipe": "exact_r1_plus_three_changes", "ppo": arm_c,
                  "seeds": [511, 522, 533], "max_games_per_seed": 20000,
                  "evaluation_points": [0, 2500, 5000, 7500, 10000, 15000, 20000],
                  "changes_vs_exact_r1": ARM_C_CHANGES,
                  "early_stop": ["two confirmed severe regressions",
                                 "three consecutive registered evaluations after game 7,500 with no "
                                 "point gain above 1.5pp on either teacher or field score"],
                  "diagnostics_only": "KL to I0 and to the previous promoted checkpoint is LOGGED "
                                      "only; it is never optimized"},
        },
        "budgets": {"arm_A": 36000, "arm_B": 22500, "arm_C": 60000, "total": 118500,
                    "hard_maximum_including_spillover": 120000,
                    "evaluation_games_counted_separately": True},
        "panels": {
            "screen": {"teacher": 20, "mega_lucario": 10, "iono": 10, "mega_abomasnow": 10,
                       "per_seat": True, "total_per_checkpoint": 100},
            "confirmation": {"teacher": 100, "mega_lucario": 50, "iono": 50, "mega_abomasnow": 50,
                             "per_seat": True, "total_per_checkpoint": 500},
            "final": {"teacher": 200, "mega_lucario": 100, "iono": 100, "mega_abomasnow": 100,
                      "per_seat": True, "total_per_finalist": 1000,
                      "teacher_extension_to": 800},
            "control": "diagnostic only; excluded from promotion metrics",
        },
        "nomination_rule": ["promotion composite exceeds branch best",
                            "teacher score improves by >= 3pp",
                            "strategic-field score improves by >= 4pp",
                            "it is the branch's final registered checkpoint"],
        "gates": {
            "major_regression": "candidate <= baseline - 0.07 AND bootstrap P(regression) >= 0.90",
            "exact_reproducibility": "§18 (six conditions)",
            "exact_continuation": "§19", "stabilized_continuation": "§20",
            "promotion": "§21 (I0 replaced only on a strictly better, statistically supported, "
                         "regression-free candidate)",
            "teacher_non_inferiority": "one-sided 95% lower bound >= 0.47 (unchanged c008 rule)",
            "submission": "§23",
        },
        "teacher_submission_ref": ctx["teacher_submission_ref"],
        "protected": ["B0", "I0"],
    }

    # ---- configuration diff (AC-03) ----
    def diff(a, b):
        keys = sorted(set(a) | set(b))
        return {k: {"exact_r1": a.get(k), "arm": b.get(k)} for k in keys if a.get(k) != b.get(k)}

    dA, dB, dC = diff(recipe, recipe), diff(recipe, recipe), diff(recipe, arm_c)
    cdiff = {
        "exact_r1_recipe": recipe,
        "arm_A_vs_exact_r1": {"differences": dA, "identical": not dA},
        "arm_B_vs_exact_r1": {"differences": dB, "identical": not dB},
        "arm_C_vs_exact_r1": {"differences": dC,
                              "changed_keys": sorted(dC),
                              "expected_changed_keys": sorted(ARM_C_CHANGES),
                              "changes_exactly_the_three_registered_values":
                                  sorted(dC) == sorted(ARM_C_CHANGES)
                                  and all(dC[k]["arm"] == ARM_C_CHANGES[k] for k in dC)},
        "initializations": {"A": "B0", "B": "I0", "C": "I0"},
        "population_identical_across_arms": True,
        "prohibited_in_all_arms": ["teacher behavioural-cloning replay", "optimized KL loss",
                                   "reward shaping", "deck changes", "architecture-family changes",
                                   "random-initialized RL", "search/MCTS", "unregistered tuning",
                                   "training on Mega Abomasnow"],
    }
    return registry, experiment, cdiff


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=ART["c010"])
    p.add_argument("--log-dir", default=os.path.join(C["c010"], "results", "test_logs"))
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True); os.makedirs(a.log_dir, exist_ok=True)
    registry, experiment, cdiff = build()
    json.dump(registry, open(os.path.join(a.out_dir, "baseline_incumbent_registry.json"), "w"), indent=2)
    json.dump(experiment, open(os.path.join(a.out_dir, "experiment_registry.json"), "w"), indent=2)
    json.dump(cdiff, open(os.path.join(a.out_dir, "arm_configuration_diff.json"), "w"), indent=2)

    checks = [
        ("B0_hash_matches_disk", sha(os.path.join(_REPO, registry["B0"]["checkpoint_path"]))
         == registry["B0"]["checkpoint_sha256"]),
        ("I0_hash_matches_disk", sha(os.path.join(_REPO, registry["I0"]["checkpoint_path"]))
         == registry["I0"]["checkpoint_sha256"]),
        ("B0_and_I0_protected", registry["B0"]["protected"] and registry["I0"]["protected"]),
        ("I0_is_c008_R1_seed101", registry["I0"]["candidate_id"] == "R1_101"),
        ("arm_A_equals_exact_r1", cdiff["arm_A_vs_exact_r1"]["identical"]),
        ("arm_B_equals_exact_r1", cdiff["arm_B_vs_exact_r1"]["identical"]),
        ("arm_C_changes_exactly_three", cdiff["arm_C_vs_exact_r1"]["changes_exactly_the_three_registered_values"]),
        ("arm_C_lr_3e-5", experiment["arms"]["C"]["ppo"]["learning_rate"] == 3e-5),
        ("arm_C_rollout_256", experiment["arms"]["C"]["ppo"]["rollout_game_target"] == 256),
        ("arm_C_min_decisions_32768", experiment["arms"]["C"]["ppo"]["min_trainable_decisions"] == 32768),
        ("exact_r1_lr_1e-4", experiment["exact_r1_recipe"]["learning_rate"] == 1e-4),
        ("both_threshold_rollout_rule_verified",
         experiment["exact_r1_provenance"]["implementation_matches_both_thresholds_rule"]),
        ("budget_total_118500", experiment["budgets"]["total"] == 118500),
        ("hard_max_120000", experiment["budgets"]["hard_maximum_including_spillover"] == 120000),
        ("seeds_registered", experiment["arms"]["A"]["seeds"] == [311, 322, 333]
         and experiment["arms"]["B"]["seeds"] == [411, 422, 433]
         and experiment["arms"]["C"]["seeds"] == [511, 522, 533]),
        ("abomasnow_evaluation_only", "EVALUATION ONLY" in experiment["population"]["abomasnow"]),
    ]
    all_ok = all(c[1] for c in checks)
    lines = ["c010 AC-02/AC-03 baseline + arm registration", "=" * 60,
             f"B0 {registry['B0']['checkpoint_sha256'][:16]} teacher={registry['B0']['c010_teacher_score']} "
             f"field={registry['B0']['c010_field_score']:.4f} (PROTECTED)",
             f"I0 {registry['I0']['candidate_id']} {registry['I0']['checkpoint_sha256'][:16]} "
             f"teacher={registry['I0']['c010_teacher_score']} "
             f"field={registry['I0']['c010_field_score']:.4f} @ {registry['I0']['training_games']} games (PROTECTED)",
             f"deck fingerprint {experiment['frozen_deck_fingerprint'][:16]}", "",
             f"exact R1 recipe resolved from {experiment['exact_r1_provenance']['c008_registration']} "
             f"+ {experiment['exact_r1_provenance']['c008_implementation']}",
             f"  lr={experiment['exact_r1_recipe']['learning_rate']} "
             f"rollout={experiment['exact_r1_recipe']['rollout_game_target']} "
             f"min_dec={experiment['exact_r1_recipe']['min_trainable_decisions']} "
             f"epochs={experiment['exact_r1_recipe']['epochs']} clip={experiment['exact_r1_recipe']['clip']}",
             f"Arm C changes: {cdiff['arm_C_vs_exact_r1']['changed_keys']}", ""]
    for n, ok in checks:
        lines.append(f"  [{'OK ' if ok else 'FAIL'}] {n}")
    lines.append(f"\nALL_OK = {all_ok}")
    open(os.path.join(a.log_dir, "baseline_incumbent_validation.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
