# c009 — Amendment to c008: Evaluation Repair and RL Evidence Recalibration

## 1. Purpose

Repair the c008 evaluation evidence without modifying c008, retraining any policy, changing the frozen Dragapult deck, or changing the teacher.

c009 must determine, from corrected raw-game evidence:

1. Whether any saved c008 R1 or R2 checkpoint improved over the untouched c007 V2-A initialization.
2. Which saved checkpoint is actually strongest.
3. Whether any saved RL checkpoint is teacher-non-inferior.
4. Whether the c008 strategic-field, held-out, regression, feasibility, and next-step conclusions remain valid.
5. Whether any already-trained checkpoint qualifies for submission on the exact frozen deck.
6. Whether one redesigned teacher-anchored RL experiment is justified.

This is an amendment and evidence-repair contract, not a new RL experiment.

Required final decisions:

```text
C008_EVALUATION = REPAIRED | UNREPAIRABLE
RL_IMPROVED_OVER_INITIALIZATION = YES | NO | INCONCLUSIVE
BEST_SAVED_CHECKPOINT =
    V2A_BASELINE
  | R0_<seed>_<checkpoint>
  | R1_<seed>_<checkpoint>
  | R2_<seed>_<checkpoint>
  | NONE
TEACHER_NONINFERIORITY = PASS | FAIL | NOT_TESTABLE
RL_FEASIBILITY_RECALIBRATED = PROVEN | INCONCLUSIVE | REJECTED
SUBMISSION_D_AMENDED = SUBMIT | DO_NOT_SUBMIT
PROMOTION_DECISION =
    PROMOTE_RL
  | KEEP_TEACHER
  | WAIT_FOR_MORE_GAMES
  | NO_RL_SUBMISSION
NEXT_STEP =
    REDESIGN_TEACHER_ANCHORED_RL
  | FIXED_DECK_SELECTIVE_SEARCH
  | BEGIN_DECK_PIPELINE
```

A negative result may still produce contract `PASS` when every repair and decision criterion completes honestly.

---

## 2. Known c008 defects to repair

c009 begins with these known issues, which must be independently reproduced and documented.

### 2.1 Strategic-result identity corruption

The c008 evaluator used unordered multiprocessing results and then reassigned arm labels by positional `zip`.

Pattern:

```python
results = pool.imap_unordered(worker, jobs)
for job, result in zip(jobs, results):
    result['arm'] = job['arm']
```

This can associate a completed game with the wrong policy arm.

The c008 aggregate artifacts showed impossible per-arm game counts, confirming corruption.

### 2.2 Median representative presented as “best”

c008 selected a median seed representative for final evaluation, but summaries described it as the best checkpoint per arm.

c009 must distinguish:

```text
typical arm representative
best validation-selected checkpoint
best corrected-evaluation checkpoint
```

### 2.3 No untouched V2-A game-zero baseline

c008 did not evaluate the exact c007 V2-A initialization under the same final protocol.

Therefore, improvement from RL over initialization was not established.

### 2.4 Content-blind acceptance validation

c008 acceptance reporting treated file existence as criterion success without validating artifact contents.

c009 must validate content, raw-game counts, identity, hashes, and aggregate reproducibility.

### 2.5 R2 interpretation limits

c009 does not retrain R2, but its conclusion must acknowledge:

- KL anchored to V2-A rather than the rule teacher.
- Teacher-replay loss was strong relative to PPO.
- Low-anchor schedule phases may not have been reached.
- Multi-select reference KL may cover only the first sub-selection.

These are algorithmic limitations, not reasons to alter saved checkpoints.

---

## 3. Dependencies and immutability

Required:

```text
c005 frozen Dragapult teacher and deck
c007 selected untouched V2-A checkpoint
c008 checkpoint registry
c008 checkpoint-selection artifacts
c008 saved R0/R1/R2 checkpoints
c008 direct teacher games
c008 training curves and summaries
c008 source code
official strategic opponents from c005
```

Before work:

- Record current branch and HEAD.
- Record c005–c008 final commits.
- Verify teacher, deck, V2-A, and every evaluated checkpoint hash.
- Verify c008 raw source and result artifacts are readable.
- Preserve pre-existing user changes.

### Absolute immutability

Do not modify any file under:

```text
contracts/c005_teacher_import_submission_and_dataset/
contracts/c006_distilled_policy_baseline/
contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/
contracts/c008_fixed_deck_teacher_anchored_rl/
```

Do not modify frozen teacher/deck files.

Create new repair tools and tests under c009-controlled project paths.

If required checkpoints are missing or corrupt, set `PARTIAL` or `BLOCKED` according to Section 26.

---

## 4. Scope

Expected work:

- Reproduce the c008 label-corruption bug.
- Build a corrected evaluation runner with immutable job identity.
- Add evaluator unit/integration tests.
- Enumerate and hash all candidate checkpoints.
- Evaluate untouched V2-A.
- Evaluate all validation-selected R1/R2 checkpoints.
- Optionally evaluate all selected R0 checkpoints as controls.
- Run staged teacher head-to-head.
- Run corrected strategic and held-out evaluation.
- Preserve compact raw per-game records.
- Recompute all aggregate reports from raw games.
- Add a content-aware evidence validator.
- Recalculate c008 decisions.
- Conditionally package and submit an already-trained RL checkpoint only if every amended gate passes.

---

## 5. Non-goals

Do not:

- Train or fine-tune any policy.
- Create a new checkpoint.
- Change PPO hyperparameters.
- Change reward shaping.
- Change opponent populations for training.
- Mutate the deck.
- Modify c008 tools or results.
- Re-run the 95,000+ training games.
- Perform new distillation.
- Perform selective search.
- Use final evaluation to alter weights.
- Lower c008 competitive gates.

---

## 6. Branch and naming

Branch:

```text
contract/c009_amendment_c008
```

New repair source should use c009 names, for example:

```text
tools/c009_eval_repair.py
tools/c009_aggregate_repair.py
tools/c009_validate_evidence.py
tests/test_c009_eval_identity.py
tests/test_c009_evidence_validation.py
```

Do not overwrite `tools/c008_*`.

---

## 7. Candidate checkpoint registry

Create a frozen registry containing at minimum:

### B0 — untouched supervised initialization

```text
B0 = exact c007 selected V2-A checkpoint before any RL update
```

### R1 candidates

Include every c008 R1 seed’s validation-selected checkpoint.

At minimum, inspect the c008 registry for:

```text
R1 seed 101
R1 seed 202
```

### R2 candidates

Include every c008 R2 seed’s validation-selected checkpoint.

At minimum:

```text
R2 seed 101
R2 seed 202
R2 seed 303
```

### R0 controls

Include each c008 R0 seed’s validation-selected checkpoint when present.

The registry must include:

```json
{
  "candidate_id": "...",
  "arm": "R1",
  "seed": 101,
  "training_games": 0,
  "checkpoint_path": "...",
  "checkpoint_sha256": "...",
  "source_selection_metric": 0.0,
  "source_selection_rank": 1,
  "is_median_representative": false,
  "is_best_within_arm_by_c008_validation": true
}
```

Do not infer checkpoint identities from filenames alone when a c008 registry exists.

---

## 8. Reproduce and test the c008 bug

### 8.1 Minimal reproduction

Create a deterministic test where worker completion order differs from job order.

Show that positional reassignment after `imap_unordered` produces incorrect policy identities.

### 8.2 Correct identity protocol

Every submitted job must contain:

```json
{
  "job_id": "...",
  "candidate_id": "...",
  "checkpoint_sha256": "...",
  "opponent_id": "...",
  "seat": 0,
  "replicate": 0,
  "requested_seed": 0
}
```

Every worker result must return the same identity fields directly.

No post-hoc positional reattachment is permitted.

### 8.3 Required assertions

Before aggregation:

```text
all submitted job IDs are unique
all returned job IDs are unique
submitted job-ID set equals returned job-ID set
candidate ID matches frozen job registry
checkpoint hash matches candidate registry
opponent and seat match the submitted job
expected count per candidate/opponent/seat is exact
no unexpected candidates or opponents exist
all games are terminal or explicitly classified as defects
```

Any failed identity assertion invalidates the evaluation.

---

## 9. Corrected raw-game schema

Preserve one record per game:

```json
{
  "job_id": "...",
  "candidate_id": "...",
  "arm": "R1",
  "seed": 101,
  "checkpoint_sha256": "...",
  "deck_id": "...",
  "opponent_id": "...",
  "seat": 0,
  "replicate": 0,
  "requested_seed": 0,
  "outcome": "win",
  "score": 1.0,
  "terminal": true,
  "decision_count": 0,
  "fallback_count": 0,
  "invalid_action_count": 0,
  "exception_count": 0,
  "timeout_count": 0,
  "latency_p50_ms": 0.0,
  "latency_p95_ms": 0.0,
  "latency_p99_ms": 0.0,
  "duration_seconds": 0.0
}
```

Store raw records compressed.

Raw records are the source of truth for every aggregate.

---

## 10. Evaluation phases

Use staged evaluation to minimize wasted games while preserving a fair decision.

## Phase A — Baseline and checkpoint screen

Evaluate all registered candidates against:

```text
frozen Dragapult teacher
```

Use:

```text
50 games per seat
100 total per candidate
```

Both seats are mandatory.

Calculate:

- Point estimate.
- Wilson or bootstrap interval.
- Defect counts.
- Latency.
- Seat effect.

A candidate advances to Phase B when either:

1. Point estimate is at least 0.25; or
2. Upper 95% confidence bound is at least 0.35; or
3. Candidate is the best R1 or best R2 checkpoint by c008 validation and must be confirmed as a mandatory arm representative.

B0 always advances.

At least one R1 and one R2 candidate advance unless no valid checkpoint exists.

## Phase B — Teacher confirmation

For advancing candidates, extend teacher comparison to:

```text
200 games per seat
400 total per candidate
```

When a candidate’s score remains plausibly near non-inferiority:

```text
upper uncertainty region overlaps 0.40 or higher
```

extend in balanced increments to a maximum of:

```text
400 games per seat
800 total
```

Teacher non-inferiority uses the original c008 rule:

```text
one-sided 95% lower bound >= 0.47
```

## Phase C — Corrected strategic field

Evaluate:

```text
T  = frozen teacher
B0 = untouched V2-A
best corrected R1 candidate
best corrected R2 candidate
best corrected R0 candidate, when valid
```

Against:

- Official Mega Lucario
- Official Iono
- Official Mega Abomasnow as held-out opponent
- Frozen Dragapult teacher mirror

For each candidate/opponent:

```text
50 games per seat
100 total
```

Engineering control may be evaluated separately and may not influence strategic rank.

## Phase D — Confirmation of a plausible submission candidate

Only when a saved RL candidate:

- passes teacher non-inferiority; and
- has no obvious strategic collapse

extend its strategic comparison and the teacher control to the c008 sequential maximum needed to test the original improvement and regression rules.

Do not extend clearly inferior candidates merely to consume the maximum budget.

---

## 11. Corrected candidate selection

### 11.1 Within-arm candidate

Select corrected best R1 and R2 checkpoints using:

1. Phase B teacher score.
2. Strategic-field score when teacher results are statistically tied.
3. Held-out Abomasnow score.
4. Lower worst-matchup risk.
5. Lower defect rate.
6. Lower P99 latency.
7. Earlier checkpoint when otherwise tied.

Report all seed results.

### 11.2 Global best saved checkpoint

An RL checkpoint may beat B0 only when:

- Teacher score exceeds B0’s teacher score; and
- Strategic-field score is not lower; and
- At least one of those differences has a 90% bootstrap probability above zero; and
- No major regression relative to B0 is found.

If no RL checkpoint satisfies this:

```text
RL_IMPROVED_OVER_INITIALIZATION = NO
BEST_SAVED_CHECKPOINT = V2A_BASELINE
```

Use `INCONCLUSIVE` only when uncertainty genuinely prevents a decision.

### 11.3 Teacher non-inferiority

Apply the original c008 gate exactly:

```text
one-sided 95% lower bound >= 0.47
```

Do not redefine the threshold.

---

## 12. Corrected strategic analysis

From corrected raw games, generate:

- Matchup matrix.
- Seat-balanced matrix.
- Pairwise confidence intervals.
- Global ranking or equivalent.
- Held-out Abomasnow report.
- Worst-matchup report.
- Improvement report.
- Regression report.
- Candidate-versus-B0 report.
- Candidate-versus-teacher report.

### Major regression

Preserve c008’s rule:

```text
candidate <= teacher - 0.07
and bootstrap probability of regression >= 90%
```

### Reproducible improvement over teacher

Preserve c008’s rule:

1. Global field score above teacher with 90% bootstrap interval above zero; or
2. One strategic matchup improves by at least 5 percentage points with at least 90% bootstrap probability, teacher non-inferiority passes, and no major regression exists.

### Improvement over initialization

Report separately from improvement over teacher.

Do not conflate:

```text
RL improved over B0
RL is competitive with teacher
RL beats teacher
```

---

## 13. Content-aware evidence validator

Implement a validator that checks artifact contents, not only existence.

At minimum validate:

- Every expected candidate exists in the registry.
- Every evaluated checkpoint hash matches.
- Every expected raw-game count is exact.
- Both seats are present equally.
- Raw-game job identities are complete.
- Aggregate counts reproduce raw games.
- Matchup scores reproduce raw games.
- Confidence intervals reproduce raw games.
- Holdout report uses only Mega Abomasnow.
- Teacher head-to-head reports use only the frozen teacher.
- No c005–c008 file changed.
- No policy weights changed.
- No new training checkpoint exists.
- Submission decision follows the amended gates.
- Conditional artifacts are correctly present or absent.

Validator failure blocks contract `PASS`.

---

## 14. Recalibrated RL feasibility

Set:

```text
RL_FEASIBILITY_RECALIBRATED = PROVEN
```

only when a saved RL checkpoint:

- clearly improves over B0;
- passes teacher non-inferiority;
- shows reproducible strategic improvement; and
- has no major regression.

Set:

```text
RL_FEASIBILITY_RECALIBRATED = INCONCLUSIVE
```

when:

- a saved RL checkpoint clearly improves over B0; but
- remains below teacher or has unresolved uncertainty.

Set:

```text
RL_FEASIBILITY_RECALIBRATED = REJECTED
```

when:

- no saved RL checkpoint improves over B0 under corrected evidence; or
- every RL checkpoint materially degrades B0.

This decision applies to the c008 PPO setup, not to all possible RL algorithms.

---

## 15. Next-step rule

Set:

```text
NEXT_STEP = REDESIGN_TEACHER_ANCHORED_RL
```

only when:

- RL improves over B0 across corrected evidence;
- at least two seeds or two independent confirmation batches show the signal;
- the best checkpoint is not catastrophically below teacher;
- one clear c008 algorithmic blocker can be addressed.

Examples of valid blocker:

- excessive replay-anchor strength
- weak reference-KL target
- poor early-game value estimates
- insufficient low-anchor training phase

Set:

```text
NEXT_STEP = FIXED_DECK_SELECTIVE_SEARCH
```

when:

- corrected evidence shows no meaningful RL improvement over B0; or
- RL remains severely below teacher despite some weak signal;
- teacher plus value/search has higher expected value than another PPO run.

Set:

```text
NEXT_STEP = BEGIN_DECK_PIPELINE
```

only when agent-only fixed-deck work is judged to have reached diminishing returns and the user-approved roadmap gate is met.

Do not choose the deck pipeline merely because c008 had an evaluation bug.

---

## 16. Amended submission gate

Set:

```text
SUBMISSION_D_AMENDED = SUBMIT
```

only when an already-trained checkpoint:

- passes reliability.
- passes teacher non-inferiority.
- shows reproducible improvement over teacher under corrected evidence.
- has no major regression.
- uses the exact frozen Dragapult deck.
- passes package validation.

Otherwise:

```text
SUBMISSION_D_AMENDED = DO_NOT_SUBMIT
```

No retraining is allowed before this decision.

---

## 17. Conditional package and Kaggle workflow

A package may be built only for a qualifying already-trained checkpoint.

Use:

```text
submission_D_amended_rl.tar.gz
```

Validate:

- exact frozen deck
- checkpoint SHA-256
- archive SHA-256
- clean extraction
- required `cg/` structure
- zero invalid actions/errors/timeouts
- latency and size
- no optimizer/training artifacts

When and only when:

```text
SUBMISSION_D_AMENDED = SUBMIT
```

Claude Code is explicitly authorized and required to upload.

Use description:

```text
c009 amended c008: <candidate_id> <final_commit_short_sha>
```

Retrieve:

- submission reference
- status history
- public score snapshot
- current teacher submission `54948560`
- teacher-versus-RL comparison
- promotion decision

Poll every 30 seconds for at most 20 attempts.

If authorized upload fails externally, set contract `PARTIAL`.

When `DO_NOT_SUBMIT`, record:

```text
KAGGLE_UPLOAD = SKIPPED_BY_GATE
PROMOTION_DECISION = NO_RL_SUBMISSION
```

---

## 18. Mandatory acceptance criteria

### AC-01 — Dependency and immutability verification

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

Pass when c005–c008 hashes match and no earlier contract file changes.

### AC-02 — c008 defect reproduction

Evidence:

```text
results/artifacts/c008_defect_reproduction.json
results/artifacts/c008_invalid_artifacts.md
results/test_logs/c008_defect_reproduction.txt
```

Pass when the unordered identity bug is reproduced and affected c008 conclusions are enumerated.

### AC-03 — Corrected identity-safe evaluator

Evidence:

```text
results/artifacts/evaluator_identity_protocol.json
results/test_logs/evaluator_identity_tests.txt
```

Pass when reversed/out-of-order completion tests preserve exact job identity.

### AC-04 — Frozen checkpoint registry

Evidence:

```text
results/artifacts/candidate_checkpoint_registry.json
results/test_logs/checkpoint_registry_validation.txt
```

Pass when B0 and all required R1/R2 selected checkpoints are hashed and classified.

### AC-05 — Corrected raw-game evidence

Evidence:

```text
results/artifacts/corrected_games.jsonl.gz
results/artifacts/corrected_game_manifest.json
results/test_logs/corrected_evaluation_execution.txt
```

Pass when every executed job has complete identity and all count assertions pass.

### AC-06 — Untouched V2-A baseline evaluation

Evidence:

```text
results/artifacts/v2a_baseline_evaluation.json
```

Pass when B0 receives the registered teacher and strategic evaluation.

### AC-07 — Per-seed R1/R2 checkpoint evaluation

Evidence:

```text
results/artifacts/per_seed_checkpoint_evaluation.json
results/artifacts/checkpoint_screening.csv
results/test_logs/checkpoint_screening.txt
```

Pass when every required selected R1/R2 checkpoint receives Phase A and every advancing checkpoint receives Phase B.

### AC-08 — Corrected teacher non-inferiority

Evidence:

```text
results/artifacts/amended_teacher_noninferiority.json
results/test_logs/amended_teacher_execution.txt
```

Pass when the rule is applied to all advancing candidates.

### AC-09 — Corrected strategic and held-out analysis

Evidence:

```text
results/artifacts/amended_matchup_matrix.csv
results/artifacts/amended_pairwise_intervals.json
results/artifacts/amended_global_ranking.json
results/artifacts/amended_holdout_report.json
results/artifacts/amended_improvement_report.json
results/artifacts/amended_regression_report.json
results/test_logs/amended_strategic_execution.txt
```

Pass when every aggregate reproduces corrected raw games exactly.

### AC-10 — RL improvement over initialization decision

Evidence:

```text
results/artifacts/rl_vs_initialization.json
results/artifacts/RL_IMPROVEMENT_OVER_INITIALIZATION.md
```

Pass when `YES`, `NO`, or `INCONCLUSIVE` follows the registered rule.

### AC-11 — Best saved checkpoint and recalibrated feasibility

Evidence:

```text
results/artifacts/amended_checkpoint_selection.json
results/artifacts/RL_FEASIBILITY_RECALIBRATED.md
```

Pass when best checkpoint and feasibility decisions follow corrected evidence.

### AC-12 — Content-aware evidence validation

Evidence:

```text
results/artifacts/evidence_validation.json
results/test_logs/evidence_validation.txt
```

Pass when all content checks pass. File existence alone is insufficient.

### AC-13 — Amended submission decision and package

Evidence:

```text
results/artifacts/SUBMISSION_D_AMENDED_DECISION.md
results/artifacts/submission_D_amended_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/test_logs/submission_D_amended_smoke.txt
```

When qualified, also:

```text
results/artifacts/submission_D_amended_rl.tar.gz
```

Pass when the gate is applied correctly.

### AC-14 — Conditional Kaggle evidence and promotion decision

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

When no upload occurs, record `SKIPPED_BY_GATE`.

### AC-15 — Next-step decision

Evidence:

```text
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
```

Pass when exactly one next step and one highest-leverage blocker are stated.

### AC-16 — Git and source integrity

Evidence:

```text
results/GIT_REPORT.md
results/artifacts/c009.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

Pass when c009 repair code is committed, earlier contracts remain immutable, and no model/checkpoint is altered.

---

## 19. Required results structure

```text
contracts/c009_amendment_c008/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── dependency_verification.txt
│   ├── c008_defect_reproduction.txt
│   ├── evaluator_identity_tests.txt
│   ├── checkpoint_registry_validation.txt
│   ├── corrected_evaluation_execution.txt
│   ├── checkpoint_screening.txt
│   ├── amended_teacher_execution.txt
│   ├── amended_strategic_execution.txt
│   ├── evidence_validation.txt
│   ├── submission_D_amended_smoke.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── dependency_verification.json
│   ├── immutability_verification.json
│   ├── c008_defect_reproduction.json
│   ├── c008_invalid_artifacts.md
│   ├── evaluator_identity_protocol.json
│   ├── candidate_checkpoint_registry.json
│   ├── corrected_games.jsonl.gz
│   ├── corrected_game_manifest.json
│   ├── checkpoint_screening.csv
│   ├── v2a_baseline_evaluation.json
│   ├── per_seed_checkpoint_evaluation.json
│   ├── amended_teacher_noninferiority.json
│   ├── amended_matchup_matrix.csv
│   ├── amended_pairwise_intervals.json
│   ├── amended_global_ranking.json
│   ├── amended_holdout_report.json
│   ├── amended_improvement_report.json
│   ├── amended_regression_report.json
│   ├── rl_vs_initialization.json
│   ├── RL_IMPROVEMENT_OVER_INITIALIZATION.md
│   ├── amended_checkpoint_selection.json
│   ├── RL_FEASIBILITY_RECALIBRATED.md
│   ├── evidence_validation.json
│   ├── SUBMISSION_D_AMENDED_DECISION.md
│   ├── submission_D_amended_rl.tar.gz
│   ├── submission_D_amended_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_rl_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── NEXT_STEP.md
│   ├── next_step.json
│   ├── c009.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
└── failures/
```

Conditional artifacts may be absent only where explicitly allowed.

---

## 20. Required summary

`SUMMARY.md` must state:

- c008 defects reproduced.
- c008 artifacts invalidated.
- Candidate checkpoints and hashes.
- B0 result.
- Each R1/R2 seed result.
- Corrected best R1/R2 checkpoint.
- Corrected teacher head-to-head.
- Corrected strategic and held-out results.
- RL improvement over initialization.
- Teacher non-inferiority.
- Recalibrated RL feasibility.
- Submission decision.
- Kaggle status when applicable.
- Next step.
- Highest-leverage blocker.
- Known limitations.

`STATUS.json`:

```json
{
  "contract": "c009_amendment_c008",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "c008_evaluation": "REPAIRED",
  "rl_improved_over_initialization": "NO",
  "best_saved_checkpoint": "V2A_BASELINE",
  "teacher_noninferiority": "FAIL",
  "rl_feasibility_recalibrated": "REJECTED",
  "submission_D_amended": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "promotion_decision": "NO_RL_SUBMISSION",
  "next_step": "FIXED_DECK_SELECTIVE_SEARCH",
  "highest_leverage_blocker": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

A `PASS` requires valid repaired evidence, not a positive RL result.

---

## 21. Git requirements

Create from the accepted c008 final HEAD.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c009:
```

Recommended commits:

```text
c009: add identity-safe c008 evaluation repair
c009: evaluate baseline and saved RL checkpoints
c009: add amended evidence validation and decisions
```

Do not:

- Push.
- Force-push.
- Rebase shared history.
- Amend user commits.
- Modify c005–c008.
- Modify checkpoint files.
- Create new trained weights.
- Commit credentials.
- Lower thresholds after results.

---

## 22. Bounded compute

This is an evaluation-only amendment.

Target total evaluation budget:

```text
2,000–5,000 games
```

The budget may exceed 5,000 only when a saved checkpoint remains statistically plausible for c008’s teacher non-inferiority or submission gate.

Do not rerun training.

Record exact game totals.

---

## 23. Stop and status rules

Set `BLOCKED` when:

- Required checkpoints are missing.
- Checkpoint hashes cannot be verified.
- cabt runtime is unavailable.
- Frozen teacher/deck is unavailable.
- User changes overlap and cannot be preserved.

Set `PARTIAL` when:

- Identity-safe evaluation is incomplete.
- B0 is not evaluated.
- Required R1/R2 checkpoints are skipped.
- Raw games do not reproduce aggregates.
- Content-aware validation fails.
- An eligible package cannot be validated.
- Authorized Kaggle upload fails externally.
- Earlier contracts are modified.

Do not mark `PASS` because result files merely exist.

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
c008 defect reproduced:
c008 artifacts invalidated:
Untouched V2-A result:
R0 checkpoints evaluated:
R1 checkpoints evaluated:
R2 checkpoints evaluated:
Best corrected R1:
Best corrected R2:
Best saved checkpoint:
RL improved over initialization:
Teacher non-inferiority:
Corrected strategic result:
Held-out Abomasnow result:
Major regressions:
RL feasibility recalibrated:
Submission D amended decision:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Promotion decision:
Next step:
Highest-leverage blocker:
Total evaluation games:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria are executed and the content-aware validator passes.
