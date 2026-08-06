# c010 — Fixed-Deck RL Training Loop v2

## 1. Objective

Build and test a dependable agent-improvement loop on the exact frozen c005 Dragapult deck before any deck optimization.

c009 established:

```text
untouched c007 V2-A vs frozen teacher: 16.0%
best c008 R1 checkpoint vs teacher:    22.0%

untouched V2-A strategic field:         15.25%
best c008 R1 strategic field:           25.50%
```

c010 must determine whether that gain is:

1. **Reproducible** — the exact c008 R1 recipe improves V2-A across independent seeds.
2. **Extendable** — continuing from the protected 22% incumbent produces a stronger confirmed incumbent.
3. **Stabilizable** — minimal variance-reduction changes extend the incumbent when the exact loop does not.
4. **Operationally reliable** — promotions, regressions, and decisions are reconstructed from identity-safe raw evidence.

Required decisions:

```text
EXACT_REPRODUCIBILITY = PROVEN | INCONCLUSIVE | FAILED
EXACT_CONTINUATION = EXTENDED | NOT_EXTENDED | INCONCLUSIVE
STABILIZED_CONTINUATION = EXTENDED | NOT_EXTENDED | INCONCLUSIVE
BEST_AGENT = V2A_BASELINE | R1_INCUMBENT | A_<seed>_<checkpoint> | B_<seed>_<checkpoint> | C_<seed>_<checkpoint> | NONE
TRAINING_LOOP_STATUS = VALIDATED | PROMISING | REJECTED
SUBMISSION_E = SUBMIT | DO_NOT_SUBMIT
PROMOTION_DECISION = PROMOTE_NEW_AGENT | KEEP_R1_INCUMBENT | KEEP_TEACHER | WAIT_FOR_MORE_GAMES | NO_RL_SUBMISSION
NEXT_STEP = SCALE_FIXED_DECK_RL | REDESIGN_FIXED_DECK_AGENT | BEGIN_DECK_PIPELINE
```

A negative competitive result may still produce contract `PASS` if all registered work and evidence checks complete honestly.

---

## 2. Strategic sequencing

The project sequence remains:

```text
frozen Dragapult deck
→ reliable agent-training loop
→ validated stronger agent
→ external calibration
→ deck work
```

Do not perform deck search, mutation, tuning, or optimization in c010.

`BEGIN_DECK_PIPELINE` is allowed only when `TRAINING_LOOP_STATUS=VALIDATED` and the final report explicitly concludes that policy variance is low enough for deck comparisons to be meaningful. Otherwise remain in fixed-deck agent work.

---

## 3. Dependencies and immutable inputs

Required:

```text
c005 frozen Dragapult teacher and exact deck
c007 untouched selected V2-A checkpoint
c008 PPO implementation and saved checkpoints
c009 corrected checkpoint registry and identity-safe evaluation evidence
c009 incumbent: c008 R1 seed 101 validation-selected checkpoint near 10,040 games
```

Before work:

- record branch and HEAD;
- record final commits for c005–c009;
- verify dependency hashes;
- verify frozen deck fingerprint;
- verify V2-A and incumbent checkpoint SHA-256;
- verify c009 raw games reproduce the recorded B0 and incumbent scores;
- preserve unrelated user changes.

Do not modify any file under:

```text
contracts/c005_teacher_import_submission_and_dataset/
contracts/c006_distilled_policy_baseline/
contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/
contracts/c008_fixed_deck_teacher_anchored_rl/
contracts/c009_amendment_c008/
```

Do not modify the frozen teacher, deck, V2-A, incumbent, or any prior checkpoint.

---

## 4. Non-goals

Do not:

- change the deck or card counts;
- introduce a new architecture family;
- use random-initialized RL;
- use MCTS or selective search;
- perform broad hyperparameter sweeps;
- use teacher behavioral-cloning replay;
- use KL optimization to V2-A or the rule teacher;
- add reward shaping;
- train on Mega Abomasnow;
- lower gates after results;
- promote the newest checkpoint merely because it is newer.

---

## 5. Branch and new source

Branch:

```text
contract/c010_fixed_deck_rl_loop_v2
```

Suggested source:

```text
tools/c010_train_loop.py
tools/c010_eval.py
tools/c010_aggregate.py
tools/c010_validate_evidence.py
tests/test_c010_arm_registration.py
tests/test_c010_incumbent_protection.py
tests/test_c010_identity_safe_eval.py
tests/test_c010_promotion_rules.py
tests/test_c010_content_validation.py
```

Do not overwrite c008/c009 tools.

---

## 6. Frozen baselines

Register and hash:

```text
B0 = exact c007 selected V2-A checkpoint
I0 = exact c009 best saved checkpoint, c008 R1 seed 101 near 10,040 games
T  = exact c005 frozen Dragapult teacher
```

B0 and I0 are protected and may never be overwritten.

The exact c005 Dragapult deck must be identical for B0, I0, all arms, all evaluations, and any package.

---

## 7. Common environment and reward

Reuse the validated c008/c009 environment and action decoder:

- one trainable step per non-forced selection;
- forced decisions bypass policy loss;
- legal-action masking;
- masked categorical log-probabilities;
- sequential masked-without-replacement sums for fixed-cardinality multi-select;
- registered variable-cardinality and ordered decoder semantics;
- unsupported forms become explicit defects, never silent teacher fallback.

Reward:

```text
win  = +1
draw =  0
loss = -1
```

All intermediate rewards remain zero.

---

## 8. Common training population

Use the exact c008 R1 population for every arm:

```text
35% frozen teacher
20% official Mega Lucario
20% official Iono
15% lagged branch-specific snapshots after 5,000 training games
10% deterministic engineering control
```

Before lagged self-play, redistribute the 15% proportionally among teacher, Lucario, and Iono.

Requirements:

- approximately 50/50 seats;
- exact opponent and seat counts recorded per rollout and cumulatively;
- lagged snapshot IDs and hashes recorded;
- Mega Abomasnow remains evaluation-only;
- no arm-specific population tuning.

---

## 9. Exact c008 R1 PPO recipe

Resolve and freeze the exact successful c008 R1 configuration before training.

Expected values:

```text
gamma                         0.997
GAE lambda                    0.95
PPO clip                      0.20
value coefficient             0.50
entropy coefficient           0.010 → 0.002
gradient norm                 0.50
PPO epochs                    4
optimizer                     AdamW
learning rate                 1e-4
weight decay                  1e-5
advantage normalization       per update
value clipping                enabled
rollout target                128 completed games
minimum trainable decisions   8,192
```

Correct batching rule:

> Continue collecting until **both** 128 completed games and 8,192 trainable decisions are reached.

If c008 source differs, Arms A and B must use the exact resolved c008 R1 implementation. Document every resolved value and hash.

---

## 10. Arm A — exact reproducibility

Purpose: determine whether the exact c008 R1 recipe reproducibly improves B0.

```text
initialization: B0
recipe: exact c008 R1
seeds: 311, 322, 333
maximum: 12,000 completed games per seed
planned minimum: 10,000 games per seed unless a safety stop triggers
```

Evaluate at:

```text
0, 2,500, 5,000, 7,500, 10,000, 12,000 games
```

Before 10,000 games, stop only for:

- reliability failure;
- checkpoint corruption;
- two confirmed catastrophic regressions;
- global compute safety limit.

A weak small screen alone is not sufficient to terminate a reproducibility seed early.

---

## 11. Arm B — exact continuation control

Purpose: test the literal extendability of the unchanged c008 R1 loop beyond I0.

```text
initialization: I0
recipe: exact c008 R1
seeds: 411, 422, 433
maximum: 7,500 additional games per seed
```

Evaluate at:

```text
0, 2,500, 5,000, 7,500 games
```

I0 remains permanently protected.

Early stop after two consecutive confirmation evaluations when both teacher score and strategic-field score are at least 5 percentage points below I0 with at least 90% probability of genuine regression.

---

## 12. Arm C — minimally stabilized continuation

Purpose: test whether the 22% ceiling was caused by unstable continuation rather than exhausted learning signal.

```text
initialization: I0
seeds: 511, 522, 533
maximum: 20,000 additional games per seed
```

Evaluate at:

```text
0, 2,500, 5,000, 7,500, 10,000, 15,000, 20,000 games
```

Change only these parameters relative to exact R1:

```text
learning rate                 3e-5
rollout target                256 completed games
minimum trainable decisions   32,768
```

Continue collecting until both rollout thresholds are met.

Everything else remains identical to exact R1.

No teacher replay. No optimized KL loss. Log diagnostic KL to I0 and the previous promoted checkpoint only.

Maintain:

```text
branch best screened checkpoint
branch best confirmed checkpoint
global protected incumbent
```

Early stop after:

- two confirmed severe regressions; or
- three consecutive registered evaluations after game 7,500 with no point-estimate gain above 1.5 percentage points on either teacher score or strategic-field score.

---

## 13. Compute registration

Before full execution, measure:

- games/hour;
- decisions/game;
- update duration;
- memory;
- disk growth;
- projected full runtime.

Maximum training games:

```text
Arm A  36,000
Arm B  22,500
Arm C  60,000
Total 118,500
Hard maximum including calibration spillover: 120,000
```

Do not exceed the hard maximum.

Evaluation games are separate and must be recorded.

If the minimum registered experiment is infeasible, set `PARTIAL` or `BLOCKED`; do not silently alter budgets.

---

## 14. Training evidence

Preserve one compact record per training game, including:

```text
arm, seed, checkpoint-before-game, opponent, opponent checkpoint hash,
seat, outcome, score, decisions, forced decisions, episode length,
mean entropy, start/end value prediction, fallbacks, invalid actions,
exceptions, timeouts
```

Per update preserve:

```text
policy loss, value loss, entropy, approximate KL, clip fraction,
explained variance, gradient norm, learning rate, games, decisions,
opponent distribution, seat distribution, elapsed time
```

Value diagnostics must include held-out calibration and explained variance by game phase:

```text
0–20%, 20–40%, 40–60%, 60–80%, 80–100%
```

Do not treat aggregate in-rollout explained variance as proof of useful early-game credit assignment.

---

## 15. Identity-safe evaluation

Reuse c009’s job protocol.

Every job/result preserves:

```text
job_id, candidate_id, checkpoint SHA-256, opponent, seat,
replicate, requested seed, phase, deck fingerprint
```

Assertions:

- submitted and returned job-ID sets match;
- no duplicates;
- candidate and loaded checkpoint hashes match the registry;
- deck fingerprint matches the frozen deck;
- opponent/seat match the submitted job;
- expected counts are exact;
- defects are explicit;
- raw games reproduce aggregates.

No positional reattachment after unordered multiprocessing.

---

## 16. Frozen evaluation panels

Generate evaluation job registries before seeing training results.

### Screen panel

```text
teacher        20 games per seat
Mega Lucario   10 games per seat
Iono           10 games per seat
Mega Abomasnow 10 games per seat
Total          100 games per checkpoint
```

### Confirmation panel

```text
teacher        100 games per seat
Mega Lucario    50 games per seat
Iono             50 games per seat
Mega Abomasnow   50 games per seat
Total           500 games per checkpoint
```

### Final panel

Evaluate B0, I0, best A, best B, and best C:

```text
teacher        200 games per seat
Mega Lucario   100 games per seat
Iono           100 games per seat
Mega Abomasnow 100 games per seat
Total        1,000 games per finalist
```

If a finalist remains plausibly teacher-non-inferior, extend teacher head-to-head to 800 total games.

The engineering control is diagnostic-only and excluded from promotion metrics.

---

## 17. Screening, confirmation, and metrics

Nominate a checkpoint for confirmation when any holds:

- promotion composite exceeds branch best;
- teacher score improves by at least 3 percentage points;
- strategic-field score improves by at least 4 percentage points;
- it is the branch’s final registered checkpoint.

Nomination is not promotion.

Metrics:

```text
teacher score = balanced match-point rate against T
strategic-field score = average balanced score against Lucario, Iono, Abomasnow
promotion composite = 0.55 teacher + 0.15 Lucario + 0.15 Iono + 0.15 Abomasnow
```

Major regression relative to the comparison baseline:

```text
candidate <= baseline - 0.07
and bootstrap probability of regression >= 90%
```

Report every matchup and seat separately.

---

## 18. Exact reproducibility rule

Set `EXACT_REPRODUCIBILITY=PROVEN` when all hold:

1. At least two of three Arm A seeds produce confirmed checkpoints above B0 on teacher score.
2. At least two of three are above B0 on strategic-field score.
3. The median best-per-seed Arm A result exceeds B0 by at least 3 percentage points on teacher score and 5 percentage points on field score.
4. At least one median difference has at least 90% bootstrap probability above zero.
5. A majority of seeds does not suffer a major Abomasnow regression.
6. Reliability passes.

Set `FAILED` when fewer than two seeds improve on both primary dimensions and uncertainty is not the reason. Otherwise `INCONCLUSIVE`.

---

## 19. Exact continuation rule

Set `EXACT_CONTINUATION=EXTENDED` when at least two Arm B seeds produce confirmed checkpoints above I0 and the median best-per-seed Arm B result has:

```text
teacher gain >= 3 percentage points
strategic-field gain >= 3 percentage points
at least one gain with >= 90% bootstrap probability above zero
no major regression
reliability pass
```

Set `NOT_EXTENDED` when no seed produces a confirmed improvement and uncertainty is not the reason. Otherwise `INCONCLUSIVE`.

---

## 20. Stabilized continuation rule

Set `STABILIZED_CONTINUATION=EXTENDED` under the same rule as Arm B, using Arm C seeds.

Flag a strong continuation result when:

```text
teacher score >= 30%
strategic-field score >= 30%
and at least two seeds satisfy both or the confirmed aggregate satisfies both
```

Set `NOT_EXTENDED` when no seed produces a confirmed improvement and uncertainty is not the reason. Otherwise `INCONCLUSIVE`.

---

## 21. Best-agent promotion

A new candidate may replace I0 only when:

- reliability passes;
- promotion composite is higher;
- teacher score is not lower;
- strategic-field score is not lower;
- at least one primary improvement has at least 90% bootstrap probability above zero;
- no major regression exists;
- checkpoint and deck hashes validate.

Tie-breakers:

1. teacher score;
2. strategic-field score;
3. Abomasnow score;
4. worst-matchup risk;
5. P99 latency;
6. earlier training game count.

If none qualify:

```text
BEST_AGENT=R1_INCUMBENT
PROMOTION_DECISION=KEEP_R1_INCUMBENT
```

---

## 22. Training-loop status

Set `VALIDATED` when:

- exact reproducibility is proven;
- exact or stabilized continuation is extended;
- a new agent is promoted;
- improvement survives the final panel;
- no major regression exists.

Set `PROMISING` when a real replicated or extended gain exists but not all validation conditions pass.

Set `REJECTED` when exact reproducibility fails and neither continuation arm extends I0, or reliability/optimization defects prevent a credible loop.

`REJECTED` applies to this PPO-loop family, not all fixed-deck agent learning.

---

## 23. Submission gate

Set `SUBMISSION_E=SUBMIT` only when the new best agent:

- is not B0 or I0;
- passes reliability;
- passes c008 teacher non-inferiority:

```text
one-sided 95% lower bound >= 0.47
```

- shows reproducible strategic improvement over the frozen teacher;
- has no major regression;
- uses the exact frozen deck;
- passes package validation.

Otherwise `DO_NOT_SUBMIT`.

Training-loop validation alone is not sufficient for submission.

---

## 24. Conditional Kaggle workflow

Only when `SUBMISSION_E=SUBMIT`, package:

```text
submission_E_fixed_deck_rl_v2.tar.gz
```

Description:

```text
c010 Submission E: <BEST_AGENT> fixed deck <final_commit_short_sha>
```

Validate deck/checkpoint/archive hashes, clean extraction, `cg/` structure, runtime reliability, latency, size, and absence of training-only artifacts.

Claude Code is then explicitly authorized and required to upload, retrieve the reference, poll every 30 seconds for at most 20 attempts, record status/public score, refresh teacher ref `54948560`, and preserve the comparison.

Do not expose credentials.

If the gate requires upload and it fails externally, set `PARTIAL`.

When gated off:

```text
KAGGLE_UPLOAD=SKIPPED_BY_GATE
```

---

## 25. Next-step rule

Set `SCALE_FIXED_DECK_RL` when the loop is validated, the best agent remains below teacher, and curves show credible headroom.

Set `REDESIGN_FIXED_DECK_AGENT` when the loop is rejected or PPO cannot reliably extend I0. A redesign may use a different fixed-deck agent algorithm, but not deck optimization.

Set `BEGIN_DECK_PIPELINE` only under Section 2’s gate.

State exactly one highest-leverage blocker.

---

## 26. Acceptance criteria

### AC-01 Dependency and immutability

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

### AC-02 Baseline/incumbent registry

```text
results/artifacts/baseline_incumbent_registry.json
results/test_logs/baseline_incumbent_validation.txt
```

### AC-03 Arm/config registration

```text
results/artifacts/experiment_registry.json
results/artifacts/arm_configuration_diff.json
results/test_logs/arm_registration_tests.txt
```

The diff must prove A/B equal exact R1 and C changes only the three registered values.

### AC-04 PPO/environment validation

```text
results/artifacts/ppo_validation.json
results/test_logs/ppo_validation.txt
```

### AC-05 Identity-safe evaluation

```text
results/artifacts/evaluation_identity_protocol.json
results/test_logs/evaluation_identity_tests.txt
```

### AC-06 Throughput/compute registration

```text
results/artifacts/throughput_calibration.json
results/artifacts/compute_budget.json
results/test_logs/throughput_calibration.txt
```

### AC-07 Arm A

```text
results/artifacts/arm_A_summary.json
results/artifacts/arm_A_training_games.jsonl.gz
results/artifacts/arm_A_updates.jsonl.gz
results/artifacts/arm_A_checkpoint_registry.json
results/test_logs/arm_A_training.txt
```

### AC-08 Arm B

```text
results/artifacts/arm_B_summary.json
results/artifacts/arm_B_training_games.jsonl.gz
results/artifacts/arm_B_updates.jsonl.gz
results/artifacts/arm_B_checkpoint_registry.json
results/test_logs/arm_B_training.txt
```

### AC-09 Arm C

```text
results/artifacts/arm_C_summary.json
results/artifacts/arm_C_training_games.jsonl.gz
results/artifacts/arm_C_updates.jsonl.gz
results/artifacts/arm_C_checkpoint_registry.json
results/test_logs/arm_C_training.txt
```

### AC-10 Screening/confirmation

```text
results/artifacts/checkpoint_screening.csv
results/artifacts/checkpoint_confirmation.json
results/artifacts/evaluation_games.jsonl.gz
results/artifacts/evaluation_game_manifest.json
results/test_logs/checkpoint_evaluation.txt
```

### AC-11 Value/optimization diagnostics

```text
results/artifacts/value_diagnostics_by_game_phase.json
results/artifacts/optimization_diagnostics.json
results/test_logs/value_diagnostics.txt
```

### AC-12 Reproducibility/extendability decisions

```text
results/artifacts/EXACT_REPRODUCIBILITY.md
results/artifacts/EXACT_CONTINUATION.md
results/artifacts/STABILIZED_CONTINUATION.md
results/artifacts/reproducibility_extendability.json
```

### AC-13 Final panel and best agent

```text
results/artifacts/final_matchup_matrix.csv
results/artifacts/final_pairwise_intervals.json
results/artifacts/final_ranking.json
results/artifacts/final_regression_report.json
results/artifacts/best_agent_selection.json
results/test_logs/final_evaluation.txt
```

### AC-14 Content-aware validation

```text
results/artifacts/evidence_validation.json
results/test_logs/evidence_validation.txt
```

Validate contents, hashes, game counts, aggregate reconstruction, arm configuration, budgets, and decisions. File existence alone is insufficient.

### AC-15 Submission and next step

```text
results/artifacts/SUBMISSION_E_DECISION.md
results/artifacts/submission_E_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
```

Conditional Kaggle/package evidence:

```text
results/artifacts/submission_E_fixed_deck_rl_v2.tar.gz
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_agent_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

### AC-16 Git/source integrity

```text
results/GIT_REPORT.md
results/artifacts/c010.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

A `PASS` requires all sixteen criteria and content-aware validation.

---

## 27. Required root results

```text
results/SUMMARY.md
results/STATUS.json
results/ACCEPTANCE_CHECKLIST.md
results/FILES_CHANGED.md
results/COMMANDS_RUN.md
results/GIT_REPORT.md
```

`SUMMARY.md` must report dependency hashes, deck fingerprint, B0/I0 identities, exact R1 recipe, every seed result, game totals, all three experimental decisions, value diagnostics, best agent, teacher/field/Abomasnow scores, regressions, loop status, submission, next step, blocker, and limitations.

`STATUS.json` must include all required decisions, heads/commits, training/evaluation totals, blocking issues, and limitations. Example values are not predetermined outcomes.

---

## 28. Git requirements

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin `c010:`.

Recommended commits:

```text
c010: register fixed-deck rl loop v2
c010: execute reproducibility and continuation arms
c010: validate final agent and decisions
```

Do not push, force-push, rebase shared history, amend user commits, modify c005–c009, commit credentials, or alter registered gates after results.

---

## 29. Stop/status rules

Set `BLOCKED` when B0/I0, teacher/deck, cabt runtime, or action semantics are unavailable/corrupt, or user changes cannot be preserved.

Set `PARTIAL` when a required seed is skipped outside registered rules, raw evidence is missing, identity-safe evaluation fails, aggregates do not reproduce raw games, arm configurations deviate, the hard maximum is exceeded, content validation fails, earlier contracts change, or required Kaggle upload fails externally.

Do not claim `PASS` because files exist.

---

## 30. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Frozen deck fingerprint:
V2-A checkpoint:
R1 incumbent checkpoint:
Arm A seeds and best results:
Arm B seeds and best results:
Arm C seeds and best results:
Exact reproducibility:
Exact continuation:
Stabilized continuation:
Best agent:
Teacher score:
Strategic-field score:
Held-out Abomasnow score:
Major regressions:
Training-loop status:
Training games:
Evaluation games:
Submission E:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Promotion decision:
Next step:
Highest-leverage blocker:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria execute and the content-aware validator passes.
