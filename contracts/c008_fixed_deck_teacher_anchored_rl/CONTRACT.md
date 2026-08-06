# c008 — Fixed-Deck Teacher-Anchored RL

## 1. Winning objective

Run the first controlled reinforcement-learning experiment that directly optimizes game outcomes while keeping the c005 Dragapult deck completely frozen.

Compare three registered arms:

```text
R0 — randomly initialized PPO control
R1 — c007 V2-A initialized PPO
R2 — c007 V2-A initialized PPO with decaying teacher anchors
```

The purpose is not to prove that RL works at any cost. It is to determine, under a bounded and reproducible simulator budget:

1. Whether plain RL produces a meaningful learning curve.
2. Whether supervised initialization materially accelerates RL.
3. Whether teacher anchoring improves stability and final strength.
4. Whether any RL policy is locally stronger than the frozen teacher.
5. Whether a qualifying RL policy should be submitted on the exact same deck.

Required final decisions:

```text
BEST_RL_ARM = R0 | R1 | R2 | NONE
RL_FEASIBILITY = PROVEN | INCONCLUSIVE | REJECTED
SUBMISSION_D = SUBMIT | DO_NOT_SUBMIT
PROMOTION_DECISION =
    PROMOTE_RL
  | KEEP_TEACHER
  | WAIT_FOR_MORE_GAMES
  | NO_RL_SUBMISSION
NEXT_STEP =
    CONSOLIDATE_RL
  | REVISE_RL
  | RETURN_TO_SEARCH
  | BEGIN_DECK_PIPELINE
```

A negative RL result may still produce contract `PASS` when every registered experiment and decision rule is completed honestly.

---

## 2. Fixed experimental variable

The exact c005 Dragapult deck is immutable.

For every arm, checkpoint, local evaluation, and Kaggle package:

```text
deck = exact frozen c005 Dragapult deck
```

The only trainable variable is the agent.

Do not:

- mutate card counts
- substitute another deck
- tune the deck for an RL arm
- alter the frozen teacher
- alter c005, c006, or c007 artifacts

This contract is designed to isolate policy improvement.

---

## 3. Strategic context

Accepted project evidence:

- c005 selected and submitted the frozen Dragapult teacher.
- Teacher Kaggle submission reference: `54948560`.
- c006 pure behavioral cloning reached useful offline agreement but collapsed in gameplay.
- c007 built a richer state encoder, teacher instrumentation, and a larger ordered dataset.
- c007 did not find a proven positive residual override.
- Ordinary teacher imitation is not enough.
- Plain RL is not assumed to win; it is included as a capped control.
- R2 is the primary competitive hypothesis.

The main hypothesis is:

```text
V2-A initialization
+ on-policy outcome optimization
+ decaying stability anchors
> frozen teacher
```

---

## 4. Dependencies and immutability

Required:

```text
c001–c007 implementation source
c005 frozen teacher and Dragapult deck
c005/c006/c007 gauntlet and packaging tools
c007 state encoder v2
c007 selected V2-A checkpoint
c007 ordered dataset and train/validation/test manifests
c007 instrumented teacher copy and parity evidence
```

Before implementation:

- Record current branch and HEAD.
- Record c005, c006, and c007 final commits.
- Verify frozen teacher, frozen deck, V2-A checkpoint, dataset, and schema hashes.
- Verify teacher submission reference `54948560`.
- Preserve pre-existing user changes.

Absolute immutability:

```text
contracts/c005_teacher_import_submission_and_dataset/
contracts/c006_distilled_policy_baseline/
contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/
```

No file under those directories may be changed.

If required assets or hashes are unavailable, set `BLOCKED`.

---

## 5. Scope

Expected implementation:

- RL environment adapter over cabt
- Legal-option masked policy
- Context-aware multi-select sampling and log probabilities
- Value head and generalized advantage estimation
- PPO implementation
- Offline teacher-replay anchor
- Optional synchronized on-policy teacher labels
- R0/R1/R2 training
- Fixed opponent population
- Capped budgets and early stopping
- Training-curve and checkpoint evidence
- Final local evaluation
- Submission packaging
- Mandatory Kaggle upload and retrieval when the submission gate passes
- Reproducibility and Git evidence

---

## 6. Non-goals

Do not implement:

- deck optimization
- unrestricted hyperparameter sweeps
- a new representation family
- full MCTS
- LLM-generated rewards or labels
- unregistered reward shaping
- more than one PPO configuration
- more than three RL arms
- repeated post-test retraining
- ordinary distillation after RL inside this contract
- broad opponent mining
- multi-contract infrastructure refactoring

---

## 7. Pre-registered policies

## T — Frozen teacher

Exact c005 teacher and deck.

## R0 — Plain RL control

```text
state encoder v2 architecture
random initialization
PPO objective
no behavioral-cloning anchor
no reference-policy KL anchor
```

R0 exists to test whether plain RL learns at all. It receives the smallest budget.

## R1 — Supervised initialization plus RL

```text
initialize policy encoder/action head from selected c007 V2-A checkpoint
initialize value head separately
PPO objective
no teacher anchor after initialization
```

## R2 — Teacher-anchored RL

```text
same initialization as R1
PPO objective
+ offline teacher-replay loss
+ decaying KL anchor to frozen initial V2-A policy
+ optional synchronized on-policy teacher-action loss
```

R2 is the primary candidate.

No other policy may become the winner.

---

## 8. Experiment registration

Before RL training, create:

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
```

Freeze:

- dependency hashes
- architecture hashes
- action decoder semantics
- reward
- PPO hyperparameters
- opponent sampling distribution
- seat distribution
- training seeds
- per-arm game budgets
- early-stop gates
- evaluation cadence
- checkpoint-selection metric
- validation and final test populations
- non-inferiority rule
- matchup-regression rule
- submission gate
- Kaggle protocol

No result-dependent threshold changes are allowed.

One complete restart is allowed only for a documented implementation defect affecting all comparable runs.

---

## 9. RL environment and action semantics

### 9.1 Decision steps

One RL step corresponds to one non-forced agent selection event.

Forced choices:

- bypass the network
- produce no policy loss
- remain in trajectory history
- may contribute to value-return timing only through the next trainable step

### 9.2 Single-choice decisions

Use a masked categorical distribution over the current legal options.

Illegal options must have exactly zero sampling probability.

### 9.3 Fixed-cardinality unordered selections

Use sequential masked sampling without replacement.

The action log probability is the sum of the registered sub-selection log probabilities.

### 9.4 Variable-cardinality selections

Use the c007 registered cardinality/stop decoder.

### 9.5 Ordered selections

Use the c007 registered autoregressive pointer decoder.

If any c007-observed action form is unsupported:

- stop training
- record `BLOCKED`
- do not silently route strategic decisions to the teacher

Deterministic safe fallback is allowed only for:

- model exceptions
- corrupt checkpoint tests
- previously registered technical failure cases

Fallback use during official RL evaluation counts as a policy defect and must be reported.

### 9.6 Episode return

Primary reward only:

```text
win  = +1
draw =  0
loss = -1
```

Intermediate reward:

```text
0
```

No prize, damage, knockout, board-value, or teacher-score shaping is permitted in c008.

This keeps the experiment focused on actual game outcomes.

---

## 10. PPO specification

Use one implementation for all arms.

Default registered configuration:

```text
discount gamma:                 0.997
GAE lambda:                     0.95
PPO clip range:                 0.20
value-loss coefficient:         0.50
entropy coefficient:            0.010, linearly decayed to 0.002
maximum gradient norm:          0.50
PPO epochs per rollout:         4
target rollout batch:           128 completed games
minimum trainable decisions:    8,192 per update
optimizer:                      AdamW
R0 learning rate:               3e-4
R1/R2 learning rate:            1e-4
weight decay:                   1e-5
advantage normalization:        per update
value clipping:                 enabled
mixed precision:                only if numerically validated
```

If 128 games do not reach 8,192 trainable decisions, continue collecting until one threshold is met.

Record effective batch sizes and update counts.

### 10.1 R2 offline teacher replay

Each R2 PPO update also samples whole-game or ordered subsequences from the c007 training split.

Teacher-replay loss:

```text
masked negative log probability of teacher action
```

Replay coefficient schedule by consumed R2 game budget:

```text
0–20%:      0.50
20–50%:     linearly 0.50 → 0.15
50–80%:     linearly 0.15 → 0.05
80–100%:    0.05
```

Teacher replay may not use the c007 validation or test splits.

### 10.2 R2 frozen-reference KL

Anchor to the frozen initial V2-A policy on R2 on-policy states.

Use masked legal-option distributions.

Coefficient schedule:

```text
0–20%:      0.05
20–60%:     linearly 0.05 → 0.01
60–100%:    0.01
```

For multi-select decoders, sum or average KL consistently across registered sub-decisions.

### 10.3 Optional on-policy teacher action

Use an on-policy teacher-action loss only when:

- the instrumented teacher shadow is synchronized with the actual history
- synchronization tests pass after divergent RL actions
- no stale private teacher plan is used incorrectly

If synchronization cannot be proven:

- disable this term
- continue R2 with offline replay and reference KL
- document the reason

Do not fake teacher labels on unsynchronized states.

---

## 11. Training opponent population

Every arm uses the same registered population probabilities and seat balance.

Initial population:

```text
35% frozen Dragapult teacher
20% official Mega Lucario
20% official Iono
15% lagged self-play snapshot
10% deterministic engineering control
```

Before an arm has a usable lagged snapshot, replace that 15% proportionally across teacher, Lucario, and Iono.

Seat assignment:

```text
50% seat 0
50% seat 1
```

### 11.1 Lagged self-play

After an arm has consumed at least 5,000 training games:

- freeze a lagged checkpoint every 5,000 games
- keep at most the three most recent lagged checkpoints
- sample uniformly among them
- never train against the current mutable parameters directly

### 11.2 Held-out generalization opponent

Official Mega Abomasnow is held out from RL training.

It may be used only in the final test evaluation after each arm’s checkpoint is selected.

Do not alter this holdout after training begins.

---

## 12. Seeds and budgets

Training seeds:

```text
R0: 101, 202
R1: 101, 202
R2: 101, 202, 303
```

R0 is a control and receives two seeds. R2 receives the largest evidence budget.

Maximum training games per seed:

```text
R0:  10,000
R1:  30,000
R2:  50,000
```

Maximum total:

```text
230,000 training games
```

The contract should stop earlier when registered gates reject an arm.

Do not exceed these budgets.

---

## 13. Evaluation cadence and early stopping

Evaluate frozen checkpoints, not mutable live parameters.

### 13.1 Screening evaluation

At:

```text
1,000
2,500
5,000
then every 5,000 training games
```

Run a balanced screening set against:

- frozen teacher
- Mega Lucario
- Iono
- engineering control

Minimum per checkpoint:

```text
20 games per seat per strategic opponent
10 games per seat against engineering control
```

Use a fixed screening schedule shared across comparable seeds.

### 13.2 R0 stopping rules

Stop an R0 seed when either:

At 2,500 games:

```text
score against engineering control < 0.60
```

or at 5,000 games:

```text
score against teacher < 0.15
and
score against both Lucario and Iono < 0.25
```

or after two consecutive evaluations:

```text
no improvement greater than 2 percentage points
in the registered validation score
```

R0 may continue only while it demonstrates a meaningful learning curve.

### 13.3 R1/R2 stopping rules

At 10,000 games, reject a seed when:

```text
teacher score < 0.20
and strategic validation score < 0.30
```

At 20,000 games, reject a seed when:

```text
teacher score < 0.35
and strategic validation score < 0.40
```

After 20,000 games, stop when three consecutive evaluations show:

```text
no validation-score improvement greater than 1.5 percentage points
```

Do not early-stop solely because training reward is noisy.

### 13.4 Catastrophic stop

Stop an arm immediately for:

- invalid action rate above zero after one reproducible defect
- attributable crash/timeout rate above 0.1%
- non-finite parameters or losses
- policy entropy collapse with no recovery under the registered schedule
- repeated checkpoint corruption

A single implementation bug may be corrected only under the experiment-registration restart rule.

---

## 14. Checkpoint selection

Select one checkpoint per completed seed using validation evidence only.

Validation score:

```text
0.40 * score_vs_teacher
+ 0.25 * score_vs_lucario
+ 0.25 * score_vs_iono
+ 0.10 * score_vs_engineering_control
```

Seed winner:

1. Highest validation score.
2. Lower worst-strategic-opponent score if tied.
3. Lower fallback rate.
4. Lower P99 latency.
5. Earlier training checkpoint when otherwise tied.

Arm winner:

- median performance across seeds is the primary arm statistic
- select one representative checkpoint using the same validation rule
- do not choose only the luckiest seed without reporting all seeds

The held-out Abomasnow opponent must not influence checkpoint selection.

---

## 15. Required training evidence

For every arm and seed, preserve:

- game count
- decision count
- PPO updates
- opponent and seat distribution
- return mean and distribution
- policy loss
- value loss
- entropy
- approximate KL
- clip fraction
- gradient norm
- explained variance
- teacher-replay loss when applicable
- reference KL when applicable
- screening results
- early-stop reason
- checkpoint hashes
- wall-clock and simulator throughput
- invalid/error/timeout/fallback counts

Produce plots and machine-readable CSV/JSON.

Training reward alone is never sufficient evidence of improvement.

---

## 16. Final local evaluation

Evaluate:

```text
T
best R0 checkpoint, if any
best R1 checkpoint, if any
best R2 checkpoint, if any
```

All use the exact frozen Dragapult deck.

### 16.1 Reliability

For each surviving RL candidate:

```text
40 games per seat
against at least three strategic opponents
```

Require:

- zero invalid actions
- zero attributable exceptions
- zero attributable timeouts
- fallback rate recorded
- P50/P95/P99/max latency

### 16.2 Teacher head-to-head

For each surviving candidate:

Initial:

```text
200 games per seat orientation
400 total
```

Extend in balanced increments of 100 games to:

```text
800 total maximum
```

Use:

```text
win = 1
draw = 0.5
loss = 0
```

Pass local teacher non-inferiority when the one-sided 95% lower bound is:

```text
>= 0.47
```

### 16.3 Strategic field

Compare T and every surviving candidate against:

- Mega Lucario
- Iono
- held-out Mega Abomasnow
- Dragapult teacher mirror
- engineering control separately

Use both seats and the existing sequential evaluation protocol.

Report:

- pairwise intervals
- global ranking
- conservative lower bounds
- worst matchup
- seat effects
- reliability
- latency

### 16.4 Major regression

A major regression exists when, against any strategic opponent:

```text
candidate point estimate <= teacher point estimate - 0.07
```

and bootstrap probability of regression is at least 90%.

Any major regression blocks submission.

### 16.5 Reproducible improvement

A candidate has a reproducible improvement when either:

1. Global strategic-field score exceeds teacher and the 90% bootstrap interval for the difference is above zero; or
2. At least one strategic matchup improves by at least 5 percentage points with at least 90% bootstrap probability, teacher non-inferiority passes, and no major regression exists.

---

## 17. Best-arm and RL-feasibility decisions

Eligible candidate requirements:

- reliability passes
- teacher non-inferiority passes
- no major regression
- checkpoint and lineage reproducible

Select `BEST_RL_ARM` by:

1. Highest global strategic-field score.
2. Higher teacher head-to-head lower bound.
3. Better held-out Abomasnow result.
4. Lower worst-matchup risk.
5. Lower P99 latency.

If no candidate is eligible:

```text
BEST_RL_ARM = NONE
```

Set:

```text
RL_FEASIBILITY = PROVEN
```

when at least one arm:

- is teacher-non-inferior
- is reproducibly stronger in the strategic field or one matchup
- shows a stable positive learning curve across at least two seeds

Set:

```text
RL_FEASIBILITY = INCONCLUSIVE
```

when learning occurs but no candidate reaches teacher non-inferiority.

Set:

```text
RL_FEASIBILITY = REJECTED
```

when all arms fail to produce a meaningful learning curve under their budgets.

---

## 18. Submission gate

Set:

```text
SUBMISSION_D = SUBMIT
```

only when:

- `BEST_RL_ARM != NONE`
- teacher non-inferiority passes
- reproducible improvement exists
- no major regression exists
- reliability passes
- package size and runtime pass

Otherwise:

```text
SUBMISSION_D = DO_NOT_SUBMIT
```

Do not submit merely because:

- training reward increased
- the best RL arm beat another RL arm
- offline action agreement increased
- one seed was lucky
- the candidate is close to teacher without an improvement signal

---

## 19. Submission D package

When the gate passes, build:

```text
submission_D_rl.tar.gz
```

Include:

- exact frozen c005 Dragapult deck
- selected RL policy and value-free inference path
- state encoder v2
- legal-option decoders
- safe technical fallback
- required `cg/` files

Exclude:

- optimizer state
- training data
- opponent agents
- teacher replay dataset
- unused checkpoints
- secrets

Validate:

- exact archive structure
- SHA-256
- size
- clean extraction
- 80 extracted-package games
- both seats
- at least three strategic opponents
- zero invalid actions/errors/timeouts
- P99 latency inside competition limits
- corrupt/missing-model fallback test

---

## 20. Mandatory Kaggle submission and retrieval

When:

```text
SUBMISSION_D = SUBMIT
```

Claude Code is explicitly authorized and required to upload the validated archive.

No additional environment-variable authorization is required.

### 20.1 Description

Use:

```text
c008 Submission D: <BEST_RL_ARM> fixed deck <final_commit_short_sha>
```

### 20.2 Duplicate guard

Retrieve existing submissions first.

Do not duplicate an existing project submission with the same:

- description
- archive SHA-256

### 20.3 Upload and retrieval

Use the official Kaggle CLI equivalent of:

```bash
kaggle competitions submit pokemon-tcg-ai-battle \
  -f contracts/c008_fixed_deck_teacher_anchored_rl/results/artifacts/submission_D_rl.tar.gz \
  -m "<description>"
```

Preserve:

```text
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
```

Poll:

```text
every 30 seconds
maximum 20 attempts
```

Stop on terminal status.

If still pending:

- retain submission reference
- preserve latest status
- provide exact refresh command
- do not mark `PARTIAL` solely for pending processing

If credentials, network, daily limits, or competition rejection block an authorized upload:

- record exact stderr
- set `KAGGLE_UPLOAD = BLOCKED`
- set contract `PARTIAL`

### 20.4 Teacher comparison

Refresh teacher submission:

```text
54948560
```

Create:

```text
results/artifacts/kaggle_teacher_rl_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
```

Set:

```text
PROMOTION_DECISION = PROMOTE_RL
```

only when completed external evidence plus local evidence support promotion.

Use:

```text
WAIT_FOR_MORE_GAMES
```

when the score is immature or too close.

Do not overwrite historical teacher score snapshots.

---

## 21. Next-step decision

Set:

```text
NEXT_STEP = CONSOLIDATE_RL
```

when RL feasibility is proven and a qualifying policy exists.

Set:

```text
NEXT_STEP = REVISE_RL
```

when RL learns materially but remains below teacher and one clear technical blocker is identified.

Set:

```text
NEXT_STEP = RETURN_TO_SEARCH
```

when RL is rejected but selective search/value modeling remains promising.

Set:

```text
NEXT_STEP = BEGIN_DECK_PIPELINE
```

when agent-only approaches have reached diminishing returns and no bounded RL arm is competitive.

State exactly one highest-leverage blocker when RL is not proven.

---

## 22. Mandatory acceptance criteria

### AC-01 — Dependency and immutability verification

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

Pass when required hashes match and c005–c007 remain unchanged.

### AC-02 — Registered RL experiment

Evidence:

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
```

Pass when all arms, budgets, thresholds, populations, seeds, and gates are frozen before training.

### AC-03 — RL environment and action-decoder validation

Evidence:

```text
results/artifacts/rl_environment_schema.json
results/artifacts/action_decoder_coverage.json
results/test_logs/rl_environment_tests.txt
results/test_logs/action_decoder_tests.txt
```

Pass when every observed action form is supported, legal masking is exact, and log probabilities are reproducible.

### AC-04 — PPO implementation validation

Evidence:

```text
results/artifacts/ppo_validation.json
results/test_logs/ppo_unit_tests.txt
results/test_logs/ppo_smoke_training.txt
```

Pass when advantage, clipping, value loss, entropy, masking, checkpoint restore, and deterministic toy tests succeed.

### AC-05 — R0 plain-RL control

Evidence:

```text
results/artifacts/training/R0/
results/artifacts/r0_training_summary.json
results/test_logs/training_R0.txt
```

Pass when both registered seeds execute until budget or registered early stop and all evidence is preserved. R0 need not succeed competitively.

### AC-06 — R1 initialized RL

Evidence:

```text
results/artifacts/training/R1/
results/artifacts/r1_training_summary.json
results/test_logs/training_R1.txt
```

Pass when both registered seeds execute until budget or registered early stop.

### AC-07 — R2 teacher-anchored RL

Evidence:

```text
results/artifacts/training/R2/
results/artifacts/r2_training_summary.json
results/artifacts/teacher_anchor_report.json
results/test_logs/training_R2.txt
```

Pass when all three seeds execute until budget or registered early stop and anchor schedules are verified.

### AC-08 — Training curves and checkpoint selection

Evidence:

```text
results/artifacts/training_curves.csv
results/artifacts/training_curves.json
results/artifacts/checkpoint_registry.json
results/artifacts/checkpoint_selection.json
results/artifacts/plots/
results/test_logs/checkpoint_selection.txt
```

Pass when every checkpoint is traceable and selection uses validation only.

### AC-09 — Final reliability and latency

Evidence:

```text
results/artifacts/final_reliability.json
results/artifacts/final_latency.json
results/test_logs/final_smoke_games.txt
```

Pass when every surviving candidate completes the registered reliability evaluation.

### AC-10 — Teacher non-inferiority

Evidence:

```text
results/artifacts/rl_teacher_games.jsonl.gz
results/artifacts/rl_teacher_noninferiority.json
results/test_logs/rl_teacher_execution.txt
```

Pass when every surviving candidate receives the registered teacher comparison. The AC may pass even when no candidate is non-inferior.

### AC-11 — Strategic and held-out evaluation

Evidence:

```text
results/artifacts/rl_strategic_games.jsonl.gz
results/artifacts/rl_matchup_matrix.csv
results/artifacts/rl_global_ranking.json
results/artifacts/rl_holdout_report.json
results/artifacts/rl_improvement_report.json
results/artifacts/rl_regression_report.json
results/test_logs/rl_strategic_execution.txt
```

Pass when the fixed field and held-out Abomasnow evaluation are complete.

### AC-12 — Best-arm and feasibility decisions

Evidence:

```text
results/artifacts/rl_arm_selection.json
results/artifacts/RL_FEASIBILITY.md
```

Pass when `BEST_RL_ARM` and `RL_FEASIBILITY` follow the registered rules.

### AC-13 — Submission decision and package

Evidence:

```text
results/artifacts/SUBMISSION_D_DECISION.md
results/artifacts/submission_D_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/test_logs/submission_D_smoke.txt
```

When the gate passes, also:

```text
results/artifacts/submission_D_rl.tar.gz
```

Pass when the correct gate is applied and any package is validated.

### AC-14 — Kaggle workflow and promotion decision

Evidence:

```text
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_rl_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

When `DO_NOT_SUBMIT`, evidence must state `SKIPPED_BY_GATE`.

Pass when the correct conditional workflow is followed.

### AC-15 — Next-step decision

Evidence:

```text
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
```

Pass when exactly one next step and one highest-leverage blocker are identified.

### AC-16 — Git and source integrity

Evidence:

```text
results/GIT_REPORT.md
results/artifacts/c008.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

Pass when c008 implementation is committed, earlier contracts are unchanged, and no credentials or prohibited files are committed.

---

## 23. Required results structure

```text
contracts/c008_fixed_deck_teacher_anchored_rl/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── dependency_verification.txt
│   ├── rl_environment_tests.txt
│   ├── action_decoder_tests.txt
│   ├── ppo_unit_tests.txt
│   ├── ppo_smoke_training.txt
│   ├── training_R0.txt
│   ├── training_R1.txt
│   ├── training_R2.txt
│   ├── checkpoint_selection.txt
│   ├── final_smoke_games.txt
│   ├── rl_teacher_execution.txt
│   ├── rl_strategic_execution.txt
│   ├── submission_D_smoke.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── dependency_verification.json
│   ├── immutability_verification.json
│   ├── EXPERIMENT_REGISTRATION.md
│   ├── experiment_registration.json
│   ├── rl_environment_schema.json
│   ├── action_decoder_coverage.json
│   ├── ppo_validation.json
│   ├── training/
│   │   ├── R0/
│   │   ├── R1/
│   │   └── R2/
│   ├── r0_training_summary.json
│   ├── r1_training_summary.json
│   ├── r2_training_summary.json
│   ├── teacher_anchor_report.json
│   ├── training_curves.csv
│   ├── training_curves.json
│   ├── plots/
│   ├── checkpoint_registry.json
│   ├── checkpoint_selection.json
│   ├── checkpoints/
│   ├── final_reliability.json
│   ├── final_latency.json
│   ├── rl_teacher_games.jsonl.gz
│   ├── rl_teacher_noninferiority.json
│   ├── rl_strategic_games.jsonl.gz
│   ├── rl_matchup_matrix.csv
│   ├── rl_global_ranking.json
│   ├── rl_holdout_report.json
│   ├── rl_improvement_report.json
│   ├── rl_regression_report.json
│   ├── rl_arm_selection.json
│   ├── RL_FEASIBILITY.md
│   ├── SUBMISSION_D_DECISION.md
│   ├── submission_D_rl.tar.gz
│   ├── submission_D_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_rl_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── NEXT_STEP.md
│   ├── next_step.json
│   ├── c008.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
└── failures/
```

Conditional artifacts may be absent only where explicitly allowed.

---

## 24. Required summary and status

`SUMMARY.md` must include:

- dependency and immutability status
- fixed deck ID and hash
- teacher ID and submission reference
- PPO configuration
- environment throughput
- games and decisions per arm/seed
- early-stop reasons
- learning-curve conclusions
- selected checkpoint per arm
- teacher head-to-head results
- strategic and held-out results
- major regressions
- best RL arm
- RL feasibility
- Submission D decision
- Kaggle submission reference/status/score when applicable
- teacher same-run score snapshot
- promotion decision
- next step
- highest-leverage blocker
- known limitations

`STATUS.json`:

```json
{
  "contract": "c008_fixed_deck_teacher_anchored_rl",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "teacher_id": "...",
  "teacher_submission_ref": "54948560",
  "deck_id": "...",
  "best_rl_arm": "NONE",
  "rl_feasibility": "INCONCLUSIVE",
  "submission_D_decision": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "rl_public_score": null,
  "teacher_public_score_same_run": null,
  "promotion_decision": "NO_RL_SUBMISSION",
  "next_step": "REVISE_RL",
  "highest_leverage_blocker": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

A contract `PASS` does not require successful RL or a submission. It requires complete, reproducible execution and correct decisions.

---

## 25. Git requirements

Branch:

```text
contract/c008_fixed_deck_teacher_anchored_rl
```

Create from accepted c007 final HEAD.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c008:
```

Recommended commits:

```text
c008: add masked PPO environment and validation
c008: train fixed-deck R0 R1 and R2 policies
c008: add RL evaluation packaging and kaggle workflow
```

Do not:

- push
- force-push
- rebase shared history
- amend user commits
- modify c005–c007
- modify the frozen teacher or deck
- commit credentials
- change the held-out opponent
- lower gates after seeing results
- use the final test results to retrain

---

## 26. Stop and status conditions

Set `BLOCKED` when:

- required frozen assets are unavailable
- dependency hashes fail
- action forms cannot be represented correctly
- cabt or training dependencies are unavailable
- user changes overlap and cannot be preserved

Set `PARTIAL` when:

- any mandatory acceptance criterion is incomplete
- registered seeds are skipped without a stop-rule result
- training budgets or populations are changed post hoc
- final evaluation is incomplete
- a qualifying package cannot be validated
- an authorized Kaggle upload fails externally
- earlier contract files are modified

Do not create a submission from a non-qualifying checkpoint.

---

## 27. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Teacher:
Teacher submission ref:
Frozen deck:
PPO configuration:
R0 games and result:
R1 games and result:
R2 games and result:
Best R0 checkpoint:
Best R1 checkpoint:
Best R2 checkpoint:
Best RL arm:
RL feasibility:
Teacher non-inferiority:
Strategic-field improvement:
Held-out Abomasnow result:
Major regressions:
Submission D decision:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
RL public score snapshot:
Teacher public score same run:
Promotion decision:
Next step:
Highest-leverage blocker:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria are executed and verified.
