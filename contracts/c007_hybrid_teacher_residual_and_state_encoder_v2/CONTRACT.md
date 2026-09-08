# c007 — Hybrid Teacher Residual and State Encoder v2

## 1. Winning objective

Build the first learned agent that is safe by construction because the frozen Dragapult teacher remains the runtime backbone.

c007 must not attempt another unrestricted neural replacement of the teacher.

It must:

1. Build a materially richer state/action representation.
2. Instrument a behavior-equivalent offline copy of the teacher and expose its planning state as privileged labels.
3. Expand the ordered strategic dataset.
4. Train a compact advisory model using the new representation.
5. Admit at most three narrow residual intervention contexts.
6. Generate outcome-backed improvement labels for those contexts.
7. Build a hybrid that defaults to the teacher and overrides only under strict gates.
8. Prove local non-inferiority and at least one reproducible improvement.
9. Automatically submit the qualifying hybrid to Kaggle and retrieve its result.

Required final decisions:

```text
STATE_ENCODER_V2 = ACCEPT | REJECT
TEACHER_INSTRUMENTATION = VALID | INVALID
RESIDUAL_CONTEXTS = [ ... ]
BEST_HYBRID = H2_RESIDUAL | NONE
SUBMISSION_C = SUBMIT | DO_NOT_SUBMIT
PROMOTION_DECISION = PROMOTE_HYBRID | KEEP_TEACHER | WAIT_FOR_MORE_GAMES | NO_HYBRID_SUBMISSION
RESIDUAL_RL_READINESS = READY | NOT_READY
```

A negative competitive result may still produce contract `PASS` when every experiment and gate is completed honestly.

---

## 2. Strategic diagnosis from c006

c006 proved that the first pure students were reliable but strategically weak:

- Offline teacher agreement was roughly 72–73%.
- Student score against teacher was roughly 12–17%.
- Strategic-gauntlet strength collapsed.
- Neither student qualified for submission.

The working diagnosis is:

```text
lossy dynamic-state representation
+ averaged zones
+ weak card semantics
+ independent option scoring
+ incomplete previous-action identity
+ limited data
+ behavioral-cloning distribution shift
```

The following are not considered settled:

- teacher memory is unimportant;
- exact-observation uniqueness proves observability sufficiency;
- DAgger alone fixes the problem;
- a pure neural replacement is required before learned improvement is useful.

The strategic pivot is:

```text
frozen teacher
+ state encoder v2
+ learned advisory model
+ narrow evidence-backed residual overrides
```

---

## 3. Dependencies and immutability

Required accepted artifacts/source:

```text
c001–c006 implementation source
c005 frozen Dragapult teacher and deck
c005 teacher dataset
c006 ordered dataset, checkpoints, evaluation, and Kaggle tooling
c004–c006 gauntlet infrastructure
```

Before work:

- record c005/c006 final Git commits;
- verify teacher, deck, dataset, checkpoint, and submission hashes;
- verify teacher submission ref `54948560`;
- preserve all user changes.

Do not modify any file under:

```text
contracts/c005_teacher_import_submission_and_dataset/
contracts/c006_distilled_policy_baseline/
```

Do not modify the frozen teacher or deck in place. Instrumentation must use a copied source tree controlled by c007.

If required hashes do not match, set `BLOCKED`.

---

## 4. Scope

Expected implementation:

- state encoder v2;
- exact zone/entity representation;
- deterministic legal-card semantic features;
- legal-option set encoder with cross-option interactions;
- actual previous-action/history representation;
- behavior-equivalent teacher instrumentation;
- privileged teacher-plan labels;
- expanded strategic dataset;
- targeted residual-context selection;
- branch-and-rollout or controlled-policy improvement labels;
- H0/H1/H2 hybrids;
- non-inferiority and improvement evaluation;
- package validation;
- mandatory gated Kaggle upload and retrieval;
- evidence and Git reports.

Non-goals:

- unrestricted PPO/policy-gradient RL;
- full MCTS at every decision;
- deck changes;
- broad architecture search;
- LLM action labels;
- card-effect execution DSL;
- repeated DAgger loops;
- unrelated refactoring.

---

## 5. Pre-registered runtime agents

### T — Frozen teacher

Exact c005 Dragapult teacher and exact frozen deck.

### H0 — Teacher parity wrapper

Teacher plus c007 observation/instrumentation/logging wrappers.

```text
action = frozen_teacher_action
```

H0 never overrides.

### H1 — Teacher plus learned monitor

Teacher plus state encoder v2 and advisory heads.

```text
action = frozen_teacher_action
```

H1 never overrides. It records shadow recommendations, confidence, in-distribution score, and estimated residual advantage.

### H2 — Gated residual hybrid

Default:

```text
action = frozen_teacher_action
```

Override only when all are true:

- semantic context is pre-approved;
- decoder form is fully supported;
- proposed action is legal;
- state is in-distribution;
- confidence exceeds registered threshold;
- estimated advantage lower bound exceeds registered threshold;
- per-context and per-game override budgets remain;
- no safety veto fires.

Every override, abstention, and veto must be logged.

---

## 6. Experiment registration

Before dependent experiments create:

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
```

Freeze:

- dependency hashes;
- teacher/deck hashes;
- data sources/splits;
- state encoder schema;
- card semantic schema;
- instrumentation fields;
- model architecture and parameter ceiling;
- three training seeds;
- residual-context candidates and admission rule;
- counterfactual protocol;
- confidence, OOD, and advantage thresholds;
- override budgets;
- evaluation field;
- non-inferiority and improvement rules;
- submission rule;
- Kaggle retrieval protocol.

No post-hoc architecture or threshold may become the winner. One complete restart is allowed only after a documented implementation defect.

---

## 7. State encoder v2

### 7.1 In-play Pokémon

Represent separately:

```text
self active
self bench slot 0..N
opponent active
opponent bench slot 0..N
```

For each slot include when available:

- card ID and semantic features;
- current/max HP, damage, remaining-HP fraction;
- attached energy cards/types/count;
- attack readiness;
- retreat cost/readiness;
- tools;
- evolution stack/pre-evolution;
- appeared/evolved this turn;
- status conditions;
- known knockout range;
- slot identity and empty mask.

Do not average bench Pokémon.

### 7.2 Hand and discard

Represent exact multisets using set/multiset encoders.

Include card ID, semantic features, duplicate count, zone, and playability mask when derivable.

Do not average the hand or discard into one vector.

### 7.3 Deck/prize/game knowledge

Represent:

- known deck composition and estimated remaining counts;
- known/revealed prize information;
- prize counts and prize race;
- known searched/revealed cards;
- turn, phase, seat, usage flags, attack/end-turn availability.

Document hidden-information handling.

### 7.4 History

Include:

- previous context;
- actual previous selected option identities;
- previous card/target identities;
- recent action sequence;
- recent observation-log sequence where available;
- hidden state reset at game start.

### 7.5 Legal options

Represent every legal option separately and use a set encoder or cross-option attention so one option score may depend on the other available options.

Include option type, card/source/target identity, attack/ability identity, cardinality, context, and semantic fields.

### 7.6 Card semantics and unseen cards

For every legal card derive deterministic structured features:

- type, stage, HP, evolution relation;
- energy type, retreat, weakness/resistance;
- attack damage and energy costs;
- ability/attack/text-presence flags;
- deterministic coarse roles where derivable: draw, search, recovery, acceleration, switching, disruption, healing, damage placement/modification, evolution support, trainer subtype.

Unseen legal cards must not rely on random untrained ID embeddings. Use:

```text
semantic encoder + zero-initialized or feature-derived ID residual
```

### 7.7 Completeness audit

Compare c006 and v2. Classify observed source fields as represented directly, deterministically transformed, intentionally omitted, or unavailable. Every omission needs a strategic justification.

---

## 8. Teacher instrumentation

Create an offline copied teacher implementation. Do not edit frozen files.

Export available planning variables such as:

```text
plan_a
plan_b
planned attacker
planned target
planned supporter
bench attacker
prize inference
use_support
current/previous turn plan
damage-allocation intent
```

Use exact fields that exist. These labels may be auxiliary targets but may not be runtime inputs.

### Behavior-equivalence gate

Load frozen and instrumented teachers in isolated module namespaces and feed the same ordered observations/legal options.

Require:

- identical selected actions;
- identical exception behavior;
- no input mutation;
- no extra RNG calls affecting decisions;
- equivalent state transitions except logging.

Minimum:

```text
all replayable c005 decisions or at least 15,000 ordered decisions
plus 100 live games
```

Any action mismatch invalidates instrumentation until fixed.

### On-policy synchronization

Teacher/oracle labeling after H2 deviations is allowed only when teacher state is synchronized with the actual action/observation history. If synchronization cannot be proven for a context, that context cannot receive on-policy teacher labels.

---

## 9. Expanded v2 dataset

Generate/rebuild at least:

```text
600 completed teacher-controlled games
50,000 ordered decisions
```

Use both seats against:

- Mega Lucario;
- Mega Abomasnow;
- Iono;
- Dragapult mirror;
- any already accepted legally reusable strategic agent;
- engineering control reported separately.

Capture complete v2 state, exact legal-option set, actual history, privileged labels, outcome, latency, and lineage.

Preserve c006 test data as a historical benchmark. Create a new whole-game c007 split:

```text
70% train / 15% validation / 15% test
```

No leakage.

---

## 10. Advisory model and ablation

Train one registered model family with exactly three seeds.

Architecture:

```text
card semantic encoder
+ zone-specific set encoders
+ slot-specific board encoder
+ history encoder
+ legal-option set attention
+ teacher-action head
+ optional teacher-plan auxiliary heads
+ optional value/outcome head
```

Target size:

```text
500,000–2,000,000 parameters
hard maximum 3,000,000
```

Train:

```text
V2-A: action head only
V2-B: action head + privileged planning auxiliary heads
```

Select by validation only, then evaluate once on c007 test.

Report teacher agreement, high-impact semantic agreement, plan-label metrics, calibration, option-set sensitivity, c006-test back-evaluation, latency, and parameter count.

The model is not submitted standalone.

---

## 11. Residual-context admission

Candidate semantic contexts:

- Dragapult damage-counter allocation;
- promotion to active;
- energy attachment target;
- search/card target;
- attack versus continue setup;
- attack target;
- retreat/switch target;
- evolution target.

A context is admitted only when:

1. at least 300 c007 examples;
2. at least 200 examples with two meaningful legal choices;
3. decoder semantics fully supported;
4. teacher/oracle state synchronization valid;
5. counterfactual evaluation stable;
6. H1 calibration acceptable;
7. not primarily forced;
8. residual action does not corrupt future teacher state.

Admit at most three contexts.

If none qualify, do not build/submit H2; complete the negative result honestly.

---

## 12. Improvement-label generation

Teacher imitation alone cannot prove improvement.

### Preferred: branch-and-rollout

For captured states:

1. clone simulator state;
2. evaluate teacher action and admitted alternatives;
3. continue branches with synchronized registered policies;
4. balance seats and use registered rollout batches;
5. estimate action advantage and uncertainty.

Use only when state cloning and teacher synchronization are validated.

### Fallback: controlled policy variants

If exact branching is invalid, build narrow deterministic variants that alter only one semantic rule and evaluate them in balanced full games. Do not fabricate per-state counterfactual labels.

### Positive-label gate

An alternative becomes a residual label only when:

- estimated advantage exceeds registered minimum;
- lower confidence bound exceeds zero;
- instability is acceptable;
- no reliability defect occurs.

Ambiguous states retain the teacher action.

Target:

```text
2,000 evidence-backed residual examples
```

or all admissible examples if fewer exist.

---

## 13. Exactly one targeted on-policy iteration

After freezing the first H2 candidate:

1. run H2 against the fixed field;
2. capture overrides, near-threshold abstentions, teacher disagreements, and OOD-boundary states;
3. relabel only admitted contexts using the validated protocol;
4. retrain the residual head once;
5. freeze final H2.

Do not run repeated DAgger loops. Do not query a desynchronized teacher.

---

## 14. Runtime safety

H2 must include:

- teacher default;
- legal validation;
- context allowlist;
- OOD detector;
- confidence and advantage thresholds;
- per-context and per-game budgets;
- deterministic fallback;
- exception isolation;
- complete telemetry.

Initial maximum override budget:

```text
5 per game
```

The registered final value may be lower.

---

## 15. Local evaluation

Evaluate T, H0, H1, and H2 on the exact frozen deck.

### H0 parity

At least 200 games, both seats, fixed strategic field. H0 must preserve teacher actions and outcomes within registered wrapper overhead.

### Reliability

H1/H2: 40 games per seat against at least three strategic opponents. Zero invalid actions, attributable exceptions, and timeouts.

### H2 versus teacher

Initial:

```text
200 games per seat orientation / 400 total
```

Extend in balanced increments to 800 total when ambiguous.

Non-inferiority passes when the one-sided 95% lower bound on H2 score is:

```text
>= 0.47
```

### Strategic field

Compare T and H2 against Lucario, Abomasnow, Iono, Dragapult mirror, and any accepted additional strategic agent. Engineering control is separate.

### Reproducible improvement

Submission requires at least one:

1. one matchup at least +5 percentage points with bootstrap probability of improvement >=90%; or
2. global strength improvement with 90% bootstrap interval above zero; or
3. validated residual-context action-value improvement reproduced in a second held-out batch with no full-game regression.

### Major regression

Any matchup at least 7 percentage points below teacher with >=90% bootstrap probability blocks submission.

---

## 16. Selection and package

Set `BEST_HYBRID = H2_RESIDUAL` only when:

- instrumentation valid;
- state encoder accepted;
- at least one residual context admitted;
- reliability perfect;
- teacher non-inferiority passed;
- at least one reproducible improvement;
- no major regression;
- telemetry complete;
- package constraints pass.

Otherwise `BEST_HYBRID = NONE`.

When selected, build:

```text
submission_C_hybrid.tar.gz
```

Include exact deck, frozen teacher runtime, residual model, state encoder, safety gates, and required `cg/` files. Exclude training data, privileged labels, offline-only instrumentation, secrets, and unused checkpoints.

Validate clean extraction and at least 80 strategic games from the archive, both seats, zero reliability defects, safe P99 latency, and controlled fallback when model weights are missing/corrupt.

---

## 17. Mandatory Kaggle submission and retrieval

When `SUBMISSION_C = SUBMIT`, Claude Code is explicitly authorized and required to upload. No extra environment flag is required.

Use description:

```text
c007 Submission C: hybrid residual <final_commit_short_sha>
```

Before upload retrieve current submissions and guard against duplicate description plus recorded archive SHA-256.

Use the official Kaggle CLI equivalent of:

```bash
kaggle competitions submit pokemon-tcg-ai-battle \
  -f contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/results/artifacts/submission_C_hybrid.tar.gz \
  -m "<unique description>"
```

Retrieve and preserve raw verbose submissions CSV, submission ref, timestamp, status, scores, and raw row.

Poll every 30 seconds for at most 20 attempts. Preserve every snapshot in JSONL. Pending after the bounded window is allowed; retain the ref and exact refresh command.

Missing credentials, network rejection, or daily-limit failure must be recorded exactly and makes the contract `PARTIAL` because upload was explicitly required after the local gate.

Refresh teacher submission ref `54948560` in the same run and create a timestamped teacher/hybrid comparison. Do not declare superiority from one immature score snapshot.

---

## 18. Residual-RL readiness

Set `READY` only when:

- H2 passes local non-inferiority;
- H2 has a reproducible improvement;
- residual contexts and safety gates are stable;
- on-policy synchronization is valid;
- override telemetry defines a constrained action space;
- frozen H2 exists;
- no major regression exists.

Otherwise `NOT_READY` and name the single highest-leverage blocker.

---

## 19. Mandatory acceptance criteria

### AC-01 Dependency, immutability, baseline verification

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

### AC-02 Registered experiment

```text
results/artifacts/EXPERIMENT_REGISTRATION.md
results/artifacts/experiment_registration.json
```

### AC-03 State encoder v2 completeness

```text
results/artifacts/state_encoder_v2_schema.json
results/artifacts/state_encoder_v2_audit.md
results/artifacts/c006_vs_v2_feature_diff.json
results/test_logs/state_encoder_v2_tests.txt
```

### AC-04 Teacher instrumentation parity

```text
results/artifacts/teacher_instrumentation_manifest.json
results/artifacts/teacher_plan_label_schema.json
results/artifacts/teacher_instrumentation_parity.json
results/test_logs/teacher_instrumentation_parity.txt
```

### AC-05 Expanded ordered dataset

```text
results/artifacts/v2_dataset/
results/artifacts/v2_dataset_manifest.json
results/artifacts/v2_dataset_split_report.json
results/test_logs/v2_dataset_generation.txt
results/test_logs/v2_dataset_validation.txt
```

Pass requires at least 600 games and 50,000 decisions.

### AC-06 V2 model and auxiliary-label ablation

```text
results/artifacts/v2_training_runs.json
results/artifacts/v2_offline_evaluation.json
results/artifacts/v2_ablation.json
results/artifacts/checkpoints/
results/test_logs/v2_training.txt
results/test_logs/v2_offline_evaluation.txt
```

### AC-07 Residual-context admission

```text
results/artifacts/residual_context_candidates.json
results/artifacts/residual_context_admission.json
results/artifacts/RESIDUAL_CONTEXTS.md
```

### AC-08 Valid improvement labels

```text
results/artifacts/improvement_label_manifest.json
results/artifacts/improvement_labels.jsonl.gz
results/artifacts/counterfactual_evaluation.json
results/test_logs/improvement_label_generation.txt
```

### AC-09 One targeted on-policy iteration

```text
results/artifacts/on_policy_states.jsonl.gz
results/artifacts/on_policy_relabel_report.json
results/artifacts/final_residual_checkpoint.json
results/test_logs/on_policy_iteration.txt
```

### AC-10 H0 parity and hybrid reliability

```text
results/artifacts/h0_parity_report.json
results/artifacts/hybrid_reliability_report.json
results/artifacts/hybrid_latency_report.json
results/test_logs/h0_parity_games.txt
results/test_logs/hybrid_smoke_games.txt
```

### AC-11 Teacher non-inferiority

```text
results/artifacts/h2_teacher_games.jsonl.gz
results/artifacts/h2_teacher_noninferiority.json
results/test_logs/h2_teacher_execution.txt
```

This AC may pass even when H2 fails the competitive gate, provided the registered experiment completed.

### AC-12 Strategic improvement and regression analysis

```text
results/artifacts/hybrid_strategic_games.jsonl.gz
results/artifacts/hybrid_matchup_matrix.csv
results/artifacts/hybrid_global_ranking.json
results/artifacts/hybrid_improvement_report.json
results/artifacts/hybrid_regression_report.json
results/test_logs/hybrid_gauntlet_execution.txt
```

### AC-13 Best-hybrid and submission decisions

```text
results/artifacts/hybrid_selection.json
results/artifacts/hybrid_selection.md
results/artifacts/SUBMISSION_C_DECISION.md
```

### AC-14 Package and Kaggle evidence

```text
results/artifacts/submission_C_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_hybrid_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/submission_C_smoke.txt
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

When `SUBMIT`, also require `submission_C_hybrid.tar.gz`. When `DO_NOT_SUBMIT`, record `SKIPPED_BY_GATE`.

### AC-15 Residual-RL readiness

```text
results/artifacts/RESIDUAL_RL_READINESS.md
results/artifacts/residual_rl_readiness.json
```

### AC-16 Git and source integrity

```text
results/GIT_REPORT.md
results/artifacts/c007.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

All sixteen criteria must complete for `PASS`. A negative hybrid result can still pass.

---

## 20. Required results structure

```text
contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
├── artifacts/
└── failures/
```

All evidence named in the acceptance criteria must be present. Conditional submission files may be absent only when explicitly allowed.

---

## 21. Required status

`STATUS.json` must include:

```json
{
  "contract": "c007_hybrid_teacher_residual_and_state_encoder_v2",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "teacher_id": "...",
  "deck_id": "...",
  "state_encoder_v2": "ACCEPT",
  "teacher_instrumentation": "VALID",
  "residual_contexts": [],
  "best_hybrid": "NONE",
  "submission_C_decision": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "hybrid_public_score": null,
  "teacher_public_score_same_run": null,
  "promotion_decision": "NO_HYBRID_SUBMISSION",
  "residual_rl_readiness": "NOT_READY",
  "highest_leverage_blocker": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

`SUMMARY.md` must report representation changes, instrumentation parity, data/model results, admitted contexts, label evidence, H2 results, regressions, submission/Kaggle evidence, promotion decision, and RL readiness.

---

## 22. Git requirements

Branch:

```text
contract/c007_hybrid_teacher_residual_and_state_encoder_v2
```

Create from accepted c006 final HEAD.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin `c007:`.

Recommended commits:

```text
c007: add state encoder v2 and teacher instrumentation
c007: add residual labels and gated hybrid policy
c007: add hybrid evaluation packaging and kaggle workflow
```

Do not push, force-push, rebase shared history, amend user commits, modify c005/c006, modify the frozen teacher/deck, commit credentials, submit after a `DO_NOT_SUBMIT` gate, or lower gates after results.

---

## 23. Stop/status rules

Set `BLOCKED` when required frozen assets, cabt runtime, training dependencies, or preservable working tree are unavailable.

Set `PARTIAL` when any mandatory AC is incomplete; instrumentation parity fails; dataset minimum is missed; labels lack valid evidence; teacher state is desynchronized; evaluation is incomplete; a required gated Kaggle upload fails; or earlier contract files are modified.

Do not substitute unrestricted RL or a pure-neural submission.

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
State encoder v2:
Teacher instrumentation:
V2 dataset games:
V2 dataset decisions:
Selected representation model:
Residual contexts:
Improvement labels:
H0 parity:
H2 vs teacher:
Reproducible improvements:
Major regressions:
Best hybrid:
Submission C decision:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Hybrid public score snapshot:
Teacher public score same run:
Promotion decision:
Residual RL readiness:
Highest-leverage blocker:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria are executed and verified.
