# c006 — Distilled Policy Baseline

## 1. Winning objective

Train and evaluate our first neural policy on the exact frozen Dragapult teacher deck selected in c005.

This contract must answer, with gameplay evidence:

1. Can a compact stateless legal-action model reproduce the teacher?
2. Does sequence memory materially improve imitation and gameplay?
3. Can the best student match the frozen teacher closely enough to justify RL improvement?
4. Is the best student safe and efficient enough to package as a Kaggle submission?

This contract must finish with explicit decisions:

```text
BEST_STUDENT = S1_STATELESS | S2_RECURRENT | NONE
SUBMISSION_B = SUBMIT | DO_NOT_SUBMIT
RL_READINESS = READY_FOR_RL | NOT_READY_FOR_RL
```

A negative result is acceptable. The contract may `PASS` with `DO_NOT_SUBMIT` or `NOT_READY_FOR_RL` when every experiment and acceptance criterion is completed honestly.

Do not perform RL in c006.

---

## 2. Strategic context

c005 produced:

- A frozen official Dragapult teacher and exact 60-card deck.
- A validated Submission A archive.
- Four official strategic opponents.
- A model-ready teacher dataset.
- Whole-game train, validation, and test splits.
- Approximately 19,000 teacher decisions.
- A completed live Kaggle Submission A:
  - submission ref: `54948560`
  - submitted at: `2026-07-24 10:04:26.770000`
  - status at recorded snapshot: `SubmissionStatus.COMPLETE`
  - public score at recorded snapshot: `617.8`
  - description: `c005 Submission A: frozen teacher dragapult`

The c005 directory is immutable. c006 must preserve this external result inside its
own inputs/results and must not edit any c005 file.

Winning-oriented review identified critical risks:

1. The Dragapult teacher is stateful and keeps internal game/turn memory.
2. The model-ready c005 records omitted decision ordering fields even though raw capture preserved ordering.
3. Context names alone are weak proxies for decision importance.
4. The proposed 1–5 million parameter model is too large for the current dataset.
5. Card vocabulary must cover the full competition-legal pool.
6. Multi-select decisions require context-aware decoding.
7. Gameplay non-inferiority matters more than raw action agreement.

c006 must correct these issues before RL begins.

---

## 3. Dependencies

Required accepted artifacts and source:

```text
c001–c005 source code
c005 frozen teacher
c005 frozen Dragapult deck
c005 teacher dataset
c005 train/validation/test split
c005 official strategic candidates
c004/c005 gauntlet infrastructure
```

Before work begins, verify:

- c005 status and final Git commit.
- Frozen teacher source hashes.
- Frozen deck ID.
- Dataset manifest hashes.
- Split integrity.
- Submission A archive hash.
- `inputs/submission_A_kaggle_baseline.json`.

Copy the supplied teacher ladder record into:

```text
results/artifacts/baselines/submission_A_teacher_recorded.json
```

Then query Kaggle and write a fresh same-run snapshot to:

```text
results/artifacts/baselines/submission_A_teacher_live.json
results/test_logs/teacher_kaggle_refresh.txt
```

The live refresh must preserve the recorded snapshot rather than overwriting it.

If required c005 artifacts are missing or hashes do not match, set `BLOCKED`.

### Absolute c005 immutability

Do not modify, append to, reformat, or commit any file under:

```text
contracts/c005_teacher_import_submission_and_dataset/
```

This includes `SUMMARY.md`, `STATUS.json`, and all c005 result artifacts.

All new teacher-submission evidence belongs under c006 results.

---

## 4. Scope

Expected implementation:

- Sequence-preserving dataset rebuild
- Full legal-card vocabulary and features
- Decision-importance taxonomy
- Stateless student
- Recurrent student
- Context-aware action decoder
- Deterministic training scripts
- Checkpoint selection
- Offline imitation evaluation
- Full-game strategic evaluation
- Student packaging
- Submission decision
- RL-readiness decision
- Evidence and Git reports

---

## 5. Non-goals

Do not implement:

- PPO, policy-gradient RL, or self-play training
- MCTS, beam search, or search-generated labels
- Deck changes
- Teacher strategy changes
- Proprietary deck creation
- New LLM labels
- Broad hyperparameter search
- More than the pre-registered student architectures
- Schema v3
- Unrelated infrastructure refactoring

The frozen teacher and frozen deck must remain unchanged.

---

## 6. Experiment registration

Before training, create:

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
```

It must freeze:

- Dataset hashes and split IDs
- Teacher/deck hashes
- Feature schema
- Card vocabulary
- Decision taxonomy
- Model architectures
- Model parameter ceilings
- Training seeds
- Optimizer and learning rates
- Early-stopping metric
- Offline evaluation metrics
- Gameplay gauntlet
- Non-inferiority test
- Submission gate
- RL-readiness gate

No unregistered architecture or metric may become the final winner.

A single documented emergency correction is allowed only for a code defect that invalidates all runs. It must restart every affected model fairly.

---

## 7. Dataset reconstruction and sequence integrity

### 7.1 Rebuild ordered records

Rebuild model-ready examples from the raw c005 capture while preserving:

```json
{
  "game_id": "...",
  "decision_index": 0,
  "turn_index": 0,
  "step_index": 0,
  "teacher_seat": 0,
  "previous_context": null,
  "previous_teacher_action_indices": [],
  "observation": {},
  "legal_options": [],
  "teacher_action_indices": []
}
```

Use actual turn/step fields when exposed.

When a turn identifier is unavailable, derive a deterministic turn boundary from observation state/logs and document the method.

### 7.2 Game sequences

Create a sequence index:

```text
game_id → ordered example IDs
```

No sequence may cross game boundaries.

Hidden state must reset at the start of every game.

### 7.3 Split preservation

Preserve c005 game-level train/validation/test membership exactly.

No game may move between splits.

The c005 test split remains untouched until final offline model evaluation.

### 7.4 Stateless ambiguity diagnostic

Identify cases where:

- Visible normalized observation is equivalent.
- Legal options are equivalent.
- Teacher actions differ across histories.

Report:

- Exact duplicate-state ambiguity
- Near-duplicate ambiguity under a documented hash
- Contexts most affected
- An empirical upper bound on stateless exact agreement

Do not claim this bound is mathematically exact unless equivalence is exact.

---

## 8. Full legal-card vocabulary

Build a vocabulary over the complete competition-legal card pool available to the engine.

For every legal card ID, include structured features available from official/cabt metadata:

- Card ID
- Card type
- HP
- Evolution stage
- Energy type
- Retreat cost
- Weakness/resistance
- Attack costs
- Number of attacks/abilities
- Text-presence flags
- Other stable numeric/categorical metadata

Requirements:

- Unseen legal cards must not collapse to a single generic `<UNK>`.
- Reserve `<PAD>`, `<MASK>`, and `<UNKNOWN_INVALID_ID>` only for technical cases.
- Record source and hash of the legal-card list.
- Validate that every card in all teacher/opponent decks is present.

Do not build an executable card-effect DSL.

---

## 9. Decision importance taxonomy

Do not classify importance only by `SelectContext`.

Classify each decision using:

- SelectContext
- Option types
- Number of legal options
- Whether the choice is forced
- Attack availability
- Promotion/switch/evolution semantics
- Card/target selection semantics
- Multi-select cardinality
- End-turn availability
- Dragapult-specific damage-counter decisions

Required importance classes:

```text
FORCED
ROUTINE
TACTICAL
HIGH_IMPACT
```

At minimum, treat these semantically when present:

- Attack choice inside `MAIN`
- Attack target
- Promotion to active
- Energy attachment target
- Evolution target
- Search/card target
- Retreat/switch
- Dragapult damage-counter assignment
- End-turn while attack is available
- Multi-select discard/resource decisions

Produce a human-reviewable sample of at least 100 classified decisions.

---

## 10. Student architectures

Train exactly two primary architectures.

## S1 — Stateless structured action scorer

Inputs:

```text
current normalized observation
frozen deck representation
SelectContext
decision taxonomy features
legal-option representations
```

Outputs:

```text
score per currently legal option
context-aware multi-select output where required
```

Constraints:

- Target parameter count: 150,000–500,000
- Hard maximum: 750,000 trainable parameters
- No recurrent state
- No generative text
- No fixed global action output

## S2 — Recurrent structured action scorer

Same structured inputs as S1, plus game-sequence memory.

Use:

- One small GRU or equivalent recurrent state
- Reset at game start
- Truncated backpropagation through time when necessary
- Previous context and previous action as explicit inputs

Constraints:

- Target parameter count: 250,000–650,000
- Hard maximum: 900,000 trainable parameters

Do not expose the teacher’s private internal variables directly as runtime inputs. The student must infer useful memory from observable history.

## Safety policy

For both students:

- Forced decisions bypass the neural model.
- Unsupported context/decoder form uses deterministic safe fallback.
- Invalid model output uses deterministic safe fallback.
- Every fallback is logged with reason.
- The model may never return an illegal action.

---

## 11. Context-aware action decoding

Implement and test:

### Single-choice

Masked softmax over current legal options.

### Fixed-cardinality unordered multi-select

Predict one score per option and choose masked top-k where `k` is required.

### Variable-cardinality unordered selection

Use option scores plus a cardinality/stop prediction, only if this form exists in the training data.

### Ordered selection

If an ordered multi-select form exists in c005 data, implement a compact autoregressive pointer decoder or route that form to deterministic safe fallback.

Do not misrepresent ordered decisions as unordered BCE labels.

Produce a decoder-coverage report for all c005 decision forms.

---

## 12. Training protocol

### 12.1 Seeds

Train each architecture with exactly three registered seeds:

```text
S1: 3 seeds
S2: 3 seeds
```

No broad sweep.

### 12.2 Data use

- Train split: optimization
- Validation split: early stopping and checkpoint selection
- Test split: opened only after the best seed/checkpoint per architecture is frozen

### 12.3 Losses

Use:

- Masked cross-entropy for single-choice
- Appropriate set/cardinality loss for unordered multi-select
- Decoder-specific loss for ordered selection when implemented
- Optional importance weighting

Register all weights before training.

### 12.4 Early stopping

Primary validation metric:

```text
importance-weighted teacher action agreement
```

Secondary:

- Overall exact agreement
- High-impact exact agreement
- Top-k agreement
- Multi-select exact-set agreement
- Negative log likelihood

### 12.5 Checkpoint selection

Select one checkpoint per architecture using validation only.

After checkpoint hashes are frozen, evaluate once on the test split.

No test-driven retraining.

---

## 13. Offline evaluation

Report for S1 and S2:

- Overall exact action agreement
- Importance-weighted agreement
- Agreement by taxonomy class
- Agreement by SelectContext
- Agreement by semantic decision type
- Top-2 and top-3 agreement
- Multi-select exact-set and element-level metrics
- Calibration/confidence
- Unsupported/fallback rate
- Test negative log likelihood
- Parameter count
- Model size
- CPU inference P50/P95/P99/max

Also report:

```text
S2 improvement over S1
```

with bootstrap intervals by game.

### Sequence-memory decision

Declare:

```text
MEMORY_MATTERS
MEMORY_NOT_JUSTIFIED
```

Memory is justified when S2:

- Improves high-impact test agreement by at least 2 percentage points; or
- Improves game-level importance-weighted agreement with a 95% bootstrap interval above zero; or
- Produces a material gameplay improvement later.

---

## 14. Gameplay evaluation

Evaluate:

```text
T  = frozen Dragapult teacher
S1 = selected stateless checkpoint
S2 = selected recurrent checkpoint
C  = deterministic engineering control
```

All use the exact frozen Dragapult deck where applicable.

### 14.1 Reliability smoke

For S1 and S2:

- 20 games as seat 0
- 20 games as seat 1
- At least two strategic opponents

Require zero invalid actions, attributable exceptions, and timeouts.

### 14.2 Student–teacher head-to-head

For each student against teacher:

Initial:

```text
100 games with student as seat 0
100 games with student as seat 1
```

Extend in balanced increments of 50 per orientation up to 400 total games when the result is statistically ambiguous.

Compute student score where:

- win = 1
- draw = 0.5
- loss = 0

Use a one-sided 95% confidence lower bound.

Non-inferiority margin:

```text
student score >= 0.45 versus teacher
```

Non-inferiority passes when the one-sided lower bound is at least 0.45.

### 14.3 Strategic gauntlet

Evaluate teacher, S1, and S2 against:

- Official Mega Lucario
- Official Mega Abomasnow
- Official Iono
- Teacher mirror
- Engineering control reported separately

Use both seats and the c004/c005 sequential protocol.

Report:

- Global ranking
- Pairwise intervals
- Worst matchup
- Seat effects
- Reliability
- Latency
- Fallback use

### 14.4 Major regression rule

A student has a major matchup regression when its seat-balanced point estimate is at least 10 percentage points below the teacher against the same strategic opponent and the bootstrap probability of regression is at least 90%.

---

## 15. Best-student selection

Only reliability-eligible students may be selected.

Select by:

1. Passes teacher non-inferiority.
2. Highest strategic-gauntlet strength.
3. No major matchup regression.
4. Higher high-impact test agreement.
5. Lower fallback rate.
6. Lower P99 latency.
7. Smaller model when otherwise tied.

If neither student passes non-inferiority:

```text
BEST_STUDENT = NONE
```

Do not select a student merely because it is better than the other student.

---

## 16. Student submission package

If `BEST_STUDENT != NONE`, build:

```text
submission_B_student.tar.gz
```

Requirements:

- Exact frozen Dragapult deck
- Selected model weights
- Model code
- Safe fallback
- Required `cg/` package structure
- No training data
- No secrets
- Size below competition limit
- Clean extraction
- At least 40 extracted-package games against strategic opponents
- Zero invalid actions/errors/timeouts
- P99 latency safely inside the match-clock envelope

If no student passes:

- Do not create a misleading ready-to-submit package.
- An internal diagnostic archive may be produced with a clear `NOT_FOR_SUBMISSION` marker.

---

## 17. Submission and RL-readiness decisions

## Submission B

Set:

```text
SUBMIT
```

only when:

- A best student exists.
- Teacher non-inferiority passes.
- No major matchup regression.
- Reliability is perfect in official evaluation.
- Package validation passes.
- P99 latency and size pass.

Otherwise:

```text
DO_NOT_SUBMIT
```

## RL readiness

Set:

```text
READY_FOR_RL
```

only when:

- A best student exists.
- Submission gate passes or misses only for a non-policy operational issue.
- The student is not materially weaker than teacher.
- The representation/decoder covers at least 99% of teacher decisions without strategic fallback.
- Sequence-memory decision is resolved.
- Frozen student checkpoint and evaluation are reproducible.

Otherwise:

```text
NOT_READY_FOR_RL
```

Provide the single highest-leverage blocker.

---

## 18. Mandatory Kaggle submission and result retrieval

When `SUBMISSION_B = SUBMIT`, Claude Code is explicitly authorized and required to:

1. Submit `submission_B_student.tar.gz` to the competition.
2. Retrieve the created submission row.
3. Record its immutable submission reference.
4. Poll synchronously for processing status.
5. Retrieve and record the public score when available.
6. Compare the student snapshot with the teacher baseline without modifying c005.

Use the official Kaggle CLI competition commands.

### 18.1 Submission identity

Use a unique message containing:

```text
c006 Submission B: distilled <BEST_STUDENT> <final_commit_short_sha>
```

Before submitting, calculate and record:

- Archive SHA-256
- Archive size
- Final Git commit
- Selected checkpoint SHA-256
- Frozen deck ID
- Teacher ID

### 18.2 Pre-submission duplicate guard

Retrieve existing submissions before upload.

Do not upload when an existing row has both:

- the same description; and
- the same archive SHA-256 recorded by this project.

If a matching submission exists, reuse its submission reference and continue retrieval.

### 18.3 Required submit command

Use the current official equivalent of:

```bash
kaggle competitions submit pokemon-tcg-ai-battle   -f contracts/c006_distilled_policy_baseline/results/artifacts/submission_B_student.tar.gz   -m "<unique c006 message>"
```

Capture stdout/stderr in:

```text
results/test_logs/kaggle_submission.txt
```

Never print or store credentials.

### 18.4 Submission-row retrieval

Immediately retrieve the user's competition submissions in verbose CSV form and preserve the raw response:

```text
results/artifacts/kaggle_submissions_after_submit.csv
results/test_logs/kaggle_submission_retrieval.txt
```

Match the submitted row primarily by the unique description and file name. Record:

```json
{
  "competition": "pokemon-tcg-ai-battle",
  "submission_ref": "...",
  "file_name": "submission_B_student.tar.gz",
  "local_archive": "...",
  "archive_sha256": "...",
  "description": "...",
  "submitted_at": "...",
  "status": "...",
  "public_score": "",
  "private_score": "",
  "source": "kaggle competitions submissions",
  "raw_submission": {}
}
```

Write it to:

```text
results/artifacts/kaggle_submission_status.json
```

### 18.5 Bounded status polling

After the row is found, poll synchronously:

```text
every 30 seconds
maximum 20 retrieval attempts
```

Stop early when status becomes terminal, including `COMPLETE` or an error state.

Preserve every observation in:

```text
results/artifacts/kaggle_submission_history.jsonl
```

Do not claim the public score is final; it is a timestamped ladder snapshot.

If processing remains pending after the bounded polling window:

- Keep the submission reference.
- Record the latest status as `PENDING`.
- Do not mark the contract `PARTIAL` solely because Kaggle is still processing.
- Provide the exact refresh command.

If credentials are missing, the competition rejects the upload, the daily limit is reached,
or network access fails:

- Do not fake submission evidence.
- Set `KAGGLE_UPLOAD = BLOCKED`.
- Record exact stderr and the blocker.
- Set the contract `PARTIAL` because the user explicitly authorized and required submission.

### 18.6 Teacher/student ladder comparison

Retrieve the teacher row for submission ref `54948560` in the same execution window.

Create:

```text
results/artifacts/kaggle_teacher_student_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
```

The comparison must include:

- Teacher recorded snapshot: `617.8`
- Teacher live same-run snapshot, if retrievable
- Student live snapshot, if complete
- Score timestamps
- Number/status maturity caveat
- Local teacher/student evidence

Set:

```text
PROMOTION_DECISION =
    PROMOTE_STUDENT
  | KEEP_TEACHER
  | WAIT_FOR_MORE_GAMES
  | NO_STUDENT_SUBMISSION
```

Rules:

- `PROMOTE_STUDENT` only when the student has completed processing and current external evidence plus local evidence support it.
- `KEEP_TEACHER` when the completed student is clearly worse or locally unsafe.
- `WAIT_FOR_MORE_GAMES` when external evidence is immature or too close to interpret.
- Never call the student better solely from one noisy score snapshot.

When `SUBMISSION_B = DO_NOT_SUBMIT`, perform no upload and set:

```text
KAGGLE_UPLOAD = SKIPPED_BY_GATE
PROMOTION_DECISION = NO_STUDENT_SUBMISSION
```

---

## 19. Mandatory acceptance criteria

### AC-01 — Dependency and freeze verification

Evidence:

```text
results/artifacts/c005_dependency_verification.json
results/artifacts/baselines/submission_A_teacher_recorded.json
results/artifacts/baselines/submission_A_teacher_live.json
results/test_logs/dependency_verification.txt
results/test_logs/teacher_kaggle_refresh.txt
```

Pass when all required c005 hashes and split memberships match, the supplied
teacher submission record is preserved under c006, a live refresh is attempted,
and no c005 file is modified.

### AC-02 — Ordered sequence dataset

Evidence:

```text
results/artifacts/sequence_dataset/
results/artifacts/sequence_dataset_manifest.json
results/test_logs/sequence_dataset_validation.txt
```

Pass when order, game boundaries, turn/step fields, and original split membership are validated.

### AC-03 — Stateless ambiguity analysis

Evidence:

```text
results/artifacts/stateless_ambiguity_report.json
results/artifacts/stateless_ambiguity_examples.jsonl
```

Pass when exact and near-duplicate ambiguity is quantified and reproducible.

### AC-04 — Full legal-card vocabulary

Evidence:

```text
results/artifacts/card_vocabulary.json
results/artifacts/card_feature_schema.json
results/test_logs/card_vocabulary_tests.txt
```

Pass when all legal and candidate-deck cards are represented without generic legal-card collapse.

### AC-05 — Decision taxonomy and decoder coverage

Evidence:

```text
results/artifacts/decision_taxonomy.json
results/artifacts/decision_taxonomy_samples.jsonl
results/artifacts/decoder_coverage_report.json
results/test_logs/decoder_tests.txt
```

Pass when every c005 decision form is classified and supported or explicitly routed to safe fallback.

### AC-06 — Registered reproducible training

Evidence:

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
results/artifacts/training_runs.json
results/test_logs/training_S1.txt
results/test_logs/training_S2.txt
```

Pass when exactly three seeds per architecture complete and all final checkpoints are reproducible.

### AC-07 — Frozen offline model evaluation

Evidence:

```text
results/artifacts/offline_evaluation.json
results/artifacts/offline_metrics_by_context.csv
results/artifacts/offline_metrics_by_semantic_type.csv
results/artifacts/memory_ablation.json
results/test_logs/offline_evaluation.txt
```

Pass when selected checkpoints are evaluated once on the frozen test split and S1/S2 comparison is complete.

### AC-08 — Reliability and CPU inference

Evidence:

```text
results/artifacts/model_latency_report.json
results/artifacts/model_reliability_report.json
results/test_logs/model_smoke_games.txt
```

Pass when S1 and S2 complete required smoke games with no invalid actions/errors/timeouts and latency is reported.

### AC-09 — Student–teacher non-inferiority

Evidence:

```text
results/artifacts/student_teacher_games.jsonl.gz
results/artifacts/student_teacher_noninferiority.json
results/test_logs/student_teacher_execution.txt
```

Pass when both students complete the registered head-to-head and the statistical conclusion is reproducible. Passing the AC does not require non-inferiority itself.

### AC-10 — Strategic gauntlet comparison

Evidence:

```text
results/artifacts/student_strategic_gauntlet.jsonl.gz
results/artifacts/student_matchup_matrix.csv
results/artifacts/student_global_ranking.json
results/artifacts/student_worst_matchups.json
results/artifacts/student_regression_report.json
results/test_logs/student_gauntlet_execution.txt
```

Pass when teacher, S1, and S2 are evaluated against the fixed strategic field in both seats.

### AC-11 — Best-student and memory decisions

Evidence:

```text
results/artifacts/student_selection.json
results/artifacts/student_selection.md
```

Pass when `BEST_STUDENT` and memory decisions follow the predefined rules, including `NONE` when appropriate.

### AC-12 — Submission B package, Kaggle upload, and result retrieval

Evidence:

```text
results/artifacts/SUBMISSION_B_DECISION.md
results/artifacts/submission_B_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_student_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/submission_B_smoke.txt
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

When best student exists and the gate says `SUBMIT`, also:

```text
results/artifacts/submission_B_student.tar.gz
```

Pass when:

- The correct `SUBMIT`/`DO_NOT_SUBMIT` gate is applied.
- Any package is validated.
- A gated `SUBMIT` is actually uploaded or an exact external blocker is recorded.
- The submission row/reference is retrieved when upload succeeds.
- Bounded status polling is executed.
- Teacher/student ladder evidence and promotion decision are preserved.
- No c005 file is changed.

### AC-13 — RL readiness decision

Evidence:

```text
results/artifacts/RL_READINESS.md
results/artifacts/rl_readiness.json
```

Pass when readiness is decided under the registered gate and one highest-leverage blocker is identified when not ready.

### AC-14 — Git and source integrity

Evidence:

```text
results/GIT_REPORT.md
results/artifacts/c006.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

Pass when source, models, configs, and evaluation code are committed appropriately without modifying frozen teacher/deck or earlier results.

---

## 20. Required results structure

```text
contracts/c006_distilled_policy_baseline/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── dependency_verification.txt
│   ├── sequence_dataset_validation.txt
│   ├── card_vocabulary_tests.txt
│   ├── decoder_tests.txt
│   ├── training_S1.txt
│   ├── training_S2.txt
│   ├── offline_evaluation.txt
│   ├── model_smoke_games.txt
│   ├── student_teacher_execution.txt
│   ├── student_gauntlet_execution.txt
│   ├── submission_B_smoke.txt
│   ├── teacher_kaggle_refresh.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── c005_dependency_verification.json
│   ├── baselines/
│   │   ├── submission_A_teacher_recorded.json
│   │   └── submission_A_teacher_live.json
│   ├── sequence_dataset/
│   ├── sequence_dataset_manifest.json
│   ├── stateless_ambiguity_report.json
│   ├── stateless_ambiguity_examples.jsonl
│   ├── card_vocabulary.json
│   ├── card_feature_schema.json
│   ├── decision_taxonomy.json
│   ├── decision_taxonomy_samples.jsonl
│   ├── decoder_coverage_report.json
│   ├── EXPERIMENT_REGISTRATION.md
│   ├── experiment_registration.json
│   ├── training_runs.json
│   ├── checkpoints/
│   ├── offline_evaluation.json
│   ├── offline_metrics_by_context.csv
│   ├── offline_metrics_by_semantic_type.csv
│   ├── memory_ablation.json
│   ├── model_latency_report.json
│   ├── model_reliability_report.json
│   ├── student_teacher_games.jsonl.gz
│   ├── student_teacher_noninferiority.json
│   ├── student_strategic_gauntlet.jsonl.gz
│   ├── student_matchup_matrix.csv
│   ├── student_global_ranking.json
│   ├── student_worst_matchups.json
│   ├── student_regression_report.json
│   ├── student_selection.json
│   ├── student_selection.md
│   ├── SUBMISSION_B_DECISION.md
│   ├── submission_B_validation.json
│   ├── submission_B_student.tar.gz
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_student_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── RL_READINESS.md
│   ├── rl_readiness.json
│   ├── c006.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
└── failures/
```

If no student qualifies, `submission_B_student.tar.gz` may be absent.

---

## 21. Required summary

`SUMMARY.md` must include:

- Final status
- Dataset examples and games
- Stateless ambiguity
- Card vocabulary size
- S1/S2 parameter counts
- Training seeds and selected checkpoints
- Test agreement metrics
- Memory decision
- Student–teacher results
- Strategic-gauntlet results
- Reliability and latency
- Best student
- Submission B decision
- Kaggle upload status
- Kaggle submission reference
- Kaggle processing status
- Student public-score snapshot
- Teacher recorded and live score snapshots
- Promotion decision
- RL readiness
- Exact blocker if not ready

`STATUS.json`:

```json
{
  "contract": "c006_distilled_policy_baseline",
  "status": "PASS",
  "acceptance_criteria_total": 14,
  "acceptance_criteria_passed": 14,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "teacher_id": "...",
  "deck_id": "...",
  "best_student": "S1_STATELESS",
  "memory_decision": "MEMORY_NOT_JUSTIFIED",
  "submission_B_decision": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "student_public_score": null,
  "teacher_recorded_public_score": 617.8,
  "teacher_live_public_score": null,
  "promotion_decision": "NO_STUDENT_SUBMISSION",
  "rl_readiness": "NOT_READY_FOR_RL",
  "blocking_issues": [],
  "known_limitations": []
}
```

A `PASS` does not require a successful student; it requires correct execution and decision-making.

---

## 22. Git requirements

Branch:

```text
contract/c006_distilled_policy_baseline
```

Create from accepted c005 final HEAD.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c006:
```

Recommended commits:

```text
c006: add sequence dataset and structured policy features
c006: train stateless and recurrent distilled students
c006: add gameplay evaluation and submission decision
```

Do not:

- Push
- Force-push
- Rebase shared history
- Amend user commits
- Modify frozen teacher/deck
- Modify any file under `contracts/c005_teacher_import_submission_and_dataset/`
- Modify earlier results
- Commit credentials
- Use the test split for training decisions

---

## 23. Stop and status conditions

Set `BLOCKED` if:

- c005 frozen assets or hashes are unavailable.
- Training dependencies cannot run.
- Cabt runtime is unavailable.
- User changes overlap and cannot be preserved.

Set `PARTIAL` if:

- Any mandatory AC is incomplete.
- Fewer than three seeds per architecture complete.
- Test split is used before checkpoint freeze.
- Gameplay comparison is incomplete.
- Decision taxonomy or decoder coverage is unknown.
- Submission or RL-readiness decision cannot be made.

Do not lower gates to force a student submission.

---

## 24. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Teacher:
Frozen deck:
Sequence examples:
Card vocabulary:
S1 parameters:
S2 parameters:
Selected S1 checkpoint:
Selected S2 checkpoint:
Memory decision:
S1 vs teacher:
S2 vs teacher:
Best student:
Submission B decision:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Student public score snapshot:
Teacher recorded public score:
Teacher live public score:
Promotion decision:
RL readiness:
Highest-leverage blocker:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all fourteen acceptance criteria are executed and verified.
