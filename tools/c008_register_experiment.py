"""c008 AC-02: freeze the full RL experiment BEFORE training (§8). No result-dependent
threshold may change afterward. Emits EXPERIMENT_REGISTRATION.md + experiment_registration.json.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def build():
    dep = json.load(open(os.path.join(ART, "dependency_verification.json")))
    ppo_val = json.load(open(os.path.join(ART, "ppo_validation.json")))
    from cg import rl_policy as rlp
    pol = rlp.RLPolicy(seed=0)
    pcount = pol.trunk.param_count() + sum(v.data.size for v in pol.pv.values())
    reg = {
        "contract": "c008_fixed_deck_teacher_anchored_rl",
        "frozen_before_training": True,
        "dependencies": {
            "c005_final_head": dep["c005_final_head"], "c006_final_head": dep["c006_final_head"],
            "c007_final_head": dep["c007_final_head"], "c008_initial_head": dep["c008_initial_head"],
            "teacher_id": dep["teacher_id"], "deck_id": dep["frozen_deck_id"],
            "frozen_teacher_main_sha256": dep["frozen_teacher_main_sha256"],
            "v2a_checkpoint_sha256": dep["v2a_checkpoint_sha256"],
            "teacher_submission_ref": dep["teacher_submission_ref"],
        },
        "fixed_deck": "exact c005 Dragapult deck for every arm/checkpoint/eval/package (immutable)",
        "architecture": {"policy": "cg.rl_policy (c007 V2-A trunk + value head + STOP logit)",
                         "param_count": pcount, "torch_free_numpy": True,
                         "value_head_initialized_separately": True},
        "action_decoder_semantics": {
            "step": "one non-forced selection (§9.1); forced (n<=1 / maxCount==0 / min==max==n) bypass, no transition",
            "single_choice": "masked categorical (illegal prob exactly 0)",
            "fixed_multiselect": "sequential masked sampling without replacement (k=min=max picks)",
            "variable_multiselect": "sequential masked sampling + learned STOP logit; up to maxCount picks",
            "log_prob": "sum of sub-step masked log-probs (act()==evaluate() verified)",
            "ordered": "not observed in-deck; if ever observed -> BLOCK (§9.5), never routed silently to teacher",
            "reward_timing": "consecutive trainable steps treated as adjacent for gamma-discounting "
                             "(forced steps carry no decision value)",
            "eval_mode": "greedy (argmax) — matches deployed inference; rollouts sample stochastically",
        },
        "reward": {"win": 1, "draw": 0, "loss": -1, "intermediate": 0, "shaping": "none (§9.6)"},
        "ppo": {
            "gamma": 0.997, "gae_lambda": 0.95, "clip": 0.20, "value_coef": 0.50,
            "entropy_coef": {"start": 0.010, "end": 0.002, "schedule": "linear over budget"},
            "max_grad_norm": 0.50, "epochs_per_rollout": 4, "target_rollout_games": 128,
            "min_trainable_decisions_per_update": 8192,
            "rollout_rule": "collect until >=128 games AND >=8192 trainable decisions",
            "minibatch": 512, "optimizer": "AdamW", "weight_decay": 1e-5,
            "lr": {"R0": 3e-4, "R1": 1e-4, "R2": 1e-4},
            "advantage_normalization": "per update", "value_clipping": True,
            "mixed_precision": "disabled (numpy float64)",
        },
        "r2_anchors": {
            "teacher_replay": {"loss": "masked NLL of teacher action on c007 TRAIN split only "
                               "(never validation/test)", "minibatch": 256,
                               "coef_schedule": "0-20%:0.50; 20-50%:0.50->0.15; 50-80%:0.15->0.05; 80-100%:0.05"},
            "frozen_reference_kl": {"anchor": "frozen initial V2-A policy, first-step masked distribution",
                                    "coef_schedule": "0-20%:0.05; 20-60%:0.05->0.01; 60-100%:0.01"},
            "on_policy_teacher_action": "DISABLED — synchronized instrumented-teacher shadow after divergent "
                                        "RL actions is not proven; R2 uses offline replay + reference KL only (§10.3)",
        },
        "opponent_population": {
            "with_lagged": {"teacher_dragapult": 0.35, "mega_lucario": 0.20, "iono": 0.20,
                            "lagged_selfplay": 0.15, "control": 0.10},
            "before_lagged": "15% redistributed proportionally across teacher/lucario/iono "
                             "(-> 0.42/0.24/0.24, control 0.10)",
            "seat_balance": "50% seat0 / 50% seat1",
            "lagged_selfplay": "after 5,000 games freeze every 5,000; keep 3 most recent; sample uniformly; "
                               "never the current mutable params",
        },
        "held_out_opponent": "Mega Abomasnow — excluded from training, used only in final test eval "
                             "after checkpoint selection; never influences selection",
        "seeds": {"R0": [101, 202], "R1": [101, 202], "R2": [101, 202, 303]},
        "budgets": {"R0": 10000, "R1": 30000, "R2": 50000, "max_total": 230000,
                    "note": "maxima; early-stop gates bound actual compute; screening games are "
                            "EVALUATION and do NOT consume the training-game budget"},
        "screening": {"cadence_games": "1000, 2500, 5000, then every 5000",
                      "per_checkpoint": "20 games/seat/strategic-opponent (teacher,lucario,iono) "
                                        "+ 10 games/seat vs control = 140 games",
                      "evaluate_frozen_checkpoints": True},
        "checkpoint_selection": {
            "validation_blend": "0.40*teacher + 0.25*lucario + 0.25*iono + 0.10*control",
            "seed_winner_tiebreak": ["highest blend", "lower worst-strategic", "lower fallback", "lower P99", "earlier ckpt"],
            "arm_statistic": "median across seeds; representative checkpoint by same rule; all seeds reported",
            "abomasnow_excluded_from_selection": True,
        },
        "early_stop": {
            "R0": ["control<0.60 at 2500", "teacher<0.15 AND lucario<0.25 AND iono<0.25 at 5000",
                   "no blend improvement >2pp over two consecutive evals"],
            "R1_R2": ["teacher<0.20 AND strategic<0.30 at 10000", "teacher<0.35 AND strategic<0.40 at 20000",
                      "after 20000: no blend improvement >1.5pp over three consecutive evals"],
            "catastrophic": ["invalid>0 after one reproducible defect", "attributable crash/timeout >0.1%",
                             "non-finite params/losses", "entropy collapse with no recovery", "checkpoint corruption"],
        },
        "final_evaluation": {
            "reliability": "40 games/seat vs >=3 strategic opponents; zero invalid/exception/timeout; latency P50/95/99/max",
            "teacher_head_to_head": "200/seat (400) extend by 100 to 800; win=1/draw=.5/loss=0; "
                                    "one-sided 95% LB >= 0.47 to pass",
            "strategic_field": "Lucario, Iono, held-out Abomasnow, Dragapult mirror; control separate; both seats",
            "major_regression": "candidate point <= teacher point - 0.07 AND bootstrap P(regression) >= 90% (blocks submission)",
            "reproducible_improvement": "global field > teacher with 90% interval > 0, OR one matchup >=+5pp @ >=90% "
                                        "with non-inferiority pass and no major regression",
        },
        "submission_gate": "SUBMISSION_D=SUBMIT iff BEST_RL_ARM!=NONE AND non-inferiority passes AND reproducible "
                           "improvement exists AND no major regression AND reliability passes AND package/size/runtime pass. "
                           "Never submit for rising training reward / beating another RL arm / offline agreement / a lucky seed.",
        "kaggle_protocol": {"description": "c008 Submission D: <BEST_RL_ARM> fixed deck <sha>",
                            "dup_guard": "unique description + archive sha256", "poll": "30s x 20; pending allowed",
                            "teacher_refresh_ref": "54948560"},
        "measured_timing": {
            "ppo_update_8192x4_omp8_s": 15.8,
            "toy_positive_control_learned": ppo_val["toy_positive_control"]["learned"],
            "smoke_rollout_s": ppo_val["smoke_training"]["rollout_s"],
            "note": "RL is inherently non-reproducible (engine random_device + sampling); multi-threaded BLAS "
                    "used for updates. Honest-negative early-stop path estimated ~4-6h across all arms/seeds.",
        },
        "restart_policy": "one complete restart only for a documented implementation defect affecting all comparable runs",
    }
    return reg


def to_md(r):
    b = r["budgets"]; pp = r["ppo"]
    return "\n".join([
        "# c008 Experiment Registration (frozen before training)", "",
        f"Teacher `{r['dependencies']['teacher_id']}` | deck `{r['dependencies']['deck_id']}` | "
        f"ref {r['dependencies']['teacher_submission_ref']}",
        f"chain c005 {r['dependencies']['c005_final_head'][:12]} -> c006 {r['dependencies']['c006_final_head'][:12]} "
        f"-> c007 {r['dependencies']['c007_final_head'][:12]} -> c008 init {r['dependencies']['c008_initial_head'][:12]}", "",
        f"## Policy\n- {r['architecture']['policy']}: {r['architecture']['param_count']:,} params (pure numpy)", "",
        "## Arms & budgets (maxima; early-stops bound compute; screening != training budget)",
        f"- R0 random init, seeds {r['seeds']['R0']}, <= {b['R0']:,} games, lr {pp['lr']['R0']}",
        f"- R1 V2-A init, seeds {r['seeds']['R1']}, <= {b['R1']:,} games, lr {pp['lr']['R1']}",
        f"- R2 V2-A init + decaying teacher replay + reference KL, seeds {r['seeds']['R2']}, <= {b['R2']:,} games, "
        f"lr {pp['lr']['R2']} (primary hypothesis)",
        f"- total max {b['max_total']:,} games", "",
        f"## PPO\n- gamma {pp['gamma']} lambda {pp['gae_lambda']} clip {pp['clip']} vf {pp['value_coef']} "
        f"ent {pp['entropy_coef']['start']}->{pp['entropy_coef']['end']} epochs {pp['epochs_per_rollout']} "
        f"rollout {pp['rollout_rule']} minibatch {pp['minibatch']} AdamW wd {pp['weight_decay']}",
        f"- reward {r['reward']}; {r['action_decoder_semantics']['reward_timing']}", "",
        "## R2 anchors",
        f"- teacher replay: {r['r2_anchors']['teacher_replay']['coef_schedule']} (train split only)",
        f"- reference KL: {r['r2_anchors']['frozen_reference_kl']['coef_schedule']}",
        f"- on-policy teacher action: {r['r2_anchors']['on_policy_teacher_action']}", "",
        f"## Opponent population\n- {r['opponent_population']['with_lagged']} (before lagged: "
        f"{r['opponent_population']['before_lagged']}); seats {r['opponent_population']['seat_balance']}",
        f"- held-out: {r['held_out_opponent']}", "",
        f"## Screening\n- {r['screening']['cadence_games']}; {r['screening']['per_checkpoint']}",
        f"- checkpoint selection: {r['checkpoint_selection']['validation_blend']}", "",
        "## Early-stop", "- R0: " + "; ".join(r["early_stop"]["R0"]),
        "- R1/R2: " + "; ".join(r["early_stop"]["R1_R2"]), "",
        "## Final gates",
        f"- non-inferiority: teacher one-sided 95% LB >= 0.47",
        f"- major regression: {r['final_evaluation']['major_regression']}",
        f"- reproducible improvement: {r['final_evaluation']['reproducible_improvement']}",
        f"- submission: {r['submission_gate']}", "",
        f"_{r['restart_policy']}_",
    ]) + "\n"


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    reg = build()
    json.dump(reg, open(os.path.join(ART, "experiment_registration.json"), "w"), indent=2)
    open(os.path.join(ART, "EXPERIMENT_REGISTRATION.md"), "w").write(to_md(reg))
    print("registered. policy params", reg["architecture"]["param_count"],
          "| toy PPO learned", reg["measured_timing"]["toy_positive_control_learned"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
