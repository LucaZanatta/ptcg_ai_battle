# c012 — Fixed-Deck Self-Play Curriculum and Claude Teacher Qualification

## 1. Purpose

Run one staged, overnight fixed-deck research program that:

1. Repairs the remaining c011 continuation/evaluation defects.
2. Confirms all promising c011 checkpoints and freezes the real incumbent.
3. Analyzes behavioral and state-distribution overlap among the frozen teacher, official opponents, and elite learned policies.
4. Runs a controlled adaptive elite self-play curriculum experiment against an unchanged-population PPO control.
5. Builds a frozen hard-state benchmark.
6. Qualifies Claude Opus, accessed through Claude Code, as an offline teacher, specialist, or adjudicator.
7. Does **not** train on Claude labels in this contract.

The exact c005 Dragapult deck remains frozen for all training, evaluation, analysis, and any submission package.

The primary training question is:

> Does an adaptive elite population self-play curriculum improve the strongest confirmed fixed-deck agent more broadly than ordinary continuation, without causing matchup forgetting?

The independent teacher question is:

> Can Claude Opus produce legal, hidden-information-safe, repeatable, and objectively useful labels on difficult PTCG states?

Required final decisions:

```text
C011_REPAIR =
    COMPLETE
  | PARTIAL
  | BLOCKED

TRUE_INCUMBENT =
    <candidate_id>
  | NONE

OPPONENT_OVERLAP =
    SUPPORTED
  | PARTIALLY_SUPPORTED
  | NOT_SUPPORTED
  | INCONCLUSIVE

CURRICULUM_RESULT =
    ADAPTIVE_WINS
  | CONTROL_WINS
  | TIED
  | INCONCLUSIVE

SELF_PLAY_LOOP =
    EXTENDED
  | NOT_EXTENDED
  | INCONCLUSIVE

CLAUDE_BRANCHING =
    VALID
  | INVALID
  | INCONCLUSIVE

CLAUDE_TEACHER_STATUS =
    QUALIFIED_GENERAL_TEACHER
  | QUALIFIED_SPECIALIST
  | QUALIFIED_ADJUDICATOR
  | PROMISING_UNVALIDATED
  | INCONCLUSIVE
  | REJECTED
  | EXTERNAL_BLOCK

BEST_AGENT =
    TRUE_INCUMBENT
  | P0_<seed>_<checkpoint>
  | P1_<seed>_<checkpoint>
  | ENSEMBLE_<id>
  | SOUP_<id>
  | NONE

SUBMISSION_F =
    SUBMIT
  | DO_NOT_SUBMIT

PROMOTION_DECISION =
    PROMOTE_NEW_AGENT
  | KEEP_TRUE_INCUMBENT
  | KEEP_TEACHER
  | WAIT_FOR_MORE_GAMES
  | NO_RL_SUBMISSION

NEXT_STEP =
    SCALE_ADAPTIVE_SELF_PLAY
  | RUN_CLAUDE_CONTROLLED_PILOT
  | INTEGRATE_CLAUDE_TEACHER
  | REDESIGN_FIXED_DECK_AGENT
  | BEGIN_DECK_PIPELINE
```

A negative result may still produce contract `PASS` when every registered phase and acceptance criterion completes honestly.

---

## 2. Strategic constraints

The project sequence remains:

```text
frozen Dragapult deck
→ dependable fixed-deck agent loop
→ stronger validated agent
→ external calibration
→ deck work only after the agent-loop gate
```

Do not begin deck optimization in c012.

Claude labels may be generated and qualified, but may not be used to update policy weights in c012.

The sole new training variable is the opponent curriculum.

Do not simultaneously change:

- PPO mathematics
- reward
- policy architecture
- value architecture
- action semantics
- deck
- teacher-loss objective
- Claude supervision

---

## 3. Dependencies

Required accepted evidence and artifacts:

```text
c005 frozen Dragapult teacher and exact deck
c007 selected V2-A checkpoint
c008/c009 PPO and identity-safe evaluation infrastructure
c010 elite checkpoints and incumbent evidence
c011 PyTorch/CUDA PPO backend
c011 saved checkpoints:
    S611
    S622
    S633
c011 raw training/evaluation records
c011 source bundle
```

Expected c011 confirmed policy evidence:

```text
S633 teacher score approximately 33.50%
S622 strategic field approximately 37.67%
S611 complementary Abomasnow strength
```

Resolve every identity and checkpoint hash from c011 registries. Do not infer from filename alone.

Before any edit or execution:

- Record branch and HEAD.
- Record final commits for c005–c011.
- Verify dependency hashes.
- Verify c005 deck fingerprint.
- Verify teacher hash.
- Verify all c011 candidate checkpoint hashes.
- Verify c011 raw final games reproduce the recorded final matrix.
- Record machine/CUDA profile.
- Preserve unrelated user changes.

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
```

Do not modify:

- frozen deck
- frozen teacher
- V2-A
- c010/c011 checkpoints
- c011 raw games
- c011 decisions
- earlier source snapshots

All new source, tests, checkpoints, prompts, Claude inputs/outputs, registries, raw games, and decisions belong to c012-controlled paths.

---

## 5. Non-goals

Do not:

- search or mutate decks
- change card counts
- introduce a new policy architecture family
- introduce a new value architecture family
- use MCTS or selective search
- train on Claude labels
- use teacher BC replay
- use KL optimization
- use reward shaping
- run random-initialized RL
- perform broad PPO hyperparameter sweeps
- use pure 100% mirror self-play
- assume teacher/Lucario policy overlap before analysis
- silently downgrade Claude model
- expose credentials
- lower thresholds after results
- promote the latest checkpoint merely because it is newer
- claim Claude superiority from explanations or agreement alone

---

## 6. Branch and naming

Branch:

```text
contract/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification
```

Suggested source:

```text
tools/c012_repair_c011.py
tools/c012_confirm_checkpoints.py
tools/c012_ensemble_eval.py
tools/c012_overlap_analysis.py
tools/c012_curriculum_registry.py
tools/c012_train_population.py
tools/c012_eval.py
tools/c012_hard_state_extract.py
tools/c012_claude_label.py
tools/c012_branching_validate.py
tools/c012_claude_qualify.py
tools/c012_decide.py
tools/c012_validate_evidence.py
tests/test_c012_rng_restore.py
tests/test_c012_budget_accounting.py
tests/test_c012_early_stopping.py
tests/test_c012_scale_bootstrap.py
tests/test_c012_identity_safe_eval.py
tests/test_c012_curriculum_lock.py
tests/test_c012_claude_schema.py
tests/test_c012_hidden_information.py
tests/test_c012_source_bundle.py
```

Do not overwrite c011 source.

---

# PHASE 0 — Repair c011 and freeze the true incumbent

## 7. Active RNG and trainer-state repair

The active `numpy.random.Generator` state used by training must be saved and restored through:

```python
rng.bit_generator.state
```

Do not substitute the legacy global NumPy RNG state.

The resumable trainer state must contain:

```text
policy weights
value weights
Adam optimizer moments
optimizer step
training game count
trainable decision count
entropy schedule definition
entropy schedule progress
active NumPy Generator type and state
PyTorch CPU RNG state
PyTorch CUDA RNG state
Python random state when used
lagged opponent registry and hashes
current curriculum state
branch checkpoint registry
```

Add a true continuation test:

1. Run N updates.
2. Save state.
3. Continue M updates.
4. Separately restore after N.
5. Continue the same M updates.
6. Verify matching opponent draws, seats, requested seeds, minibatch permutations, losses, and parameters within registered tolerance.

A test using precomputed minibatch orders is insufficient.

## 8. Completed-game budget accounting

Training budgets count every completed game, including games containing only forced decisions.

Track separately:

```text
completed_games
games_with_trainable_decisions
trainable_decisions
```

No arm may exceed its registered completed-game maximum except for one unavoidable already-started rollout, which must be reported and remain within the hard contract ceiling.

## 9. In-run early stopping

Implement actual checkpoint evaluation during training.

Registered early stopping must be able to terminate a branch before the full budget.

Do not perform all evaluation only after training completion.

Every stop decision must preserve:

```text
checkpoint
raw evaluation games
confidence calculation
registered rule triggered
timestamp/game count
```

## 10. Correct scale bootstrap

Repair c011’s scale conclusion logic to calculate the registered median best-per-seed improvement, not the maximum significance of any seed/metric.

Preserve a c011 repaired-decision report without modifying c011 artifacts.

## 11. Confirm all promising c011 checkpoints

Build a frozen c011 candidate registry containing:

- all confirmed finalists
- all unconfirmed late checkpoints
- every screen-nominated or near-nominated checkpoint
- S611/S622/S633 final policies
- c010 incumbent

Run confirmation panels for every valid unconfirmed candidate.

Minimum confirmation panel:

```text
Frozen teacher: 100 games per seat
Mega Lucario:    50 games per seat
Iono:            50 games per seat
Mega Abomasnow:  50 games per seat
```

Total:

```text
500 games per candidate
```

Both seats are mandatory.

## 12. Elite ensembles and model soups

Evaluate only cheap, registered combinations:

### Logit ensembles

At minimum:

```text
S611 + S622
S611 + S633
S622 + S633
S611 + S622 + S633
```

Use equal logit averaging first.

One additional registered weighting may use c011 final teacher/field ranks, but weights must be frozen before results.

### Weight soups

At minimum:

```text
equal arithmetic average of S611/S622/S633
pairwise arithmetic averages
```

Only valid for architecture-identical checkpoints.

Validate:

- output finiteness
- legal masking
- runtime latency
- NPZ export
- exact component hashes

No post-result weight tuning.

## 13. Freeze three objects

After corrected confirmation:

```text
TRAINING_INCUMBENT
Best single trainable checkpoint or validated weight soup.

EVALUATION_ELITE
Best deployable single policy, ensemble, or soup.

ELITE_POOL
Diverse strong single policies/soups used as fixed opponents.
```

An online logit ensemble may be `EVALUATION_ELITE` but may not be the trainable initialization unless its weights are represented by a validated soup.

Required incumbent selection priority:

1. higher teacher score
2. higher strategic field
3. higher Abomasnow score
4. lower worst-matchup risk
5. lower latency
6. earlier training game count

Promotion requires:

- reliability pass
- no major regression
- at least 90% bootstrap probability of improvement on one primary metric
- no reduction on the other primary metric

Freeze and hash all objects before Phase 1.

---

# PHASE 1 — Opponent and policy overlap analysis

## 14. Analysis population

Analyze:

```text
frozen Dragapult teacher
Mega Lucario
Iono
Mega Abomasnow
S611
S622
S633
TRAINING_INCUMBENT
EVALUATION_ELITE when applicable
historical c010/c011 incumbents
```

## 15. Required cross-play matrix

Run identity-safe balanced cross-play sufficient to estimate:

- pairwise score
- seat effect
- game length
- decision count
- reliability
- confidence intervals

Do not infer behavioral similarity from win rate alone.

## 16. Behavioral fingerprints

For each policy/opponent, preserve:

```text
mean and distribution of game length
first meaningful attack turn
prize progression by turn
active/bench damage curves
bench development
evolution timing
energy commitment
hand size
discard size
legal-action count
promotion frequency
attack frequency
target-selection distribution
multi-select frequency
forced-decision fraction
```

## 17. State-distribution overlap

Compare state distributions using stable, interpretable measures.

At minimum:

- standardized feature means/variances
- Jensen-Shannon or equivalent divergence for categorical distributions
- Wasserstein or equivalent distance for numeric features
- nearest-neighbor overlap in encoder-v2 representation
- decision-category-conditioned overlap
- early/mid/late-game overlap

Do not use a single opaque embedding score as the only evidence.

## 18. Policy agreement on identical states

On a frozen legal-state benchmark, query each eligible policy on the same visible states.

Measure:

- top-1 agreement
- top-k overlap
- action-category agreement
- confidence/entropy
- teacher/Lucario agreement conditional on decision category
- agreement in states where S633 improved
- disagreement in Iono/Abomasnow failures

## 19. Gain attribution

Using c011/c012 games, estimate where S633 or the repaired incumbent improved relative to the prior incumbent:

```text
opening setup
search
evolution
energy attachment
attack timing
target selection
promotion
multi-select
early game
midgame
late game
```

Do not claim causal attribution without evidence.

## 20. Lock curriculum hypothesis

Before Phase 2 training, write and hash-lock:

```text
opponent_overlap_report.json
OPPONENT_OVERLAP.md
curriculum_hypothesis.md
curriculum_registry.json
```

The hypothesis may be:

- supported
- partially supported
- not supported
- inconclusive

The adaptive curriculum must be fully specified before training results.

No curriculum parameter may be changed after the first Phase 2 training game.

---

# PHASE 2 — Controlled self-play curriculum

## 21. Common training setup

All Phase 2 arms start from the exact frozen `TRAINING_INCUMBENT`.

Use:

- c011 PyTorch/CUDA FP32 PPO backend
- exact c011 policy/value architecture
- exact c011 reward
- exact c011 action semantics
- exact c011 PPO hyperparameters
- exact c011 rollout/update configuration unless required for repaired continuation semantics
- exact frozen Dragapult deck
- full trainer-state checkpoints
- identity-safe evaluation
- game-zero evaluation
- balanced seats

Do not change PPO mathematics.

## 22. Arm P0 — unchanged-population control

Purpose:

> Measure ordinary additional continuation from the repaired incumbent.

Seeds:

```text
711
722
733
```

Use the exact c011 opponent mixture.

Expected baseline mixture:

```text
35% frozen teacher
20% Mega Lucario
20% Iono
15% lagged branch snapshots
10% deterministic control
```

Resolve and record the exact c011 implementation.

Maximum:

```text
30,000 completed training games per seed
```

Registered checkpoints:

```text
game 0
5,000
10,000
15,000
20,000
25,000
30,000
```

## 23. Arm P1 — adaptive elite population self-play

Purpose:

> Test whether adaptive elite population self-play improves broader generalization beyond ordinary continuation.

Seeds:

```text
811
822
833
```

Same maximum:

```text
30,000 completed training games per seed
```

Initial mixture:

```text
30% frozen teacher
17.5% Mega Lucario
17.5% Iono
15% elite/self-play pool
10% lagged branch snapshots
10% deterministic control
```

`ELITE_POOL` must contain diverse frozen policies selected in Phase 0.

The adaptive elite fraction may increase:

```text
15% → 25% → 35% → maximum 45%
```

It may decrease when regression is detected.

Mixture mass is reallocated only among registered categories according to the frozen curriculum registry.

## 24. Adaptive curriculum gates

Increase elite/self-play share only after a registered confirmation evaluation shows:

- teacher score preserved or improved relative to current branch best
- no Iono major regression
- no Abomasnow major regression
- improved elite cross-play score
- no historical-policy forgetting
- reliability pass

Decrease elite/self-play share or freeze curriculum progression after:

- confirmed Iono or Abomasnow regression
- worsening historical-policy coverage
- cycling indicator
- elite cross-play improvement without external-field improvement

Do not advance curriculum merely because game count increased.

## 25. Informative opponent sampling

Within the elite pool, prefer opponents with estimated learner score in a registered informative band.

Default band:

```text
0.25 ≤ learner score ≤ 0.75
```

Retain minimum exposure to:

- strongest elite
- oldest elite
- matchup specialists
- teacher
- Lucario
- Iono

No opponent may disappear entirely unless the registry explicitly allows it.

Preserve exact sampling probabilities and realized counts.

## 26. Historical forgetting panel

At every registered evaluation, include:

```text
frozen teacher
Mega Lucario
Iono
Mega Abomasnow
S611
S622
S633
TRAINING_INCUMBENT
at least two historical incumbents
```

The teacher must also be evaluated on the same strategic panel used for learned candidates.

## 27. Screening panel

Per registered checkpoint:

```text
teacher:          20 games per seat
Mega Lucario:     10 games per seat
Iono:             10 games per seat
Mega Abomasnow:   10 games per seat
elite pool:       5 games per seat per selected elite
historical panel: 5 games per seat per selected historical policy
```

## 28. Confirmation panel

For nominated branch-best checkpoints:

```text
teacher:          100 games per seat
Mega Lucario:      50 games per seat
Iono:              50 games per seat
Mega Abomasnow:    50 games per seat
elite/historical:  25 games per seat per policy
```

## 29. Final panel

Evaluate:

```text
TRAINING_INCUMBENT
best P0 checkpoint per seed
best P1 checkpoint per seed
best aggregate P0 candidate
best aggregate P1 candidate
frozen teacher
EVALUATION_ELITE
```

Minimum:

```text
teacher:       200 games per seat
Mega Lucario:  100 games per seat
Iono:          100 games per seat
Mega Abomasnow:100 games per seat
elite/historical cross-play: 50 games per seat per policy
```

Use the same job registry where applicable.

## 30. Curriculum score

Primary metrics:

```text
teacher score
three-opponent strategic field:
    Mega Lucario
    Iono
    Mega Abomasnow
elite cross-play score
historical coverage score
```

Do not include engineering control in strategic ranking.

Promotion composite for screening only:

```text
0.40 × teacher score
0.25 × strategic field
0.20 × elite cross-play
0.15 × historical coverage
```

Reliability and regression are disqualifying gates.

## 31. Major regression and forgetting

Major matchup regression:

```text
candidate <= baseline - 0.07
and bootstrap probability of regression >= 90%
```

Historical forgetting:

```text
candidate historical coverage <= baseline - 0.05
and bootstrap probability >= 90%
```

Cycling indicator:

- strong gain against recent elites
- simultaneous confirmed loss against older elites or external opponents

Report separately.

## 32. Curriculum decision

Set:

```text
CURRICULUM_RESULT = ADAPTIVE_WINS
```

when:

1. At least two of three P1 seeds beat the median P0 result on teacher score.
2. At least two of three beat median P0 strategic field.
3. Median P1 gain is at least:
   - +3 percentage points teacher; and
   - +3 percentage points strategic field.
4. At least one median gain has bootstrap probability above zero of at least 90%.
5. No majority P1 seed has Iono, Abomasnow, or historical-forgetting major regression.
6. Reliability passes.

Set `CONTROL_WINS` under the symmetric rule.

Set `TIED` when differences are small and uncertainty is not the reason.

Otherwise `INCONCLUSIVE`.

## 33. Self-play-loop decision

Set:

```text
SELF_PLAY_LOOP = EXTENDED
```

when the best P1 candidate:

- beats `TRAINING_INCUMBENT` on teacher score
- beats or preserves strategic field
- beats elite cross-play
- has at least 90% probability of improvement on one primary metric
- has no major regression
- passes reliability

Set `NOT_EXTENDED` when no P1 candidate improves over the incumbent and uncertainty is not the reason.

Otherwise `INCONCLUSIVE`.

---

# PHASE 3 — Hard-state benchmark extraction

## 34. Benchmark size and categories

Freeze:

```text
200–300 primary states
plus 40–60 repeated states for consistency
```

Select under registered criteria before Claude sees any state.

Categories must include:

```text
early setup
search
evolution
energy attachment
attack selection
target selection
promotion
multi-select
Iono failures
Abomasnow failures
teacher/elite disagreements
high policy entropy
poor value confidence
decisions followed by losses
rare student-generated states
```

No category may dominate more than 25% unless insufficient valid states exist.

## 35. Runtime-visible serialization

Claude receives only:

```text
own hand
public board
public discard information
public action history
known deck information
legal actions
relevant visible card text
relevant competition rules
```

Claude must not receive:

```text
opponent hidden hand
unknown deck order
future RNG
private simulator internals
eventual game result
rule-teacher action
incumbent action
other elite actions
```

Store a hidden-information audit for every serialized state.

## 36. Frozen benchmark

Create:

```text
hard_state_benchmark.jsonl.gz
hard_state_manifest.json
hard_state_hidden_information_audit.json
```

Hash-lock before Claude labeling.

---

# PHASE 4 — Claude Opus offline-teacher qualification

## 37. Claude Code preflight

Before batch labeling, run one small preflight through Claude Code.

Required:

```text
non-interactive print mode
explicit Opus model request
tools disabled
no repository modification
schema-constrained JSON
sequential execution
no silent model fallback
bounded state count
saved raw prompt and response
```

If Opus is unavailable, authentication fails, usage limits block execution, or recursive Claude Code invocation is disallowed:

```text
CLAUDE_TEACHER_STATUS = EXTERNAL_BLOCK
```

Preserve Phases 0–3 and all completed Phase 2 evidence.

External Claude failure must not invalidate a completed curriculum experiment.

## 38. Prompt protocol

Use a frozen prompt and schema.

Claude must return:

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

Constraints:

- selected action must be legal
- rankings contain only legal actions
- no duplicate actions
- confidence in [0,1]
- rationale concise
- no reference to hidden information
- no tool calls
- no code execution

Do not show teacher/incumbent choices or eventual outcome.

## 39. Repeated-label consistency

Relabel the repeated subset independently.

Measure:

- top-1 agreement
- top-3 overlap
- confidence stability
- category-specific consistency

Do not use hidden session persistence between repetitions.

## 40. Counterfactual branching validation

Before objective action adjudication, validate saved-state branching.

For a calibration subset:

1. Restore saved state.
2. Apply recorded original action.
3. Continue under registered rollout policies and matched stochastic conditions.
4. Compare with recorded continuation under known simulator stochastic limits.

Branching is `VALID` only when:

- restored visible state matches
- legal actions match
- original action reproduces expected transition distribution
- no hidden-information leakage
- candidate actions can be applied symmetrically
- paired rollout protocol is documented

If branching is invalid or unreliable:

```text
CLAUDE_BRANCHING = INVALID or INCONCLUSIVE
```

Claude may not be called objectively superior.

## 41. Action adjudication

When branching is valid, compare on disagreement states:

```text
Claude action
rule teacher action
TRAINING_INCUMBENT action
EVALUATION_ELITE action when distinct
```

Use:

- same restored state
- legal-action enforcement
- matched rollout policies
- paired seeds where possible
- multiple rollout continuations
- both relevant seats when meaningful

Preserve:

- action values
- confidence intervals
- pairwise differences
- category breakdown
- rollout defects

Agreement with the rule teacher is descriptive, not the success metric.

## 42. Claude qualification decisions

Set:

```text
CLAUDE_TEACHER_STATUS = QUALIFIED_GENERAL_TEACHER
```

only when:

- schema-valid rate = 100%
- legal-action rate = 100%
- hidden-information violations = 0
- repeated top-1 consistency >= 85%
- branching valid
- Claude action value exceeds both teacher and incumbent overall with >=90% bootstrap probability
- no major category regression
- confidence is directionally calibrated

Set:

```text
QUALIFIED_SPECIALIST
```

when Claude is objectively superior in one or more registered decision categories but not globally.

Set:

```text
QUALIFIED_ADJUDICATOR
```

when Claude reliably ranks disagreements or identifies the better action without qualifying as a general teacher.

Set:

```text
PROMISING_UNVALIDATED
```

when outputs are legal and consistent but objective branching is unavailable.

Set:

```text
INCONCLUSIVE
```

when uncertainty prevents a result.

Set:

```text
REJECTED
```

for:

- legal/schema failures
- hidden-information violations
- poor consistency
- objective underperformance

Claude labels may not update policy weights in c012 under any outcome.

---

# PHASE 5 — Final decisions and conditional submission

## 43. Best-agent selection

A new candidate may replace `TRAINING_INCUMBENT` only when:

- reliability passes
- teacher score is higher
- strategic field is not lower
- at least one primary improvement has >=90% bootstrap probability above zero
- no Iono/Abomasnow major regression
- no historical forgetting
- checkpoint/deck hashes validate

Selection priority:

1. teacher score
2. strategic field
3. elite cross-play
4. Abomasnow
5. worst-matchup risk
6. latency
7. earlier checkpoint

## 44. Submission gate

Set:

```text
SUBMISSION_F = SUBMIT
```

only when the best new agent:

- passes reliability
- passes original teacher non-inferiority:

```text
one-sided 95% lower bound >= 0.47
```

- shows reproducible same-panel strategic improvement over the frozen teacher
- has no major regression
- uses the exact frozen deck
- passes package validation

Otherwise:

```text
SUBMISSION_F = DO_NOT_SUBMIT
```

Claude qualification alone can never trigger submission.

## 45. Conditional Kaggle workflow

When and only when:

```text
SUBMISSION_F = SUBMIT
```

package:

```text
submission_F_selfplay_curriculum.tar.gz
```

Use description:

```text
c012 Submission F: <BEST_AGENT> fixed deck <final_commit_short_sha>
```

Validate:

- exact deck fingerprint
- checkpoint SHA-256
- archive SHA-256
- clean extraction
- required `cg/` structure
- zero invalid actions/errors/timeouts
- package size and latency
- no credentials
- no training-only artifacts
- duplicate guard

Claude Code is explicitly authorized and required to:

- upload to Kaggle
- retrieve submission reference
- poll every 30 seconds for at most 20 attempts
- preserve status history
- record public-score snapshot
- refresh teacher submission ref `54948560`
- compare teacher and candidate
- determine promotion

When no upload occurs:

```text
KAGGLE_UPLOAD = SKIPPED_BY_GATE
```

---

## 46. Next-step rules

Set:

```text
NEXT_STEP = SCALE_ADAPTIVE_SELF_PLAY
```

when adaptive curriculum wins and the best agent remains below teacher parity with credible learning headroom.

Set:

```text
NEXT_STEP = RUN_CLAUDE_CONTROLLED_PILOT
```

when Claude qualifies as specialist/adjudicator/general teacher and curriculum results are complete, but Claude labels have not yet been integrated.

Set:

```text
NEXT_STEP = INTEGRATE_CLAUDE_TEACHER
```

only when Claude qualifies strongly enough that the next contract should compare PPO-only continuation versus Claude-corrected continuation.

Set:

```text
NEXT_STEP = REDESIGN_FIXED_DECK_AGENT
```

when neither ordinary continuation nor adaptive curriculum extends the incumbent.

Set:

```text
NEXT_STEP = BEGIN_DECK_PIPELINE
```

only when:

- fixed-deck agent loop is validated
- best agent is reproducibly evaluable
- the user-approved roadmap gate is met
- policy-quality noise is judged low enough for deck comparison

State exactly one highest-leverage blocker.

---

## 47. Machine and CUDA profile

Target machine:

```text
OS: Ubuntu 24.04 native Linux
CPU: AMD Ryzen 9 7900X, 12 cores / 24 threads
RAM: 61 GiB
GPU: NVIDIA RTX 5070, 12,227 MiB VRAM
PyTorch: 2.12.1+cu130
CUDA available: true
```

Use:

- PyTorch CUDA FP32
- measured simulator-worker count
- pinned memory when beneficial
- non-blocking transfers
- GPU/VRAM utilization logging
- CPU/RAM logging
- games/hour and decisions/hour
- no BF16 unless separately revalidated
- at least 100 GiB free disk before full execution

Do not assume maximum GPU utilization is the objective.

---

## 48. Compute budget

### Phase 0/1 evaluation

Target:

```text
5,000–12,000 games
```

### Phase 2 training

Maximum:

```text
P0: 3 × 30,000 = 90,000 games
P1: 3 × 30,000 = 90,000 games
Total primary training maximum = 180,000 completed games
```

Hard training maximum including unavoidable rollout spillover:

```text
184,000 completed games
```

### Phase 2 evaluation

Record separately.

### Claude

Maximum primary labels:

```text
300 states
```

Maximum repeated labels:

```text
60 states
```

Sequential only.

Do not consume Claude usage beyond registered limits.

Self-play training has priority over Claude qualification.

---

## 49. Training evidence

Preserve compact metadata for every training game:

```json
{
  "arm": "P1",
  "training_seed": 811,
  "policy_checkpoint_before_game": "...",
  "opponent_category": "elite",
  "opponent_id": "...",
  "opponent_checkpoint_sha256": "...",
  "sampling_probability": 0.0,
  "curriculum_stage": 0,
  "seat": 0,
  "outcome": "win",
  "score": 1.0,
  "completed_game": true,
  "trainable_decision_count": 0,
  "forced_decision_count": 0,
  "episode_length": 0,
  "policy_entropy_mean": 0.0,
  "fallback_count": 0,
  "invalid_action_count": 0,
  "exception_count": 0,
  "timeout_count": 0
}
```

Per update preserve:

- policy/value loss
- entropy
- approximate KL
- clip fraction
- explained variance
- gradient norm
- learning rate
- completed games
- trainable games
- trainable decisions
- opponent probabilities
- realized opponent counts
- seat distribution
- curriculum changes
- elapsed time
- CUDA metrics

---

## 50. Identity-safe evaluation

Reuse and extend c009/c011 identity protocol.

Every result preserves:

```text
job_id
candidate_id
checkpoint hash
opponent ID/hash
seat
replicate
requested seed
phase
deck fingerprint
```

Required assertions:

- exact submitted/returned job set equality
- no duplicate IDs
- exact expected counts
- loaded hashes match registry
- deck matches frozen fingerprint
- aggregate reconstruction from raw games
- all defects explicit

No positional relabeling after unordered execution.

---

## 51. Mandatory Python source/debug archive

Create:

```text
results/artifacts/c012_python_source_bundle.zip
```

It must contain:

- every tracked repository Python file at final HEAD
- every c012 Python file used
- all tests
- all executed entrypoints
- prompt templates
- Claude JSON schemas
- Claude labeling scripts
- exact sanitized Claude inputs
- raw Claude outputs
- dependency snapshots
- `pip freeze`
- Python/PyTorch/CUDA/NVIDIA/CPU/RAM/OS snapshots
- git patch
- initial/final HEAD
- implementation commits
- import inventory
- entrypoint inventory
- source-path/SHA-256 manifest
- c012 contract, command, inputs, and references

Exclude:

- credentials
- `.venv`
- caches
- large checkpoints
- unrelated datasets
- hidden/private state not needed for debugging

Validate:

- clean extraction
- no path traversal
- every manifest hash
- no credential patterns
- source importability where applicable

---

## 52. Mandatory acceptance criteria

### AC-01 — Dependencies and immutability

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

### AC-02 — c011 repair

Evidence:

```text
results/artifacts/c011_repair_report.json
results/artifacts/trainer_state_schema.json
results/test_logs/rng_restore.txt
results/test_logs/trainer_state_continuation.txt
results/test_logs/budget_accounting.txt
results/test_logs/early_stopping.txt
results/test_logs/scale_bootstrap.txt
```

### AC-03 — c011 candidate confirmation

Evidence:

```text
results/artifacts/c011_candidate_registry.json
results/artifacts/c011_checkpoint_confirmation.json
results/artifacts/c011_confirmation_games.jsonl.gz
results/test_logs/c011_checkpoint_confirmation.txt
```

### AC-04 — Elite ensemble/soup evaluation

Evidence:

```text
results/artifacts/elite_combination_registry.json
results/artifacts/elite_combination_results.json
results/test_logs/elite_combination_eval.txt
```

### AC-05 — True incumbent and elite pool

Evidence:

```text
results/artifacts/frozen_incumbent_registry.json
results/artifacts/elite_pool_registry.json
results/artifacts/TRUE_INCUMBENT.md
results/test_logs/incumbent_freeze.txt
```

### AC-06 — Opponent overlap analysis

Evidence:

```text
results/artifacts/cross_play_matrix.csv
results/artifacts/behavioral_fingerprints.json
results/artifacts/state_distribution_overlap.json
results/artifacts/policy_agreement.json
results/artifacts/gain_attribution.json
results/artifacts/opponent_overlap_report.json
results/artifacts/OPPONENT_OVERLAP.md
results/test_logs/opponent_overlap_analysis.txt
```

### AC-07 — Locked curriculum registry

Evidence:

```text
results/artifacts/curriculum_hypothesis.md
results/artifacts/curriculum_registry.json
results/artifacts/curriculum_registry.sha256
results/test_logs/curriculum_lock.txt
```

### AC-08 — P0 control execution

Evidence:

```text
results/artifacts/P0_summary.json
results/artifacts/P0_training_games.jsonl.gz
results/artifacts/P0_updates.jsonl.gz
results/artifacts/P0_checkpoint_registry.json
results/test_logs/P0_training.txt
```

### AC-09 — P1 adaptive curriculum execution

Evidence:

```text
results/artifacts/P1_summary.json
results/artifacts/P1_training_games.jsonl.gz
results/artifacts/P1_updates.jsonl.gz
results/artifacts/P1_checkpoint_registry.json
results/artifacts/P1_curriculum_history.jsonl
results/test_logs/P1_training.txt
```

### AC-10 — Curriculum evaluation and decisions

Evidence:

```text
results/artifacts/curriculum_evaluation_games.jsonl.gz
results/artifacts/curriculum_final_matrix.csv
results/artifacts/curriculum_pairwise_intervals.json
results/artifacts/forgetting_report.json
results/artifacts/cycling_report.json
results/artifacts/CURRICULUM_RESULT.md
results/artifacts/SELF_PLAY_LOOP.md
results/artifacts/curriculum_decision.json
results/test_logs/curriculum_evaluation.txt
```

### AC-11 — Hard-state benchmark

Evidence:

```text
results/artifacts/hard_state_benchmark.jsonl.gz
results/artifacts/hard_state_manifest.json
results/artifacts/hard_state_hidden_information_audit.json
results/test_logs/hard_state_extraction.txt
```

### AC-12 — Claude preflight and labeling

Evidence:

```text
results/artifacts/claude_prompt.md
results/artifacts/claude_label_schema.json
results/artifacts/claude_preflight.json
results/artifacts/claude_inputs.jsonl.gz
results/artifacts/claude_outputs.jsonl.gz
results/artifacts/claude_validation.json
results/test_logs/claude_preflight.txt
results/test_logs/claude_labeling.txt
```

When externally blocked, preserve explicit error evidence.

### AC-13 — Branching and Claude qualification

Evidence:

```text
results/artifacts/branching_validation.json
results/artifacts/claude_action_adjudication.json
results/artifacts/claude_consistency.json
results/artifacts/claude_category_results.json
results/artifacts/CLAUDE_TEACHER_STATUS.md
results/artifacts/claude_teacher_decision.json
results/test_logs/branching_validation.txt
results/test_logs/claude_qualification.txt
```

### AC-14 — Final best-agent and submission decision

Evidence:

```text
results/artifacts/final_matchup_matrix.csv
results/artifacts/final_pairwise_intervals.json
results/artifacts/final_regression_report.json
results/artifacts/best_agent_selection.json
results/artifacts/SUBMISSION_F_DECISION.md
results/artifacts/submission_F_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/test_logs/final_evaluation.txt
```

Conditional Kaggle evidence:

```text
results/artifacts/submission_F_selfplay_curriculum.tar.gz
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/artifacts/kaggle_teacher_agent_comparison.json
results/artifacts/KAGGLE_PROMOTION_DECISION.md
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

### AC-15 — Content-aware evidence validation and source bundle

Evidence:

```text
results/artifacts/evidence_validation.json
results/artifacts/c012_python_source_bundle.zip
results/artifacts/c012_python_source_manifest.json
results/test_logs/evidence_validation.txt
results/test_logs/source_bundle_validation.txt
```

### AC-16 — Next step, Git, and source integrity

Evidence:

```text
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
results/GIT_REPORT.md
results/artifacts/c012.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

A `PASS` requires content validation, not file existence.

---

## 53. Required results structure

```text
contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── GIT_REPORT.md
├── artifacts/
│   ├── dependency_verification.json
│   ├── immutability_verification.json
│   ├── c011_repair_report.json
│   ├── trainer_state_schema.json
│   ├── c011_candidate_registry.json
│   ├── c011_checkpoint_confirmation.json
│   ├── c011_confirmation_games.jsonl.gz
│   ├── elite_combination_registry.json
│   ├── elite_combination_results.json
│   ├── frozen_incumbent_registry.json
│   ├── elite_pool_registry.json
│   ├── TRUE_INCUMBENT.md
│   ├── cross_play_matrix.csv
│   ├── behavioral_fingerprints.json
│   ├── state_distribution_overlap.json
│   ├── policy_agreement.json
│   ├── gain_attribution.json
│   ├── opponent_overlap_report.json
│   ├── OPPONENT_OVERLAP.md
│   ├── curriculum_hypothesis.md
│   ├── curriculum_registry.json
│   ├── curriculum_registry.sha256
│   ├── P0_summary.json
│   ├── P0_training_games.jsonl.gz
│   ├── P0_updates.jsonl.gz
│   ├── P0_checkpoint_registry.json
│   ├── P1_summary.json
│   ├── P1_training_games.jsonl.gz
│   ├── P1_updates.jsonl.gz
│   ├── P1_checkpoint_registry.json
│   ├── P1_curriculum_history.jsonl
│   ├── curriculum_evaluation_games.jsonl.gz
│   ├── curriculum_final_matrix.csv
│   ├── curriculum_pairwise_intervals.json
│   ├── forgetting_report.json
│   ├── cycling_report.json
│   ├── CURRICULUM_RESULT.md
│   ├── SELF_PLAY_LOOP.md
│   ├── curriculum_decision.json
│   ├── hard_state_benchmark.jsonl.gz
│   ├── hard_state_manifest.json
│   ├── hard_state_hidden_information_audit.json
│   ├── claude_prompt.md
│   ├── claude_label_schema.json
│   ├── claude_preflight.json
│   ├── claude_inputs.jsonl.gz
│   ├── claude_outputs.jsonl.gz
│   ├── claude_validation.json
│   ├── branching_validation.json
│   ├── claude_action_adjudication.json
│   ├── claude_consistency.json
│   ├── claude_category_results.json
│   ├── CLAUDE_TEACHER_STATUS.md
│   ├── claude_teacher_decision.json
│   ├── final_matchup_matrix.csv
│   ├── final_pairwise_intervals.json
│   ├── final_regression_report.json
│   ├── best_agent_selection.json
│   ├── SUBMISSION_F_DECISION.md
│   ├── submission_F_selfplay_curriculum.tar.gz
│   ├── submission_F_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_agent_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── evidence_validation.json
│   ├── c012_python_source_bundle.zip
│   ├── c012_python_source_manifest.json
│   ├── NEXT_STEP.md
│   ├── next_step.json
│   ├── c012.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
├── test_logs/
│   ├── dependency_verification.txt
│   ├── rng_restore.txt
│   ├── trainer_state_continuation.txt
│   ├── budget_accounting.txt
│   ├── early_stopping.txt
│   ├── scale_bootstrap.txt
│   ├── c011_checkpoint_confirmation.txt
│   ├── elite_combination_eval.txt
│   ├── incumbent_freeze.txt
│   ├── opponent_overlap_analysis.txt
│   ├── curriculum_lock.txt
│   ├── P0_training.txt
│   ├── P1_training.txt
│   ├── curriculum_evaluation.txt
│   ├── hard_state_extraction.txt
│   ├── claude_preflight.txt
│   ├── claude_labeling.txt
│   ├── branching_validation.txt
│   ├── claude_qualification.txt
│   ├── final_evaluation.txt
│   ├── evidence_validation.txt
│   ├── source_bundle_validation.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
└── failures/
```

Conditional artifacts may be absent only when explicitly allowed and the absence is validated.

---

## 54. Required summary and status

`SUMMARY.md` must state:

- dependency hashes
- machine/CUDA profile
- c011 defects repaired
- true incumbent
- evaluation elite
- elite pool
- checkpoint/ensemble/soup results
- opponent-overlap conclusion
- curriculum hypothesis
- P0 per-seed results
- P1 per-seed results
- curriculum decision
- self-play-loop decision
- Iono/Abomasnow regressions
- historical forgetting/cycling
- hard-state benchmark composition
- Claude preflight/model
- Claude legality/schema/hidden-information results
- branching validity
- Claude qualification
- best agent
- teacher and strategic-field scores
- submission decision
- Kaggle evidence when applicable
- next step
- highest-leverage blocker
- training/evaluation/Claude totals
- known limitations

`STATUS.json` schema:

```json
{
  "contract": "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "c011_repair": "COMPLETE",
  "true_incumbent": "...",
  "opponent_overlap": "PARTIALLY_SUPPORTED",
  "curriculum_result": "ADAPTIVE_WINS",
  "self_play_loop": "EXTENDED",
  "claude_branching": "VALID",
  "claude_teacher_status": "QUALIFIED_SPECIALIST",
  "best_agent": "...",
  "submission_F": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "kaggle_submission_status": null,
  "promotion_decision": "PROMOTE_NEW_AGENT",
  "next_step": "RUN_CLAUDE_CONTROLLED_PILOT",
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

## 55. Git requirements

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c012:
```

Recommended commits:

```text
c012: repair c011 continuation and freeze incumbent
c012: analyze opponent overlap and lock curriculum
c012: execute control and adaptive self-play
c012: qualify claude offline teacher
c012: validate final agent and decisions
```

Do not:

- push
- force-push
- rebase shared history
- amend user commits
- modify c005–c011
- commit credentials
- change registered curriculum or gates after training begins

---

## 56. Stop and status rules

Set `BLOCKED` when:

- required checkpoint/deck/teacher is missing
- c011 CUDA backend cannot be reproduced
- true incumbent cannot be resolved
- user changes overlap and cannot be preserved
- simulator is unavailable

Set `PARTIAL` when:

- c011 repair is incomplete
- a required P0/P1 seed is skipped without registered stop rule
- identity-safe evaluation fails
- raw games do not reproduce aggregates
- curriculum registry changes after lock
- training hard maximum is exceeded
- content-aware validation fails
- earlier contracts are modified
- required Kaggle upload fails externally

Claude external block alone may produce overall `PASS` only when:

- AC-12/13 explicitly record `EXTERNAL_BLOCK`
- Claude-dependent acceptance logic treats the external block as an allowed terminal outcome
- every non-Claude mandatory phase passes
- all attempted Claude inputs/errors are preserved
- status accurately reports the limitation

Do not claim Claude qualification when externally blocked.

---

## 57. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Frozen deck fingerprint:
C011 repair:
True training incumbent:
Evaluation elite:
Elite pool:
Opponent overlap:
Curriculum hypothesis:
P0 seeds and results:
P1 seeds and results:
Curriculum result:
Self-play loop:
Best agent:
Teacher score:
Strategic-field score:
Iono score:
Abomasnow score:
Elite cross-play:
Historical forgetting:
Cycling:
Claude model:
Claude preflight:
Claude branching:
Claude teacher status:
Claude strongest categories:
Training games:
Evaluation games:
Claude primary labels:
Claude repeated labels:
Submission F:
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

Do not claim `PASS` unless all sixteen acceptance criteria execute and the content-aware validator passes.
