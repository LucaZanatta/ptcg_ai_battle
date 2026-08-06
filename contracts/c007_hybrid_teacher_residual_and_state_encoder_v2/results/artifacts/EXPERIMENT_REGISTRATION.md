# c007 Experiment Registration (frozen before dependent experiments)

Teacher `dragapult` | deck `sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab` | teacher ref 54948560
c005 4137d983c6a0 -> c006 08ebac883854 -> c007 init 08ebac883854

## Model
- ModelV2 (pure-numpy, cg.policy_model_v2): 538,770 params (band [500000, 2000000], hard max 3,000,000; in-band True)
- V2-A action-only; V2-B + privileged aux heads ['plan_main_target(softmax)', 'use_support(bce)', 'value/outcome(bce)'] (coef {'plan': 0.3, 'support': 0.3, 'value': 0.3})
- seeds [101, 202, 303]; Adam lr 0.0015 max_epochs 22 patience 5; select on validation iw-agreement only

## State encoder v2
- dims {'CARD_FEAT': 52, 'N_BOARD': 12, 'SLOT_DYN': 36, 'N_HAND': 12, 'HAND_DYN': 2, 'N_DISCARD': 16, 'OPT_DENSE': 51, 'OPT_ROWS': 2, 'GLOBAL': 211, 'N_CTX': 49, 'N_OPTTYPE': 17, 'N_AREA': 13, 'vocab_size': 1270}

## Dataset
- targets: >= 600 games / >= 50000 decisions
- opponents ['mega_lucario', 'mega_abomasnow', 'iono', 'dragapult (mirror)'] + control (__control__ (DetControl) — included in data-gen and gauntlet, REPORTED SEPARATELY)
- split {'scheme': 'whole-game 70/15/15', 'seed': 70157, 'stratify_by': ['opponent', 'teacher_seat'], 'test_frozen': True, 'no_leakage': True}

## Residual contexts
- candidate pool: ['search_card_target', 'dragapult_damage_counter', 'promotion_to_active', 'energy_attachment_target', 'retreat_switch', 'evolution_target']
- primary: dragapult_damage_counter; admit at most 3
- admission requires ALL: >=300 c007 examples; >=200 examples with two meaningful legal choices; decoder semantics fully supported; teacher/oracle state synchronization valid; counterfactual evaluation stable; H1 calibration acceptable (ECE <= 0.15 in-context); not primarily forced (forced fraction < 0.5); residual action does not corrupt future teacher state

## Counterfactual / improvement labels
- primary: controlled deterministic policy variants (§12 fallback): a variant alters ONE semantic rule in an admitted context; A/B vs teacher in balanced full games; the improvement claim is POLICY-LEVEL (global strength), never fabricated per-state labels.
- branch-and-rollout: time-boxed 30-min capability probe recorded under results/artifacts; used at most as a per-state stability check, not as the primary improvement evidence.
- positive-label gate: ['estimated advantage > registered minimum', 'one-sided 90% LCB > 0', 'instability acceptable', 'no reliability defect']
- damage-counter variants: ['V_plan_a: use plan_a.counter when plan_a.attack != 0 (main.py L278-284/L705 plan_a/plan_b mismatch)', 'V_reset: reset AttackPlan.counter on the early-return path (stale class-attr, L55/L215-216)', 'V_thresh: corrected HP-band threshold in DAMAGE_COUNTER_ANY (L709 reachability)', 'V_greedy: greedy knockout-maximizing spread allocation']

## Gates
- override: confidence >= 0.6, advantage LCB > 0.0, budget 5/game (3/context)
- OOD: per-context: global-feature vector within [1st,99th] percentile envelope of that context's training decisions AND legal-option count within training range; else abstain
- non-inferiority: one-sided 95% lower bound (5th pct seat-balanced bootstrap) >= 0.47 (400 orientation, extend to 800)
- reproducible improvement (any): ['one matchup >= +5pp with bootstrap P(improvement) >= 0.90', 'global strength improvement, 90% bootstrap interval above zero (PRIMARY target)', 'validated residual-context action-value improvement reproduced in a 2nd held-out batch, no full-game regression']
- major regression blocks: any matchup >= 7pp below teacher with >= 90% bootstrap probability

## Submission
- SUBMISSION_C=SUBMIT iff BEST_HYBRID=H2_RESIDUAL (instrumentation valid + encoder accepted + >=1 residual context admitted + perfect reliability + non-inferiority LB>=0.47 + >=1 reproducible improvement + no major regression + telemetry complete + package validation)

## Kaggle
- {'description': 'c007 Submission C: hybrid residual <final_commit_short_sha>', 'dup_guard': 'unique description + recorded archive sha256', 'poll': 'every 30s, max 20 attempts; pending-after-window allowed; retain ref + refresh cmd', 'teacher_refresh_ref': '54948560'}

_one documented code-defect correction may fairly restart affected runs; otherwise no changes after freeze_
