# c011 — Fixed-Deck CUDA PPO Scale and Source Audit Bundle

## 1. Purpose

Continue agent-only optimization on the exact frozen c005 Dragapult deck while replacing the c008/c010 NumPy-micrograd training backend with a parity-validated custom PyTorch/CUDA backend.

c011 must first repair the remaining c010 decision and checkpoint-selection gaps, then prove that the CUDA backend preserves policy semantics, then run a bounded multi-seed scale experiment from the strongest correctly confirmed incumbent.

This contract must answer:

1. Which saved c010 checkpoint is truly the strongest confirmed fixed-deck incumbent?
2. Does the custom PyTorch/CUDA backend reproduce the existing NumPy policy and PPO mathematics within registered tolerances?
3. Does CUDA materially improve PPO-update or end-to-end training throughput on the registered RTX 5070 machine?
4. Can the confirmed incumbent be extended beyond its c010 strength across multiple independent seeds?
5. Is the fixed-deck training loop strong enough to continue scaling, does it require an algorithm redesign, or is it ready to support later deck work?

Required final decisions:

```text
C010_EVIDENCE_REPAIR = REPAIRED | PARTIAL | UNREPAIRABLE
CUDA_BACKEND_PARITY = PASS | FAIL
CUDA_EXECUTION_MODE = FP32_CUDA | BF16_CUDA | NUMPY_FALLBACK
CUDA_SPEEDUP = MATERIAL | MARGINAL | NONE | INCONCLUSIVE
INCUMBENT_ID = <registered candidate ID>
SCALE_RESULT = EXTENDED | NOT_EXTENDED | INCONCLUSIVE
BEST_AGENT = INCUMBENT | S_<seed>_<checkpoint> | NONE
TRAINING_LOOP_STATUS = VALIDATED | PROMISING | REJECTED
SUBMISSION_F = SUBMIT | DO_NOT_SUBMIT
PROMOTION_DECISION = PROMOTE_NEW_AGENT | KEEP_INCUMBENT | KEEP_TEACHER | NO_RL_SUBMISSION
NEXT_STEP = CONTINUE_FIXED_DECK_RL | REDESIGN_FIXED_DECK_AGENT | FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE
```

A negative competitive result may still produce contract `PASS` when every mandatory experiment and validation criterion completes honestly.

---

## 2. Winning-oriented strategy

The active sequence remains:

```text
frozen Dragapult deck
→ dependable agent-improvement loop
→ stronger fixed-deck agent
→ external calibration
→ deck optimization only after the agent-loop gate
```

Do not mutate, search, or optimize the deck in c011.

`FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE` is permitted only when all are true:

- `TRAINING_LOOP_STATUS = VALIDATED`;
- a reproducibly stronger fixed-deck agent exists;
- the final agent reaches at least 0.40 against the frozen teacher or passes a user-approved equivalent readiness gate;
- no major held-out regression exists;
- the agent can be reproduced, packaged, and evaluated without policy-quality noise dominating deck comparisons.

Otherwise remain in fixed-deck agent work.

---

## 3. Dependencies

Required:

```text
c005 frozen Dragapult teacher and exact deck
c007 untouched V2-A checkpoint
c008 custom environment, action decoder, PPO semantics, saved checkpoints
c009 identity-safe evaluator and content-aware validation
c010 training games, updates, checkpoints, screen/confirmation/final games, and source
registered machine profile: Ryzen 9 7900X, 61 GiB RAM, RTX 5070 12,227 MiB, CUDA-enabled PyTorch
```

Before work:

- record branch, initial HEAD, working-tree status, Python executable, PyTorch/CUDA versions, driver, GPU, CPU, RAM, and disk;
- record final accepted commits for c005–c010;
- verify frozen deck and teacher hashes;
- verify all c010 checkpoint hashes;
- reconstruct the c010 final-panel aggregates from raw games;
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
```

Do not modify:

- frozen teacher;
- frozen Dragapult deck;
- V2-A;
- any c008/c010 checkpoint;
- c009/c010 raw games or decisions;
- earlier result reports.

All repaired reports, CUDA code, tests, checkpoints, trainer states, source bundles, and evidence belong to c011-controlled paths.

---

## 5. Non-goals

Do not:

- mutate or search decks;
- introduce an external RL framework;
- install Stable-Baselines3, skrl, Ray RLlib, CleanRL, or equivalent;
- replace the custom action semantics;
- change the model architecture family;
- use random-initialized RL;
- add teacher replay, policy KL penalties, reward shaping, MCTS, or selective search;
- train on held-out Mega Abomasnow;
- perform a broad hyperparameter sweep;
- use final evaluation to alter weights;
- lower thresholds after results;
- claim CUDA success only because GPU utilization is nonzero.

PyTorch is the tensor/autograd/backend implementation, not a replacement algorithm.

---

## 6. Branch and source naming

Branch:

```text
contract/c011_fixed_deck_cuda_ppo_scale
```

Suggested new source:

```text
tools/c011_repair_c010.py
tools/c011_torch_model.py
tools/c011_torch_ppo.py
tools/c011_cuda_backend.py
tools/c011_train_scale.py
tools/c011_eval.py
tools/c011_aggregate.py
tools/c011_validate_evidence.py
tools/c011_build_source_bundle.py
tests/test_c011_forward_parity.py
tests/test_c011_action_parity.py
tests/test_c011_multiselect_parity.py
tests/test_c011_ppo_update_parity.py
tests/test_c011_npz_roundtrip.py
tests/test_c011_trainer_state_roundtrip.py
tests/test_c011_identity_safe_eval.py
tests/test_c011_source_bundle.py
```

Do not overwrite c008–c010 tools.

---

## 7. Phase 0 — c010 checkpoint and decision repair

Before new training, repair the remaining c010 evidence gaps under c011 results.

### 7.1 Confirm unconfirmed promising checkpoints

Enumerate every c010 saved checkpoint. At minimum inspect the c010 registry for late or high-screen checkpoints including, when present:

```text
C_511 around 15k games
C_522 around 10k, 15k, and 20k games
C_533 around 7.5k and 10k games
B_433 final checkpoint
```

Do not rely on these approximate names; resolve exact IDs and hashes from c010 registries.

Any saved checkpoint whose c010 screen satisfies at least one must receive a c011 confirmation panel:

```text
teacher score >= 0.27
strategic-field score >= 0.33
promotion composite within 0.03 of c010's best screen
late checkpoint at or after 75% of its branch budget with no reliability defect
```

### 7.2 Same-panel teacher baseline

Evaluate the frozen teacher on the exact c011 strategic panel against:

```text
Mega Lucario
Iono
Mega Abomasnow
```

Both seats, same game counts and identity protocol as candidate evaluation.

Do not compare a c011 candidate field score with a teacher score from a different panel when applying strategic-improvement or submission gates.

### 7.3 Repaired incumbent

Select the c011 starting incumbent from all correctly confirmed c010 candidates using:

1. teacher head-to-head;
2. strategic-field score;
3. held-out Mega Abomasnow;
4. worst-matchup risk;
5. reliability;
6. latency;
7. earlier training games when otherwise tied.

The incumbent must be frozen and hashed before CUDA training.

### 7.4 c010 governance repair

Document:

- c010 submission-gate comparison bug;
- the difference between best confirmed and strongest saved checkpoint;
- that c010 continuation was a warm restart rather than full-state continuation;
- any post-result decision-rule changes.

Do not rewrite c010 files.

---

## 8. Hardware and environment registration

Registered machine:

```text
OS: Ubuntu 24.04 native Linux
CPU: AMD Ryzen 9 7900X, 12 cores / 24 threads
RAM: 61 GiB
GPU: NVIDIA GeForce RTX 5070, 12,227 MiB VRAM
Driver: 595.71.05
PyTorch: 2.12.1+cu130
PyTorch CUDA: 13.0
Compute capability: 12.0
Python: 3.13.13
```

Preflight requirements:

- `torch.cuda.is_available()` is true;
- at least 8 GiB free GPU memory before CUDA training;
- at least 12 GiB available system RAM;
- at least 100 GiB free disk;
- no unresolved GPU OOM or thermal throttling;
- record desktop GPU use and available VRAM.

If preflight fails, record the failure. Do not silently reduce evidence requirements.

No new RL package is required or permitted.

---

## 9. Custom PyTorch/CUDA backend

Implement the existing policy/value architecture and PPO mathematics in PyTorch.

Required design:

```text
CPU simulator workers
→ identity-preserving NumPy trajectory records
→ batched tensor transfer
→ PyTorch PPO/value optimization on CUDA
→ export policy/value weights to the existing runtime NPZ format
→ evaluate through the established competition/runtime policy path
```

The official runtime and evaluation semantics remain the validated custom action stack.

### 9.1 Device behavior

- model parameters and optimizer state reside on CUDA during training;
- rollout storage may remain CPU-resident;
- use pinned memory only when measured beneficial;
- use non-blocking transfers only with pinned buffers;
- avoid per-decision CPU-to-GPU calls unless batching proves faster;
- do not force GPU rollout inference when CPU inference is faster.

### 9.2 Precision

Parity validation begins in deterministic FP32.

`BF16_CUDA` is permitted only after all are true:

- FP32 CUDA parity passes;
- BF16 masked-action and value outputs satisfy registered tolerances;
- fixed-batch PPO update remains finite and directionally consistent;
- a 2,000-game smoke run has zero reliability defects;
- measured end-to-end throughput improves by at least 10% over FP32 CUDA;
- no material evaluation regression appears in the smoke panel.

Otherwise use `FP32_CUDA`.

Do not use FP16.

### 9.3 Compilation

Do not use `torch.compile` in the main experiment unless a separately recorded benchmark proves:

- parity tests pass;
- compile warm-up cost is amortized;
- end-to-end throughput improves by at least 10%;
- no instability or graph-break issue affects action masking or multi-select logic.

Default is eager PyTorch.

---

## 10. Mandatory parity validation

CUDA training may not begin until all mandatory FP32 parity tests pass.

Use frozen fixtures covering ordinary, forced, masked, multi-select, variable-cardinality, and ordered decisions.

### 10.1 Forward parity

For the same NPZ weights and encoded states:

```text
maximum absolute logit error <= 1e-5
maximum absolute value error <= 1e-5
```

When exact ordering or floating implementation prevents this tolerance, stop and diagnose; do not simply widen it after results.

### 10.2 Legal-action probability parity

For every fixture:

- identical legal mask;
- illegal-action probability exactly zero after masking;
- selected argmax identical;
- total legal probability within `1e-6`;
- maximum legal-action probability error within `1e-5`.

### 10.3 Multi-select parity

For fixed-cardinality sequential masked selection:

- identical sub-selection order under deterministic argmax;
- summed log-probability error within `1e-5`;
- identical without-replacement mask evolution;
- identical forced-subselection bypass behavior.

### 10.4 PPO fixed-batch parity

On a frozen small trajectory batch, compare NumPy/micrograd and PyTorch before and after one registered update.

Required:

- policy loss error <= `1e-4`;
- value loss error <= `1e-4`;
- entropy error <= `1e-4`;
- approximate KL error <= `1e-4`;
- clip fraction error <= `1e-4`;
- parameter-update cosine similarity >= `0.999` for each trainable tensor;
- no NaN/Inf;
- same minibatch order and seed.

If the legacy implementation cannot expose a mathematically comparable tensor, document it and add an equivalent finite-difference or analytical check. Mandatory action semantics may not be waived.

### 10.5 NPZ round trip

PyTorch → NPZ → established runtime must preserve forward/action outputs within the forward tolerances.

### 10.6 Trainer-state round trip

Save and restore:

```text
policy weights
value weights
AdamW state
optimizer step
learning-rate state
entropy-schedule state
training game count
update count
Python RNG
NumPy RNG
PyTorch CPU RNG
PyTorch CUDA RNG
opponent sampler state
lagged snapshot registry and hashes
```

After restore, the next fixed-batch update must match an uninterrupted control within the PPO parity tolerances.

---

## 11. Throughput calibration

Benchmark the complete loop before scale training.

### 11.1 Simulator worker calibration

Benchmark:

```text
12 workers
16 workers
20 workers
```

For each record:

- games/hour;
- decisions/hour;
- CPU utilization;
- available RAM;
- process failures;
- rollout latency;
- PPO update latency;
- GPU utilization;
- VRAM;
- end-to-end update cycle time.

Choose the highest stable end-to-end throughput subject to:

- at least 8 GiB available RAM during sustained operation;
- no swap thrashing;
- no worker failure;
- no GPU OOM;
- no more than 5% throughput variance across repeated calibration windows.

Do not assume 24 workers is optimal.

### 11.2 Backend benchmark

Compare on the same frozen rollout batch:

```text
legacy NumPy/micrograd update
PyTorch CPU update
PyTorch FP32 CUDA update
optional PyTorch BF16 CUDA update
```

Define:

```text
CUDA_SPEEDUP = MATERIAL
```

when either:

- PPO-update throughput improves by at least 1.5× and end-to-end training throughput improves by at least 1.15×; or
- end-to-end training throughput improves by at least 1.25×.

Define `MARGINAL` when end-to-end gain is positive but below those thresholds.

Define `NONE` when CUDA is not faster or is operationally worse.

If FP32 CUDA parity passes but CUDA speed is `NONE`, set `CUDA_EXECUTION_MODE = NUMPY_FALLBACK` for scale training and explain why. Correctness and winning throughput take priority over forcing GPU use.

---

## 12. Training recipe

Use the c010 Arm C algorithm exactly, except for the registered backend migration and longer scale horizon.

Registered algorithm:

```text
initialization                  = repaired c010 incumbent
gamma                          = 0.997
GAE lambda                     = 0.95
PPO clip                       = 0.20
value coefficient              = 0.50
entropy schedule               = c010 Arm C schedule, resolved and frozen
maximum gradient norm          = 0.50
PPO epochs                     = 4
optimizer                      = AdamW
learning rate                  = 3e-5
weight decay                   = 1e-5
advantage normalization        = per update
value clipping                 = enabled
rollout target                 = 256 completed games
minimum trainable decisions    = 32,768
reward                         = terminal win +1, draw 0, loss -1
```

Collect until both rollout thresholds are reached.

No teacher replay or KL loss.

The backend may change; the learning algorithm may not.

---

## 13. Training population

Use the c010 population exactly:

```text
35% frozen Dragapult teacher
20% official Mega Lucario
20% official Iono
15% lagged branch-specific snapshots after 5,000 games
10% deterministic engineering control
```

Before lagged self-play, redistribute the 15% proportionally among teacher, Lucario, and Iono.

Requirements:

- seats approximately 50/50;
- exact opponent/seat counts preserved per rollout and cumulatively;
- lagged snapshot IDs and hashes preserved;
- Mega Abomasnow remains evaluation-only;
- no seed-specific population tuning.

---

## 14. Scale arms

Run three independent scale seeds from the same repaired incumbent.

```text
S1 seed 611
S2 seed 622
S3 seed 633
```

Each is a warm restart because c010 did not preserve full trainer state. State this explicitly.

Maximum additional completed training games per seed:

```text
40,000
```

Registered evaluation points:

```text
game 0
5,000
10,000
15,000
20,000
30,000
40,000
```

After the first c011 update, all later checkpoints must contain full trainer state so future continuation can be literal rather than a warm restart.

Maximum registered new training games:

```text
120,000
```

Hard maximum including calibration smoke games:

```text
124,000
```

Do not exceed the hard maximum.

---

## 15. Incumbent protection and early stopping

The repaired c010 incumbent is permanently protected.

Each seed tracks:

```text
latest checkpoint
best screened checkpoint
best confirmed checkpoint
full trainer-state checkpoint
```

A newer checkpoint never replaces an older stronger checkpoint automatically.

Early stop a seed after game 10,000 when either:

### Confirmed severe regression

Two consecutive confirmation evaluations show:

```text
teacher score <= incumbent - 0.07
and strategic-field score <= incumbent - 0.07
and regression probability >= 90% on both
```

### Confirmed plateau

Three consecutive registered evaluations show no confirmed improvement of at least:

```text
+0.02 teacher score
or
+0.02 strategic-field score
```

relative to that seed's best confirmed checkpoint.

Do not stop solely from a noisy 100-game screen.

---

## 16. Training evidence

Preserve one compact record per training game with:

```text
arm/seed
full trainer-state ID
policy checkpoint hash
opponent ID and opponent checkpoint hash
seat
outcome and score
decision count
forced-decision count
episode length
policy entropy mean
initial and final value prediction
invalid actions
fallbacks
exceptions
timeouts
```

Per update preserve:

- losses;
- entropy;
- approximate KL;
- clip fraction;
- explained variance;
- gradient norm;
- learning rate;
- precision mode;
- device;
- games and decisions;
- CPU/GPU timing;
- GPU utilization and VRAM;
- CPU utilization and RAM;
- opponent and seat distributions;
- checkpoint/trainer-state lineage.

Value diagnostics must use actual terminal outcomes, not only GAE lambda-return targets, and report by game phase:

```text
Brier score
calibration error
outcome accuracy/AUC when defined
Monte Carlo outcome error
explained variance against terminal outcome
advantage mean/std and signal-to-noise
```

Phases:

```text
0–20%
20–40%
40–60%
60–80%
80–100%
```

---

## 17. Identity-safe evaluation

Reuse c009/c010 immutable job identity.

Every job/result includes:

```text
job_id
candidate_id
checkpoint SHA-256
trainer-state ID when applicable
opponent
seat
replicate
requested seed
phase
frozen deck fingerprint
```

Mandatory assertions:

- submitted/returned job sets match;
- no duplicate IDs;
- checkpoint hashes match loaded weights;
- deck fingerprint matches;
- opponent and seat match registry;
- expected counts are exact;
- defects are explicit;
- raw games reproduce every aggregate.

No positional reattachment after unordered multiprocessing.

---

## 18. Evaluation panels

Pre-generate fixed job registries before training results are inspected.

### 18.1 Screen panel

For every registered checkpoint:

```text
teacher:       20 games per seat
Mega Lucario:  10 games per seat
Iono:          10 games per seat
Mega Abomasnow:10 games per seat
```

Total 100 games.

### 18.2 Confirmation panel

For every nominated checkpoint:

```text
teacher:       100 games per seat
Mega Lucario:   50 games per seat
Iono:           50 games per seat
Mega Abomasnow: 50 games per seat
```

Total 500 games.

### 18.3 Final panel

Evaluate:

```text
frozen teacher as strategic-field baseline
repaired c010 incumbent
best confirmed S1
best confirmed S2
best confirmed S3
```

For each policy candidate:

```text
teacher head-to-head: 200 games per seat
Mega Lucario:         100 games per seat
Iono:                 100 games per seat
Mega Abomasnow:       100 games per seat
```

Total 1,000 games per candidate.

Evaluate the frozen teacher against Lucario, Iono, and Abomasnow using the same 100 games per seat panel and same job registry construction.

If a candidate remains plausibly teacher-non-inferior, extend direct teacher head-to-head to 800 total games.

---

## 19. Checkpoint nomination

A checkpoint receives confirmation when any is true:

- teacher screen exceeds the seed's best confirmed teacher score by at least 0.03;
- field screen exceeds the seed's best confirmed field score by at least 0.04;
- promotion composite exceeds the seed's current best screen;
- it is the seed's final registered checkpoint;
- it is a late checkpoint at or after 75% of budget and is within 0.03 of the seed's best screen composite.

This final condition reduces the chance that noisy early screen peaks hide stronger late checkpoints.

Nomination is not promotion.

---

## 20. Metrics

### Teacher score

Seat-balanced match-point rate against the frozen teacher.

### Strategic-field score

Average seat-balanced score against:

```text
Mega Lucario
Iono
Mega Abomasnow
```

Teacher is separate and not double-counted.

### Promotion composite

```text
0.55 × teacher score
+ 0.15 × Lucario
+ 0.15 × Iono
+ 0.15 × Abomasnow
```

### Major regression

Relative to the repaired incumbent:

```text
candidate <= incumbent - 0.07
and bootstrap probability of regression >= 90%
```

For submission, also test regression relative to the frozen teacher on the same panel.

---

## 21. Scale-result decision

Set:

```text
SCALE_RESULT = EXTENDED
```

when:

1. at least two of three seeds produce a confirmed checkpoint that beats the repaired incumbent on teacher score;
2. at least two beat the incumbent on strategic-field score;
3. the median best-per-seed result improves by at least:
   - 0.03 teacher score; and
   - 0.03 strategic-field score;
4. at least one median improvement has at least 90% bootstrap probability above zero;
5. no majority of seeds has a major held-out Abomasnow regression;
6. reliability passes.

Set `NOT_EXTENDED` when fewer than two seeds improve both dimensions and uncertainty is not the reason.

Otherwise set `INCONCLUSIVE`.

Flag milestone levels separately:

```text
M1: teacher >= 0.35 and field >= 0.36
M2: teacher >= 0.40 and field >= 0.40
M3: teacher non-inferiority lower bound >= 0.47
```

These are not retroactive decision-rule changes.

---

## 22. Best-agent selection

A c011 candidate may replace the repaired incumbent only when:

- reliability passes;
- teacher score is not lower;
- field score is not lower;
- promotion composite is higher;
- at least one primary improvement has at least 90% bootstrap probability above zero;
- no major regression exists;
- hash and deck validation pass.

Select among qualifying candidates by:

1. teacher score;
2. strategic-field score;
3. Abomasnow;
4. worst matchup;
5. latency;
6. earlier training games.

If none qualify:

```text
BEST_AGENT = INCUMBENT
PROMOTION_DECISION = KEEP_INCUMBENT
```

---

## 23. Training-loop status

Set:

```text
TRAINING_LOOP_STATUS = VALIDATED
```

when:

- `SCALE_RESULT = EXTENDED`;
- a new best agent is promoted;
- at least two seeds show the improvement;
- final-panel improvement survives content-aware validation;
- no major regression exists;
- full trainer-state continuation is now available;
- backend execution is reliable.

Set `PROMISING` when a real improvement exists but reproducibility, field confirmation, backend performance, or a gate remains incomplete.

Set `REJECTED` when no seed improves and the registered PPO family shows no credible extension signal, or reliability fails.

---

## 24. Submission gate

Set:

```text
SUBMISSION_F = SUBMIT
```

only when the new best agent:

- is not the repaired incumbent;
- passes reliability;
- passes direct teacher non-inferiority:

```text
one-sided 95% lower bound >= 0.47
```

- beats the frozen teacher's same-panel strategic-field score with a 90% bootstrap interval above zero, or satisfies the original registered matchup-improvement alternative;
- has no major regression relative to the teacher on the same panel;
- uses the exact frozen Dragapult deck;
- passes package validation.

Otherwise `DO_NOT_SUBMIT`.

Package validation is `NOT_APPLICABLE`, not `PASS`, when no package is required.

---

## 25. Conditional Kaggle workflow

When and only when `SUBMISSION_F = SUBMIT`, package:

```text
submission_F_fixed_deck_cuda_rl.tar.gz
```

Description:

```text
c011 Submission F: <BEST_AGENT> fixed deck <final_commit_short_sha>
```

Validate exact deck, checkpoint hash, archive hash, clean extraction, required `cg/` structure, latency, size, zero invalid actions/errors/timeouts, duplicate guard, and absence of trainer-only artifacts.

Claude Code is explicitly authorized and required to upload, retrieve the reference, poll every 30 seconds for at most 20 attempts, record score/status history, refresh teacher submission `54948560`, preserve comparison, and determine promotion.

Do not expose credentials.

If required upload fails externally, set `PARTIAL`.

When gated off:

```text
KAGGLE_UPLOAD = SKIPPED_BY_GATE
PROMOTION_DECISION = NO_RL_SUBMISSION or KEEP_INCUMBENT as appropriate
```

---

## 26. Mandatory Python source bundle

Create:

```text
results/artifacts/c011_python_source_bundle.zip
```

This archive is mandatory even when training fails or submission is skipped.

### 26.1 Required contents

Include:

1. Every tracked repository `*.py` file at final HEAD, obtained from Git rather than a hand-maintained list.
2. Every untracked or generated c011 `*.py` file used during execution.
3. All c011 tests.
4. All Python entrypoints invoked by commands in `COMMANDS_RUN.md`.
5. A source manifest containing original path, archive path, byte size, Git status, and SHA-256.
6. `pip freeze` output.
7. Python, PyTorch, CUDA, cuDNN, driver, GPU, CPU, RAM, and OS snapshots.
8. Git branch, initial HEAD, final HEAD, and `git diff`/patch.
9. An import graph or import inventory for c011 entrypoints.
10. An entrypoint list explaining which command used each Python file.
11. The exact c011 contract, command, inputs, and references.

### 26.2 Exclusions

Do not include:

- `.venv/` or site-packages;
- `__pycache__/`;
- `.pyc` files;
- credentials, tokens, cookies, `.env`, Kaggle credential files;
- model checkpoints or large datasets unless separately required;
- raw training/evaluation games already stored elsewhere in results.

### 26.3 Validation

The source bundle validator must:

- extract into a clean temporary directory;
- verify every manifest hash;
- verify all tracked Python files at final HEAD are represented;
- verify every executed Python entrypoint is present;
- verify no forbidden secret-pattern filename is included;
- verify the archive SHA-256;
- produce a human-readable inventory.

Also create:

```text
results/artifacts/c011_python_source_manifest.csv
results/artifacts/c011_python_source_bundle.sha256
results/artifacts/c011_python_entrypoints.json
results/test_logs/python_source_bundle_validation.txt
```

This bundle is specifically intended for later external debugging and audit.

---

## 27. Next-step rule

Set:

```text
NEXT_STEP = CONTINUE_FIXED_DECK_RL
```

when the loop is validated or promising with a clear upward trajectory and the best agent remains below the deck-pipeline readiness gate.

Set:

```text
NEXT_STEP = REDESIGN_FIXED_DECK_AGENT
```

when scale does not extend the incumbent, CUDA/backend defects dominate, or PPO improvement saturates below a strategically useful level.

Set:

```text
NEXT_STEP = FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE
```

only under Section 2.

State exactly one highest-leverage blocker and distinguish measured evidence from hypothesis.

---

## 28. Mandatory acceptance criteria

### AC-01 — Dependency, hardware, and immutability verification

Evidence:

```text
results/artifacts/dependency_verification.json
results/artifacts/hardware_environment.json
results/artifacts/immutability_verification.json
results/test_logs/dependency_verification.txt
```

### AC-02 — c010 evidence repair and incumbent selection

Evidence:

```text
results/artifacts/c010_governance_repair.md
results/artifacts/c010_checkpoint_reconfirmation.json
results/artifacts/c010_repaired_incumbent.json
results/test_logs/c010_repair.txt
```

### AC-03 — PyTorch model and action parity

Evidence:

```text
results/artifacts/forward_action_parity.json
results/test_logs/forward_action_parity.txt
```

### AC-04 — PPO update and gradient parity

Evidence:

```text
results/artifacts/ppo_update_parity.json
results/test_logs/ppo_update_parity.txt
```

### AC-05 — NPZ and full trainer-state round trips

Evidence:

```text
results/artifacts/npz_roundtrip.json
results/artifacts/trainer_state_roundtrip.json
results/test_logs/roundtrip_tests.txt
```

### AC-06 — CUDA precision and smoke validation

Evidence:

```text
results/artifacts/cuda_precision_decision.json
results/artifacts/cuda_smoke_validation.json
results/test_logs/cuda_smoke.txt
```

### AC-07 — Throughput calibration and backend decision

Evidence:

```text
results/artifacts/worker_calibration.json
results/artifacts/backend_benchmark.json
results/artifacts/CUDA_EXECUTION_MODE.md
results/test_logs/throughput_calibration.txt
```

### AC-08 — Scale seed 611 execution

Evidence:

```text
results/artifacts/seed_611_summary.json
results/artifacts/seed_611_training_games.jsonl.gz
results/artifacts/seed_611_updates.jsonl.gz
results/artifacts/seed_611_checkpoint_registry.json
results/test_logs/seed_611_training.txt
```

### AC-09 — Scale seed 622 execution

Evidence analogous to AC-08.

### AC-10 — Scale seed 633 execution

Evidence analogous to AC-08.

### AC-11 — Screening, confirmation, and identity-safe raw evaluation

Evidence:

```text
results/artifacts/checkpoint_screening.csv
results/artifacts/checkpoint_confirmation.json
results/artifacts/evaluation_games.jsonl.gz
results/artifacts/evaluation_game_manifest.json
results/test_logs/checkpoint_evaluation.txt
```

### AC-12 — Value, optimization, and hardware diagnostics

Evidence:

```text
results/artifacts/value_diagnostics_by_game_phase.json
results/artifacts/optimization_diagnostics.json
results/artifacts/hardware_utilization.jsonl.gz
results/test_logs/value_hardware_diagnostics.txt
```

### AC-13 — Final panel, scale decision, and best-agent selection

Evidence:

```text
results/artifacts/final_matchup_matrix.csv
results/artifacts/final_teacher_field_baseline.json
results/artifacts/final_pairwise_intervals.json
results/artifacts/final_ranking.json
results/artifacts/final_regression_report.json
results/artifacts/scale_result.json
results/artifacts/best_agent_selection.json
results/test_logs/final_evaluation.txt
```

### AC-14 — Content-aware evidence validation

Evidence:

```text
results/artifacts/evidence_validation.json
results/test_logs/evidence_validation.txt
```

Validate contents, hashes, game counts, aggregate reconstruction, parity, configuration, budgets, trainer-state lineage, decisions, and conditional artifacts.

### AC-15 — Python source bundle and source integrity

Evidence:

```text
results/artifacts/c011_python_source_bundle.zip
results/artifacts/c011_python_source_manifest.csv
results/artifacts/c011_python_source_bundle.sha256
results/artifacts/c011_python_entrypoints.json
results/test_logs/python_source_bundle_validation.txt
```

### AC-16 — Submission, next step, and Git integrity

Evidence:

```text
results/artifacts/SUBMISSION_F_DECISION.md
results/artifacts/submission_F_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/artifacts/NEXT_STEP.md
results/artifacts/next_step.json
results/GIT_REPORT.md
results/artifacts/c011.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

Conditional Kaggle evidence is required only when submission passes. A `PASS` requires the content-aware validator and source-bundle validator to pass.

---

## 29. Required result structure

```text
contracts/c011_fixed_deck_cuda_ppo_scale/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── GIT_REPORT.md
├── artifacts/
│   ├── dependency_verification.json
│   ├── hardware_environment.json
│   ├── immutability_verification.json
│   ├── c010_governance_repair.md
│   ├── c010_checkpoint_reconfirmation.json
│   ├── c010_repaired_incumbent.json
│   ├── forward_action_parity.json
│   ├── ppo_update_parity.json
│   ├── npz_roundtrip.json
│   ├── trainer_state_roundtrip.json
│   ├── cuda_precision_decision.json
│   ├── cuda_smoke_validation.json
│   ├── worker_calibration.json
│   ├── backend_benchmark.json
│   ├── CUDA_EXECUTION_MODE.md
│   ├── seed_611_summary.json
│   ├── seed_611_training_games.jsonl.gz
│   ├── seed_611_updates.jsonl.gz
│   ├── seed_611_checkpoint_registry.json
│   ├── seed_622_summary.json
│   ├── seed_622_training_games.jsonl.gz
│   ├── seed_622_updates.jsonl.gz
│   ├── seed_622_checkpoint_registry.json
│   ├── seed_633_summary.json
│   ├── seed_633_training_games.jsonl.gz
│   ├── seed_633_updates.jsonl.gz
│   ├── seed_633_checkpoint_registry.json
│   ├── checkpoint_screening.csv
│   ├── checkpoint_confirmation.json
│   ├── evaluation_games.jsonl.gz
│   ├── evaluation_game_manifest.json
│   ├── value_diagnostics_by_game_phase.json
│   ├── optimization_diagnostics.json
│   ├── hardware_utilization.jsonl.gz
│   ├── final_matchup_matrix.csv
│   ├── final_teacher_field_baseline.json
│   ├── final_pairwise_intervals.json
│   ├── final_ranking.json
│   ├── final_regression_report.json
│   ├── scale_result.json
│   ├── best_agent_selection.json
│   ├── evidence_validation.json
│   ├── c011_python_source_bundle.zip
│   ├── c011_python_source_manifest.csv
│   ├── c011_python_source_bundle.sha256
│   ├── c011_python_entrypoints.json
│   ├── SUBMISSION_F_DECISION.md
│   ├── submission_F_fixed_deck_cuda_rl.tar.gz
│   ├── submission_F_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── kaggle_teacher_agent_comparison.json
│   ├── KAGGLE_PROMOTION_DECISION.md
│   ├── NEXT_STEP.md
│   ├── next_step.json
│   ├── c011.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
├── test_logs/
│   ├── dependency_verification.txt
│   ├── c010_repair.txt
│   ├── forward_action_parity.txt
│   ├── ppo_update_parity.txt
│   ├── roundtrip_tests.txt
│   ├── cuda_smoke.txt
│   ├── throughput_calibration.txt
│   ├── seed_611_training.txt
│   ├── seed_622_training.txt
│   ├── seed_633_training.txt
│   ├── checkpoint_evaluation.txt
│   ├── value_hardware_diagnostics.txt
│   ├── final_evaluation.txt
│   ├── evidence_validation.txt
│   ├── python_source_bundle_validation.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   └── final_git_status.txt
└── failures/
```

Conditional files may be absent only where explicitly allowed and validated.

---

## 30. Required summary and status

`SUMMARY.md` must state:

- dependency and machine hashes;
- c010 governance defects and repaired incumbent;
- parity results;
- precision/backend decision;
- worker and backend throughput;
- per-seed training/evaluation results;
- trainer-state continuity evidence;
- value diagnostics by actual game outcome and phase;
- best agent;
- teacher and same-panel strategic-field baselines;
- scale result;
- training-loop status;
- submission and Kaggle decision;
- source-bundle path and SHA-256;
- next step;
- highest-leverage measured blocker;
- hypotheses clearly labeled as hypotheses;
- known limitations.

`STATUS.json` schema:

```json
{
  "contract": "c011_fixed_deck_cuda_ppo_scale",
  "status": "PASS",
  "acceptance_criteria_total": 16,
  "acceptance_criteria_passed": 16,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "c010_evidence_repair": "REPAIRED",
  "cuda_backend_parity": "PASS",
  "cuda_execution_mode": "FP32_CUDA",
  "cuda_speedup": "MATERIAL",
  "incumbent_id": "...",
  "scale_result": "EXTENDED",
  "best_agent": "S_...",
  "training_loop_status": "VALIDATED",
  "submission_F": "DO_NOT_SUBMIT",
  "kaggle_upload": "SKIPPED_BY_GATE",
  "kaggle_submission_ref": null,
  "promotion_decision": "PROMOTE_NEW_AGENT",
  "next_step": "CONTINUE_FIXED_DECK_RL",
  "python_source_bundle": "results/artifacts/c011_python_source_bundle.zip",
  "python_source_bundle_sha256": "...",
  "training_games": 0,
  "evaluation_games": 0,
  "highest_leverage_blocker": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

Values shown are examples, not predetermined outcomes.

---

## 31. Git requirements

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c011:
```

Recommended commits:

```text
c011: repair c010 checkpoint evidence
c011: add parity-validated pytorch cuda backend
c011: scale fixed-deck ppo across seeds
c011: validate final agent and source bundle
```

Do not push, force-push, rebase shared history, amend user commits, modify c005–c010, commit credentials, or change gates after results.

---

## 32. Stop and status rules

Set `BLOCKED` when:

- frozen dependencies are missing/corrupt;
- CUDA PyTorch is unavailable;
- action semantics cannot be ported;
- user changes overlap and cannot be preserved;
- simulator runtime is unavailable.

Set `PARTIAL` when:

- parity fails and the registered NumPy fallback cannot complete scale training;
- c010 promising checkpoints are skipped;
- required seeds are skipped without a registered rule;
- full trainer state is not preserved;
- raw games do not reproduce aggregates;
- hard compute maximum is exceeded;
- source bundle is incomplete or invalid;
- content-aware validation fails;
- earlier contracts are modified;
- required Kaggle upload fails externally.

Do not claim `PASS` because files exist.

---

## 33. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Machine profile:
Frozen deck fingerprint:
c010 checkpoints reconfirmed:
Repaired incumbent:
CUDA forward/action parity:
CUDA PPO parity:
Trainer-state round trip:
CUDA execution mode:
CUDA speedup:
Selected worker count:
Seed 611 best result:
Seed 622 best result:
Seed 633 best result:
Scale result:
Best agent:
Teacher score:
Strategic-field score:
Frozen-teacher field score:
Held-out Abomasnow score:
Major regressions:
Training-loop status:
Training games:
Evaluation games:
Submission F:
Submission archive:
Kaggle upload:
Kaggle submission ref:
Kaggle submission status:
Promotion decision:
Python source bundle:
Python source bundle SHA-256:
Next step:
Highest-leverage blocker:
Results directory:
Known limitations:
```

Do not claim `PASS` unless all sixteen acceptance criteria execute, the content-aware validator passes, and the Python source bundle validates.
