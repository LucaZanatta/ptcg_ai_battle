# c013 — Fixed-Deck Policy Combination and Learnability

## 1. Purpose

Extract the maximum value from the existing c011/c012 policy population before spending another large PPO budget.

c012 established a stronger deployable policy by averaging compatible learned policies, but it did not:

- evaluate true online logit/probability ensembles;
- evaluate combinations involving the complementary c012 continuation policies;
- establish why the strongest weight soup is difficult to improve;
- execute the intended adaptive curriculum;
- correctly compare the frozen teacher and official opponents on identical states;
- fairly test Claude with semantically decoded actions.

c013 must answer:

1. What is the strongest deployable policy already available?
2. Are online ensembles stronger than weight soups?
3. Is direct PPO continuation from a soup limited by its averaged value head, fresh optimizer state, or the combination geometry itself?
4. Is continuing original component lineages and recombining stronger than training the soup directly?
5. Does the repaired adaptive curriculum machinery actually function in a bounded smoke test?
6. Do the frozen teacher and official opponents show measurable behavioral/policy overlap on identical visible states?
7. Can Claude Opus understand a semantically complete PTCG state/action serialization well enough to justify a later full qualification contract?

The exact c005 Dragapult deck remains frozen.

Required final decisions:

```text
COMBINATION_RESULT =
    ONLINE_ENSEMBLE_WINS
  | WEIGHT_SOUP_WINS
  | SINGLE_POLICY_WINS
  | TIED
  | INCONCLUSIVE

TRUE_BEST_AGENT =
    <candidate_id>
  | NONE

SOUP_LEARNABILITY =
    DIRECT_CONTINUATION_WORKS
  | VALUE_REFIT_WORKS
  | COMPONENT_CONTINUE_RECOMBINE_WORKS
  | MULTIPLE_WORK
  | NOT_IMPROVED
  | INCONCLUSIVE

CURRICULUM_SMOKE =
    PASS
  | FAIL
  | BLOCKED

OPPONENT_OVERLAP =
    SUPPORTED
  | PARTIALLY_SUPPORTED
  | NOT_SUPPORTED
  | INCONCLUSIVE

CLAUDE_SEMANTIC_PREFLIGHT =
    PASS
  | PARTIAL
  | FAIL
  | EXTERNAL_BLOCK

BEST_AGENT =
    <candidate_id>
  | NONE

SUBMISSION_G =
    SUBMIT
  | DO_NOT_SUBMIT

PROMOTION_DECISION =
    PROMOTE_NEW_AGENT
  | KEEP_C012_INCUMBENT
  | KEEP_TEACHER
  | WAIT_FOR_MORE_GAMES
  | NO_RL_SUBMISSION

NEXT_STEP =
    SCALE_COMBINE_AND_CONTINUE
  | RUN_REPAIRED_ADAPTIVE_CURRICULUM
  | RUN_FULL_CLAUDE_QUALIFICATION
  | REDESIGN_FIXED_DECK_AGENT
  | BEGIN_DECK_PIPELINE
```

A negative result may still produce `PASS` when all registered phases and acceptance criteria complete honestly.

---

## 2. Strategic constraints

The project sequence remains:

```text
frozen deck
→ reliable agent loop
→ strongest validated deployable policy
→ external calibration
→ deck work only after the agent-loop gate
```

c013 is agent-only.

Do not:

- mutate or search decks;
- change card counts;
- introduce a new architecture family;
- change PPO reward or action semantics;
- train on Claude labels;
- run a large adaptive-curriculum experiment;
- run mass Claude labeling;
- perform a broad ensemble-weight search;
- perform broad PPO hyperparameter tuning;
- claim online ensembles and weight soups are equivalent;
- claim teacher/opponent overlap from win rates alone.

---

## 3. Dependencies

Required:

```text
c005 frozen Dragapult teacher and deck
c009 identity-safe evaluation
c010/c011/c012 checkpoints and raw games
c011 PyTorch/CUDA PPO backend
c011/c012 source bundles
c012 SOUP_622+633 incumbent
c012 P0_711
c012 P1_822
c012 P1_833
c011 S611
c011 S622
c011 S633
```

Resolve exact IDs and SHA-256 hashes from registries.

Before work:

- record branch and HEAD;
- record final commits for c005–c012;
- verify frozen deck and teacher hashes;
- verify every candidate checkpoint;
- reproduce c012 final-panel aggregates from raw games;
- verify CUDA/PyTorch environment;
- preserve unrelated user changes.

---

## 4. Absolute immutability

Do not modify any file under:

```text
contracts/c005_teacher_import_submission_and_dataset/
contracts/c006_distilled_policy_baseline/
contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/
contracts/c008_fixed_deck_teacher_anchored_rl/
contracts/c009_amendment_c008/
contracts/c010_fixed_deck_rl_loop_v2/
contracts/c011_fixed_deck_cuda_ppo_scale/
contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/
```

Do not modify any earlier checkpoint, raw game, decision, contract, input, reference, result, or source snapshot.

All new code and evidence belong to c013-controlled paths.

---

## 5. Branch and naming

Branch:

```text
contract/c013_fixed_deck_policy_combination_and_learnability
```

Suggested source:

```text
tools/c013_candidate_registry.py
tools/c013_ensemble_policy.py
tools/c013_combination_eval.py
tools/c013_value_refit.py
tools/c013_component_continue.py
tools/c013_recombine.py
tools/c013_curriculum_smoke.py
tools/c013_overlap_analysis.py
tools/c013_semantic_serializer.py
tools/c013_claude_preflight.py
tools/c013_decide.py
tools/c013_validate_evidence.py
tests/test_c013_ensemble_math.py
tests/test_c013_combination_registry.py
tests/test_c013_value_refit.py
tests/test_c013_trainer_resume.py
tests/test_c013_curriculum_smoke.py
tests/test_c013_opponent_identical_state.py
tests/test_c013_semantic_serialization.py
tests/test_c013_source_bundle.py
```

Do not overwrite c011/c012 tools.

---

# PHASE 0 — Dependency repair and frozen candidate registry

## 6. Carry forward critical c011/c012 repairs

Before new experiments, verify or repair within c013-controlled code:

- active `numpy.random.Generator` state persistence through `bit_generator.state`;
- PyTorch CPU/CUDA RNG persistence;
- optimizer moments and step;
- entropy schedule definition/progress;
- lagged-opponent registry;
- completed-game accounting;
- hard failure when a registered evaluation returns zero scored games;
- identity-safe checkpoint-hash refresh after saving;
- median best-per-seed bootstrap logic;
- same-panel frozen-teacher evaluation.

Do not modify c011/c012.

## 7. Candidate registry

Register and hash at minimum:

```text
C012_SOUP_622_633
S611
S622
S633
P0_711
P1_822
P1_833
c011/c012 historical incumbents
```

Registry fields:

```json
{
  "candidate_id": "...",
  "candidate_type": "single|weight_soup|online_ensemble",
  "component_ids": [],
  "component_sha256": [],
  "checkpoint_path": "...",
  "checkpoint_sha256": "...",
  "architecture_id": "...",
  "trainable": true,
  "deployable": true,
  "source_contract": "...",
  "source_evidence": "..."
}
```

Freeze the registry before combination evaluation.

---

# PHASE 1 — Strongest-policy combination search

## 8. Registered combination families

No broad weight search.

### 8.1 Existing single policies

Evaluate:

```text
C012_SOUP_622_633
S611
S622
S633
P0_711
P1_822
P1_833
```

### 8.2 Online logit ensembles

Equal-weight logit averaging:

```text
S611 + S622
S611 + S633
S622 + S633
S611 + S622 + S633

C012_SOUP_622_633 + P0_711
C012_SOUP_622_633 + P1_822
C012_SOUP_622_633 + P1_833

C012_SOUP_622_633 + P0_711 + P1_822
C012_SOUP_622_633 + P0_711 + P1_833
C012_SOUP_622_633 + P0_711 + P1_822 + P1_833
```

### 8.3 Online probability ensembles

Evaluate the same registered component sets using equal probability averaging.

### 8.4 Weight soups

For architecture-identical policies only:

```text
pairwise equal arithmetic soups among:
C012_SOUP_622_633
P0_711
P1_822
P1_833

one equal four-way soup:
C012_SOUP_622_633 + P0_711 + P1_822 + P1_833
```

Do not tune weights after results.

## 9. Ensemble semantics

For every decision:

- each component receives the identical encoded visible state and legal-action mask;
- forced actions bypass ensemble scoring;
- single-select logits/probabilities are combined only over legal actions;
- sequential multi-select recomputes each component distribution after every selected item;
- value output is combined and reported separately;
- component disagreement/entropy is logged;
- action identity and checkpoint hashes are preserved.

Test that online ensembles are not treated as weight-space equivalents.

## 10. Evaluation panels

### Selection panel

Per candidate:

```text
teacher:       50 games per seat
Mega Lucario:  25 games per seat
Iono:          25 games per seat
Mega Abomasnow:25 games per seat
```

Total:

```text
250 games per candidate
```

### Confirmation panel

For top candidates:

```text
teacher:       150 games per seat
Mega Lucario:   75 games per seat
Iono:           75 games per seat
Mega Abomasnow: 75 games per seat
```

Total:

```text
750 games per candidate
```

### Untouched final panel

For:

```text
c012 incumbent
best single
best weight soup
best logit ensemble
best probability ensemble
```

Minimum:

```text
teacher:       250 games per seat
Mega Lucario:  125 games per seat
Iono:          125 games per seat
Mega Abomasnow:125 games per seat
```

Total:

```text
1,250 games per finalist
```

Evaluate frozen teacher on the exact same strategic jobs.

## 11. Combination selection

Primary metrics:

```text
teacher score
three-opponent strategic field
Abomasnow
worst-matchup score
latency
package feasibility
```

A candidate may replace c012 incumbent only when:

- teacher score is not lower;
- strategic field is not lower;
- at least one primary gain has >=90% bootstrap probability above zero;
- no major matchup regression;
- reliability passes;
- runtime/package constraints pass.

Selection priority:

1. teacher score;
2. strategic field;
3. Abomasnow;
4. worst-matchup;
5. latency;
6. fewer components;
7. earlier source checkpoint.

If an online ensemble wins but cannot satisfy package/runtime constraints, preserve it as `EVALUATION_ELITE` but do not select it as deployable `BEST_AGENT`.

---

# PHASE 2 — Soup learnability diagnosis

## 12. Common setup

Use the exact frozen c012 soup policy as common policy initialization unless Phase 1 identifies a stronger trainable weight soup before Phase 2 begins.

Freeze the Phase 2 start before training.

Use:

- exact c011 PyTorch/CUDA PPO backend;
- exact c011/c012 architecture;
- exact reward;
- exact action semantics;
- exact frozen deck;
- identical opponent population;
- identical seeds structure;
- identity-safe evaluation;
- complete trainer-state checkpoints.

Maximum combined training budget:

```text
50,000 completed games
```

Hard maximum including rollout spillover:

```text
52,000 completed games
```

## 13. Q0 — direct soup continuation control

Initialization:

```text
soup policy weights
soup value weights
fresh Adam optimizer
```

Seeds:

```text
901
```

Maximum:

```text
12,000 completed games
```

This recreates c012’s direct-continuation condition under repaired infrastructure.

## 14. Q1 — value-head recalibration

Initialization:

```text
same soup policy weights
```

Procedure:

1. Freeze the policy head/backbone according to the registered implementation.
2. Reinitialize the value head with deterministic registered seed.
3. Collect fresh rollouts from the frozen soup policy.
4. Train only the value head on actual terminal outcomes/Monte Carlo returns.
5. Validate value calibration by game phase.
6. Unfreeze all trainable parameters.
7. Continue PPO.

Seeds:

```text
902
```

Budget:

```text
value-refit collection/training: registered and reported
PPO continuation maximum: 12,000 completed games
```

Do not use GAE lambda-returns as the sole refit target.

Report:

- Brier score;
- calibration;
- AUC;
- Monte Carlo return error;
- early/mid/late-game metrics.

## 15. Q2 — preserve component lineages, then recombine

Resume S622 and S633 separately from the fullest valid available trainer states.

If full trainer state is unavailable:

- use the best reconstructable state;
- report the limitation;
- do not call it literal continuation.

Branches:

```text
Q2A = continue S622
Q2B = continue S633
```

Seeds:

```text
903
904
```

Maximum:

```text
10,000 completed games per component
```

After continuation:

- evaluate each component;
- create equal weight soup;
- create equal logit ensemble;
- create equal probability ensemble;
- evaluate all three recombinations.

No weight tuning.

## 16. Q3 — optional ensemble-to-student distillation

Run only when a true online ensemble beats every trainable single/soup candidate on the confirmation panel by:

```text
teacher gain >= 3 percentage points
or
strategic-field gain >= 3 percentage points
```

and passes runtime/package feasibility.

Procedure:

1. Freeze the ensemble.
2. Generate states from incumbent/elite/self-play trajectories.
3. Distill ensemble action distributions into one student.
4. Preserve legal masks and sequential multi-select semantics.
5. Evaluate student before PPO.
6. Optionally continue PPO within remaining total budget.

Maximum distillation/PPO training games must remain within the Phase 2 hard maximum.

If the gate does not pass, record `SKIPPED_BY_GATE`.

## 17. Learnability evaluation

Every Q candidate receives:

```text
game-zero panel
5,000-game panel
final registered panel
```

Teacher and strategic-field scores must use identity-safe balanced jobs.

Set `SOUP_LEARNABILITY` according to which registered method produces a confirmed policy better than the Phase 2 start.

No method “works” from training reward alone.

---

# PHASE 3 — Repaired adaptive-curriculum smoke test

## 18. Purpose

Validate the execution machinery only.

This phase is not a full adaptive-curriculum effectiveness experiment.

## 19. Smoke arms

Use one short control and one short adaptive branch from the same frozen start:

```text
R0 seed 1001 — unchanged population
R1 seed 1002 — adaptive elite curriculum
```

Maximum:

```text
5,000 completed games each
```

Required evaluations:

```text
game 0
game 2,500
game 5,000
```

## 20. Required curriculum behavior

The adaptive smoke must:

- produce non-zero scored games at every registered evaluation;
- refresh checkpoint hashes correctly;
- compute all progression gates;
- change curriculum stage at least once when the frozen synthetic/real gate conditions are satisfied;
- preserve curriculum history;
- exercise early-stop code;
- save/restore trainer state mid-run;
- reproduce the next opponent/seat/minibatch sequence after restore.

Use a deterministic unit/integration fixture to force at least one stage change even if real policy performance does not trigger it.

A real training stage change is desirable but not required for smoke `PASS`; the live gate calculation must execute correctly.

`CURRICULUM_SMOKE = PASS` only when all machinery works.

Do not scale to a full curriculum experiment inside c013.

---

# PHASE 4 — Correct opponent-overlap analysis

## 21. Identical-state policy panel

On a frozen visible-state benchmark, query:

```text
frozen rule teacher
Mega Lucario
Iono
Mega Abomasnow
S611
S622
S633
c012 incumbent
c013 best candidate when available
```

Every policy must receive the same visible state and legal actions where technically valid.

If an official opponent cannot act meaningfully on a state because its deck/role differs:

- classify the state as inapplicable for that policy;
- do not fabricate an action;
- analyze only valid shared decision contexts.

## 22. Semantic action comparison

Measure:

- top-1 action agreement;
- top-k overlap;
- action-type agreement;
- attack/pass/setup timing;
- target-selection agreement;
- energy/resource commitment;
- promotion behavior;
- game-phase-conditioned agreement;
- agreement on states where teacher/Lucario transfer gains were observed.

## 23. Behavioral/state fingerprints

For each policy/opponent, measure:

- game length;
- first meaningful attack;
- prize progression;
- bench/evolution development;
- energy commitment;
- hand/discard trajectories;
- target distribution;
- action-type frequencies;
- state-feature distributions;
- early/mid/late-game profiles.

Use interpretable distances and confidence intervals.

## 24. Overlap conclusion

`OPPONENT_OVERLAP = SUPPORTED` only when teacher–Lucario similarity is higher than teacher–Iono and teacher–Abomasnow under multiple registered measures, with uncertainty reported.

Do not conclude shared policy from one metric.

---

# PHASE 5 — Claude semantic preflight

## 25. Scope

This is a semantic-understanding preflight, not full teacher qualification.

Maximum:

```text
20–30 primary states
10 repeated states
```

Use Claude Code with explicit Opus request, sequentially, tools disabled, no silent fallback.

Claude labels may not train any policy.

## 26. Required semantic serialization

Every state must contain human-readable, runtime-visible information:

```text
turn and phase
player role
own hand with card names/text
public active/bench with names, HP, damage, energy, status
public discard/lost-zone information
known prize/deck information
recent public action history
legal actions
relevant rules
```

Every legal action must contain:

```json
{
  "action_id": "...",
  "action_type": "ATTACK|ATTACH_ENERGY|EVOLVE|SEARCH|ABILITY|RETREAT|PROMOTE|TARGET|MULTI_SELECT|PASS|OTHER",
  "human_description": "...",
  "card_name": "...",
  "card_text": "...",
  "source_zone": "...",
  "target_description": "...",
  "visible_preconditions": [],
  "visible_effect_summary": "..."
}
```

No raw numerical card/action IDs without semantic decoding.

Do not reveal:

- opponent hidden hand;
- unknown deck order;
- future RNG;
- eventual outcome;
- teacher/incumbent choice;
- private simulator internals.

## 27. Category coverage

The preflight must include multiple categories:

```text
setup
search
attachment
evolution
attack
target selection
promotion
multi-select
Iono failure
Abomasnow failure
```

No more than four states from one category unless insufficient valid states exist.

## 28. Claude output

Require schema-constrained JSON:

```json
{
  "state_id": "...",
  "selected_action_id": "...",
  "ranked_action_ids": ["...", "...", "..."],
  "confidence": 0.0,
  "strategic_tags": ["..."],
  "short_rationale": "..."
}
```

Validate:

- selected/ranked actions legal;
- no duplicates;
- no hidden-information dependence;
- rationale refers only to supplied semantics;
- repeated consistency;
- category coverage;
- exact model resolved.

## 29. Preflight decision

Set:

```text
CLAUDE_SEMANTIC_PREFLIGHT = PASS
```

when:

- schema-valid = 100%;
- legal-action rate = 100%;
- hidden-information violations = 0;
- top-1 repeat consistency >=80%;
- rationales demonstrate correct use of supplied card/action semantics across at least eight categories.

Set `PARTIAL` for minor correctable failures.

Set `FAIL` for systematic semantic misunderstanding, legality failure, hidden-information use, or poor repeatability.

Set `EXTERNAL_BLOCK` for authentication/model/quota/recursive-execution failure.

Do not claim teacher superiority.

---

# PHASE 6 — Final selection and conditional submission

## 30. Best-agent selection

`BEST_AGENT` may be:

- single policy;
- weight soup;
- online ensemble;
- distilled ensemble student.

A candidate replaces c012 incumbent only when:

- reliability passes;
- teacher score is not lower;
- strategic field is not lower;
- at least one primary gain has >=90% bootstrap probability above zero;
- no Iono/Abomasnow major regression;
- no major worst-matchup regression;
- runtime/package feasibility passes.

If an online ensemble is strongest but not package-feasible:

- preserve as evaluation elite;
- select the strongest package-feasible candidate separately;
- report both.

## 31. Submission gate

Set:

```text
SUBMISSION_G = SUBMIT
```

only when the package-feasible best agent:

- passes reliability;
- passes original teacher non-inferiority:

```text
one-sided 95% lower bound >= 0.47
```

- shows reproducible same-panel strategic improvement over the frozen teacher;
- has no major regression;
- uses the exact frozen deck;
- passes package validation.

Otherwise:

```text
SUBMISSION_G = DO_NOT_SUBMIT
```

## 32. Conditional Kaggle workflow

When and only when `SUBMISSION_G = SUBMIT`:

```text
submission_G_policy_combination.tar.gz
```

Description:

```text
c013 Submission G: <BEST_AGENT> fixed deck <final_commit_short_sha>
```

Claude Code is explicitly authorized and required to:

- package;
- validate;
- upload;
- retrieve submission ref;
- poll every 30 seconds for at most 20 attempts;
- record public-score snapshot;
- refresh teacher ref `54948560`;
- preserve comparison and promotion decision.

Do not expose credentials.

---

## 33. Next-step rules

Set:

```text
NEXT_STEP = SCALE_COMBINE_AND_CONTINUE
```

when combination/learnability produces a stronger agent and shows a repeatable path.

Set:

```text
NEXT_STEP = RUN_REPAIRED_ADAPTIVE_CURRICULUM
```

when curriculum smoke passes and combination/learnability does not produce a sufficient next agent.

Set:

```text
NEXT_STEP = RUN_FULL_CLAUDE_QUALIFICATION
```

when semantic preflight passes and Claude becomes the highest-value unresolved lever.

Set:

```text
NEXT_STEP = REDESIGN_FIXED_DECK_AGENT
```

when no combination or learnability method improves and curriculum/Claude routes are not promising.

Set `BEGIN_DECK_PIPELINE` only under the previously approved agent-loop gate.

State exactly one highest-leverage blocker.

---

## 34. Machine and compute profile

Target:

```text
Ubuntu 24.04 native Linux
AMD Ryzen 9 7900X
61 GiB RAM
RTX 5070, 12,227 MiB VRAM
PyTorch 2.12.1+cu130
CUDA available
```

Use:

- CUDA FP32;
- measured worker count;
- pinned memory/non-blocking transfers where beneficial;
- GPU/VRAM/CPU/RAM logging;
- games/hour and decisions/hour;
- at least 100 GiB free disk before large execution.

## 35. Compute budget

Target:

```text
combination evaluation: 5,000–12,000 games
learnability training:  <=50,000 completed games
curriculum smoke:       <=10,000 completed games
overlap analysis:       evaluation only
Claude preflight:       <=30 primary + 10 repeats
```

Hard training maximum:

```text
62,000 completed games
```

Evaluation games are separate and must be recorded.

Do not silently exceed the hard maximum.

---

## 36. Identity-safe evidence

Every training/evaluation record must preserve:

```text
job_id
candidate_id
candidate type
component IDs/hashes
checkpoint hash
opponent ID/hash
seat
replicate
requested seed
phase
deck fingerprint
```

Raw games are the source of truth.

All aggregates must reproduce exactly from raw games.

---

## 37. Mandatory Python source/debug archive

Create:

```text
results/artifacts/c013_python_source_bundle.zip
```

Include:

- every tracked Python file at final HEAD;
- every c013 Python file;
- tests;
- executed entrypoints;
- ensemble/soup implementations;
- semantic serializer;
- Claude prompt/schema;
- sanitized Claude inputs/outputs;
- dependency snapshots;
- machine/CUDA snapshots;
- git patch and commit information;
- import/entrypoint inventory;
- source-path/SHA-256 manifest;
- contract, command, inputs, references.

Exclude:

- credentials;
- virtual environments;
- caches;
- large checkpoints;
- unrelated datasets;
- hidden/private state not required for debugging.

Validate clean extraction, hashes, path safety, and credential absence.

---

## 38. Mandatory acceptance criteria

### AC-01 — Dependency and immutability verification

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

### AC-02 — Repaired continuation infrastructure

Evidence:

```text
results/artifacts/continuation_repair_report.json
results/artifacts/trainer_state_schema.json
results/test_logs/trainer_state_restore.txt
results/test_logs/budget_accounting.txt
results/test_logs/evaluation_hash_refresh.txt
results/test_logs/median_bootstrap.txt
```

### AC-03 — Frozen candidate and combination registry

Evidence:

```text
results/artifacts/candidate_registry.json
results/artifacts/combination_registry.json
results/test_logs/combination_registry.txt
```

### AC-04 — Online ensemble implementation validation

Evidence:

```text
results/artifacts/ensemble_semantics_validation.json
results/test_logs/ensemble_math.txt
results/test_logs/multiselect_ensemble.txt
```

### AC-05 — Combination selection and confirmation

Evidence:

```text
results/artifacts/combination_selection_games.jsonl.gz
results/artifacts/combination_confirmation_games.jsonl.gz
results/artifacts/combination_results.json
results/artifacts/COMBINATION_RESULT.md
results/test_logs/combination_evaluation.txt
```

### AC-06 — Untouched final combination panel

Evidence:

```text
results/artifacts/combination_final_games.jsonl.gz
results/artifacts/combination_final_matrix.csv
results/artifacts/combination_final_intervals.json
results/test_logs/combination_final_panel.txt
```

### AC-07 — Q0/Q1 learnability execution

Evidence:

```text
results/artifacts/Q0_summary.json
results/artifacts/Q1_summary.json
results/artifacts/Q0_training_games.jsonl.gz
results/artifacts/Q1_training_games.jsonl.gz
results/artifacts/value_refit_diagnostics.json
results/test_logs/Q0_training.txt
results/test_logs/Q1_value_refit.txt
```

### AC-08 — Q2 component continuation and recombination

Evidence:

```text
results/artifacts/Q2_component_registry.json
results/artifacts/Q2_training_games.jsonl.gz
results/artifacts/Q2_recombination_results.json
results/test_logs/Q2_component_continuation.txt
```

### AC-09 — Optional Q3 gate and evidence

Evidence:

```text
results/artifacts/Q3_gate.json
results/artifacts/Q3_summary.json
results/test_logs/Q3_distillation.txt
```

Record `SKIPPED_BY_GATE` when not run.

### AC-10 — Soup learnability decision

Evidence:

```text
results/artifacts/soup_learnability.json
results/artifacts/SOUP_LEARNABILITY.md
results/test_logs/learnability_evaluation.txt
```

### AC-11 — Adaptive-curriculum smoke

Evidence:

```text
results/artifacts/curriculum_smoke_registry.json
results/artifacts/curriculum_smoke_history.jsonl
results/artifacts/CURRICULUM_SMOKE.md
results/test_logs/curriculum_smoke.txt
```

### AC-12 — Correct opponent-overlap analysis

Evidence:

```text
results/artifacts/identical_state_policy_actions.jsonl.gz
results/artifacts/semantic_action_agreement.json
results/artifacts/behavioral_fingerprints.json
results/artifacts/state_distribution_overlap.json
results/artifacts/OPPONENT_OVERLAP.md
results/test_logs/opponent_overlap.txt
```

### AC-13 — Claude semantic preflight

Evidence:

```text
results/artifacts/semantic_state_schema.json
results/artifacts/claude_prompt.md
results/artifacts/claude_output_schema.json
results/artifacts/claude_preflight_inputs.jsonl.gz
results/artifacts/claude_preflight_outputs.jsonl.gz
results/artifacts/claude_semantic_validation.json
results/artifacts/CLAUDE_SEMANTIC_PREFLIGHT.md
results/test_logs/claude_semantic_preflight.txt
```

### AC-14 — Final best-agent and submission decision

Evidence:

```text
results/artifacts/best_agent_selection.json
results/artifacts/final_regression_report.json
results/artifacts/SUBMISSION_G_DECISION.md
results/artifacts/submission_G_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/test_logs/final_evaluation.txt
```

Conditional:

```text
results/artifacts/submission_G_policy_combination.tar.gz
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_agent_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

### AC-15 — Content-aware validation and source bundle

Evidence:

```text
results/artifacts/evidence_validation.json
results/artifacts/c013_python_source_bundle.zip
results/artifacts/c013_python_source_manifest.json
results/test_logs/evidence_validation.txt
results/test_logs/source_bundle_validation.txt
```

### AC-16 — Next step, Git, and source integrity

Evidence:

```text
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
results/GIT_REPORT.md
results/artifacts/c013.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

A `PASS` requires content validation, not file existence.

---

## 39. Required results structure

```text
contracts/c013_fixed_deck_policy_combination_and_learnability/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── GIT_REPORT.md
├── artifacts/
│   ├── dependency_verification.json
│   ├── immutability_verification.json
│   ├── continuation_repair_report.json
│   ├── trainer_state_schema.json
│   ├── candidate_registry.json
│   ├── combination_registry.json
│   ├── ensemble_semantics_validation.json
│   ├── combination_selection_games.jsonl.gz
│   ├── combination_confirmation_games.jsonl.gz
│   ├── combination_results.json
│   ├── COMBINATION_RESULT.md
│   ├── combination_final_games.jsonl.gz
│   ├── combination_final_matrix.csv
│   ├── combination_final_intervals.json
│   ├── Q0_summary.json
│   ├── Q1_summary.json
│   ├── Q0_training_games.jsonl.gz
│   ├── Q1_training_games.jsonl.gz
│   ├── value_refit_diagnostics.json
│   ├── Q2_component_registry.json
│   ├── Q2_training_games.jsonl.gz
│   ├── Q2_recombination_results.json
│   ├── Q3_gate.json
│   ├── Q3_summary.json
│   ├── soup_learnability.json
│   ├── SOUP_LEARNABILITY.md
│   ├── curriculum_smoke_registry.json
│   ├── curriculum_smoke_history.jsonl
│   ├── CURRICULUM_SMOKE.md
│   ├── identical_state_policy_actions.jsonl.gz
│   ├── semantic_action_agreement.json
│   ├── behavioral_fingerprints.json
│   ├── state_distribution_overlap.json
│   ├── OPPONENT_OVERLAP.md
│   ├── semantic_state_schema.json
│   ├── claude_prompt.md
│   ├── claude_output_schema.json
│   ├── claude_preflight_inputs.jsonl.gz
│   ├── claude_preflight_outputs.jsonl.gz
│   ├── claude_semantic_validation.json
│   ├── CLAUDE_SEMANTIC_PREFLIGHT.md
│   ├── best_agent_selection.json
│   ├── final_regression_report.json
│   ├── SUBMISSION_G_DECISION.md
│   ├── submission_G_policy_combination.tar.gz
│   ├── submission_G_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_agent_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── evidence_validation.json
│   ├── c013_python_source_bundle.zip
│   ├── c013_python_source_manifest.json
│   ├── NEXT_STEP.md
│   ├── next_step.json
│   ├── c013.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
├── test_logs/
│   ├── dependency_verification.txt
│   ├── trainer_state_restore.txt
│   ├── budget_accounting.txt
│   ├── evaluation_hash_refresh.txt
│   ├── median_bootstrap.txt
│   ├── combination_registry.txt
│   ├── ensemble_math.txt
│   ├── multiselect_ensemble.txt
│   ├── combination_evaluation.txt
│   ├── combination_final_panel.txt
│   ├── Q0_training.txt
│   ├── Q1_value_refit.txt
│   ├── Q2_component_continuation.txt
│   ├── Q3_distillation.txt
│   ├── learnability_evaluation.txt
│   ├── curriculum_smoke.txt
│   ├── opponent_overlap.txt
│   ├── claude_semantic_preflight.txt
│   ├── final_evaluation.txt
│   ├── evidence_validation.txt
│   ├── source_bundle_validation.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
└── failures/
```

Conditional artifacts may be absent only when explicitly allowed and validated.

---

## 40. Required summary and status

`SUMMARY.md` must state:

- dependency and checkpoint hashes;
- c011/c012 repairs applied;
- registered candidates/combinations;
- best single, soup, logit ensemble, and probability ensemble;
- untouched final-panel results;
- Q0/Q1/Q2/Q3 outcomes;
- value-refit diagnostics;
- soup-learnability decision;
- curriculum-smoke result;
- opponent-overlap result;
- Claude semantic-preflight result;
- best package-feasible agent;
- best evaluation-only elite;
- teacher/field/Iono/Abomasnow results;
- submission decision;
- Kaggle evidence when applicable;
- next step;
- highest-leverage blocker;
- training/evaluation/Claude totals;
- known limitations.

`STATUS.json` schema:

```json
{
  "contract": "c013_fixed_deck_policy_combination_and_learnability",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "combination_result": "ONLINE_ENSEMBLE_WINS",
  "true_best_agent": "...",
  "soup_learnability": "VALUE_REFIT_WORKS",
  "curriculum_smoke": "PASS",
  "opponent_overlap": "PARTIALLY_SUPPORTED",
  "claude_semantic_preflight": "PASS",
  "best_agent": "...",
  "submission_G": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "promotion_decision": "PROMOTE_NEW_AGENT",
  "next_step": "SCALE_COMBINE_AND_CONTINUE",
  "highest_leverage_blocker": "...",
  "training_games": 0,
  "evaluation_games": 0,
  "claude_primary_labels": 0,
  "claude_repeat_labels": 0,
  "blocking_issues": [],
  "known_limitations": []
}
```

Values shown are examples, not predetermined outcomes.

---

## 41. Git requirements

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c013:
```

Recommended commits:

```text
c013: add policy-combination evaluation
c013: diagnose soup learnability
c013: validate curriculum smoke and overlap
c013: add semantic claude preflight
c013: finalize best agent and decisions
```

Do not:

- push;
- force-push;
- rebase shared history;
- amend user commits;
- modify c005–c012;
- commit credentials;
- alter gates after results.

---

## 42. Stop and status rules

Set `BLOCKED` when:

- required checkpoint/deck/teacher is missing;
- CUDA backend cannot be reproduced;
- candidate hashes cannot be verified;
- simulator is unavailable;
- user changes overlap and cannot be preserved.

Set `PARTIAL` when:

- required combination families are skipped;
- Q0/Q1/Q2 mandatory work is incomplete;
- curriculum smoke fails but is reported as pass;
- overlap analysis omits the rule teacher or official agents;
- Claude serialization omits semantic card/action information;
- identity-safe evaluation fails;
- raw games do not reproduce aggregates;
- training hard maximum is exceeded;
- content-aware validation fails;
- earlier contracts are modified;
- required Kaggle upload fails externally.

Claude external block may be an allowed terminal outcome only when explicitly recorded and all non-Claude mandatory phases pass.

Do not claim `PASS` because expected files exist.

---

## 43. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Frozen deck fingerprint:
Candidate registry:
Best single:
Best weight soup:
Best logit ensemble:
Best probability ensemble:
Combination result:
True best agent:
Package-feasible best agent:
Q0 result:
Q1 value-refit result:
Q2 component-recombine result:
Q3 distillation:
Soup learnability:
Curriculum smoke:
Opponent overlap:
Claude model:
Claude semantic preflight:
Teacher score:
Strategic-field score:
Iono score:
Abomasnow score:
Major regressions:
Training games:
Evaluation games:
Claude primary labels:
Claude repeated labels:
Submission G:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Promotion decision:
Next step:
Highest-leverage blocker:
Python source bundle:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria execute and content-aware validation passes.
