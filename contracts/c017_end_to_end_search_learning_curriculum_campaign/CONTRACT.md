# c017 — End-to-End Search, Learning, and Curriculum Campaign

## 1. Objective

Build and execute one integrated PTCG agent pipeline from the exact c016 state:

```text
frozen official Mega Lucario baseline
→ automatic baseline submission
→ bounded current-turn search
→ search-generated trajectories
→ policy/value distillation
→ baseline-anchored PPO curriculum with increasing self-play
→ policy/value-guided search or learned-policy fallback
→ common final panel
→ automatic submission of the strongest trustworthy post-baseline candidate
```

This is deliberately one large integration-first campaign rather than a chain of small contracts. The purpose is to expose interface and systems defects across the complete pipeline, preserve every probe and every line of source required for audit, perform one consolidated repair pass, and finish with external submission evidence.

The contract must not become eighteen miniature contracts. Probes are diagnostic instruments. Except for explicit submission-safety conditions, failed probes taint downstream artifacts but do not stop the pipeline.

## 2. Winning hypothesis

The registered technical hypothesis is:

> The exact official Mega Lucario agent provides reliable deck-specific semantics and fallback play; bounded search can improve complete-turn sequencing; search trajectories can train a compact policy/value model; and baseline-anchored curriculum training can increase self-play pressure without losing broad-field competence. The strongest trustworthy intermediate or final stage should outperform the frozen baseline and the Dragapult control locally and provide a credible external submission.

The contract is not required to prove that every stage is beneficial. It is required to run the full vertical system, preserve trustworthy intermediate stages, and submit the strongest stage that is legal, package-safe, permission-safe, and supported by uncorrupted evidence.

## 3. Fixed user decisions

The following decisions are final:

1. Build the complete pipeline in one contract.
2. Submit the previous c016 baseline at the beginning.
3. Use probes throughout, but do not stop after each failed probe to perfect that block.
4. Complete an early thin end-to-end run before deep debugging or scale-up.
5. Most failed probes mark artifacts `TAINTED` or `DIAGNOSTIC_ONLY`; they do not stop later blocks.
6. Only true submission-safety defects block submission of an affected candidate.
7. Perform at most one consolidated repair pass after the first end-to-end run.
8. Include the complete final source, focused competition source, milestone source snapshots, configs, tests, probes, logs, raw evidence, hashes, and Git patch under `results/`.
9. Increase self-play through a baseline-anchored curriculum based primarily on performance against the frozen baseline, with a field-regression guard.
10. Submit the strongest trustworthy stage, even when a later or more sophisticated stage is tainted or weaker.
11. Do not protect a method because it is sophisticated or expensive. External and common-panel evidence decides.

## 4. Dynamic starting state and Git

Start from the exact final c016 committed state.

Expected parent branch:

```text
contract/c016_public_agent_reproduction_gauntlet_and_champion_submission
```

Expected c016 final HEAD:

```text
eefc06aa9d7583e45a58836ce836ac9da0d8c252
```

Treat these as expected values. Before editing, record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -15 --oneline
```

Read c016 `STATUS.json`, Git history, raw candidate manifests, and the c016 final commit. If the checkout differs, use only safe checkout/branch operations. Do not reset, clean, rebase, force-push, or destroy unrelated files.

Create:

```text
contract/c017_end_to_end_search_learning_curriculum_campaign
```

from the exact c016 final HEAD. Commit messages begin with `c017:`.

Preserve dirty and untracked user files. Do not absorb unrelated work merely to make Git clean.

## 5. Historical immutability

Everything under c005 through c016 is read-only.

Do not modify:

- historical contracts or results;
- c014/c015/c016 status reports;
- prior submitted archives;
- Dragapult checkpoints and packages;
- public-source snapshots;
- unrelated user files.

All c017 code, data, packages, reports, and failures must be new files.

## 6. Time and compute envelope

This contract is a continuous integrated campaign with a hard maximum of 72 hours and at most two overnight runs.

Recommended allocation:

- baseline packaging and submission: ≤ 1 hour;
- full thin end-to-end smoke: ≤ 6 hours;
- consolidated diagnosis and repair: ≤ 8 hours;
- scaled search data, distillation, and curriculum: remaining window;
- final common panel, packages, submissions, and reporting: final 8–12 hours.

Hard compute limits unless a smaller limit is required by runtime:

- one registered primary training seed;
- no architecture tournament;
- no random-seed tournament;
- maximum 150,000 actual curriculum training games;
- maximum 25,000 search-teacher games or 150,000 search-labelled decisions, whichever arrives first;
- maximum three c017 Kaggle uploads: baseline, heuristic-search candidate, final trained/guided candidate;
- obey the current official daily submission limit if lower.

Do not extend the campaign merely because a block is “close.” Preserve the best trustworthy stage and finish.

## 7. Non-blocking probe doctrine

### 7.1 Probe statuses

Every probe records one of:

```text
PASS
WARN
FAIL_TAINTED
NOT_EXERCISED
```

Each produced artifact records:

- source version and config hash;
- direct probe dependencies;
- `trust_status`: `TRUSTED`, `TAINTED`, `DIAGNOSTIC_ONLY`, or `NON_SUBMITTABLE`;
- exact `tainted_by` probe IDs;
- whether it is usable for debugging, training, evaluation, or submission.

### 7.2 Default behavior after a failed probe

Unless further execution is technically impossible:

1. record the exact input, output, traceback, and state hash;
2. mark affected artifacts tainted;
3. apply only the smallest compatibility fallback required to continue;
4. continue the full pipeline;
5. defer substantive repair until the consolidated repair pass.

Do not pause for hours to perfect an isolated probe.

### 7.3 Submission blockers

The following block submission of the affected candidate, but do not automatically stop experimental execution:

1. hidden-information leakage;
2. illegal actions or invalid action encoding;
3. crashes, corruption, or unacceptable timeout risk;
4. candidate/opponent identity corruption in evaluation;
5. submitted package not matching evaluated source/config/deck/checkpoint;
6. unresolved code-reuse or attribution permission;
7. package extraction/import failure;
8. evidence derived from stale or wrong checkpoint identity when it is used for promotion.

Weak performance, low imitation agreement, noisy value calibration, curriculum non-promotion, search fixture misses, or moderate nondeterminism are not automatic execution blockers.

## 8. Baseline fixed before implementation

The previous baseline is the exact c016 `official_mega_lucario` candidate.

Expected source evidence:

```text
candidate_id: official_mega_lucario
source main SHA-256: ab8563b67b88b3666c2ff9c308505085a84fdac676c194c5b484d8544478c3b2
deck SHA-256: 406e2e9bd6ae82b8008b16ee64ffcbb58e4a50cd6bc36e33ae655456c6b9afee
fidelity: EXACT
permission class recorded by c016: SUBMISSION_REUSE_ALLOWED
```

Locate it from c016 raw artifacts and reverify all hashes. Do not strategically modify it before baseline submission.

The frozen baseline serves as:

- initial Kaggle calibration submission;
- legal deterministic fallback;
- fixed curriculum anchor;
- one evaluation opponent;
- source of deck-specific routine decisions.

# CAMPAIGN PASS A — BASELINE AND THIN END-TO-END INTEGRATION

## 9. Baseline package and mandatory initial submission

Build a clean inference-only archive from the exact official Mega Lucario candidate.

Preferred archive name when unused:

```text
results/packages/submission_J_official_mega_lucario_baseline.tar.gz
```

When that name or description already exists, choose a unique non-colliding c017 name and record it.

Before upload:

- verify exact source and deck hashes;
- preserve required attribution;
- inspect dependencies and network access;
- validate from a clean extraction;
- run at least 50 both-seat games against Dragapult and safe control combined;
- require zero invalid actions, zero exceptions, and zero timeouts;
- verify package entrypoint and packaged deck.

Automatically upload the exact validated archive. Record a non-null accepted reference. A score may remain `PENDING`; continue immediately after bounded polling.

Required outputs:

```text
results/probes/P00_baseline_submission/
results/packages/baseline/
results/submissions/baseline_submission.json
results/submissions/status_snapshots.jsonl
```

Failure to obtain an accepted baseline reference makes AC-01 fail, but the integrated experimental pipeline should continue when technically possible.

## 10. Thin end-to-end smoke before optimization

Build the full vertical pipeline with deliberately small budgets before scaling any block.

The smoke must execute, at least once:

```text
baseline action
→ state simulation/search attempt
→ trajectory write/read
→ policy/value train step
→ curriculum scheduler/evaluation callback
→ guided-search or learned-policy inference
→ final evaluator
→ clean package smoke
```

Suggested smoke budgets:

- search beam width 2–4;
- search node budget 32–64;
- 50–100 search-teacher games;
- 500–2,000 trajectory decisions;
- 1–3 supervised epochs;
- 2,000–5,000 curriculum games;
- 100–200 final-panel games total;
- 10 clean-extraction package games.

The objective is interface execution, not strength.

Create a machine-readable integration graph showing every interface, schema, version, and artifact hash.

Required outputs:

```text
results/integration/SMOKE_SUMMARY.md
results/integration/integration_graph.json
results/integration/interface_versions.json
results/integration/smoke_artifact_manifest.json
results/probes/P30_end_to_end_smoke/
```

Do not stop the smoke because a non-catastrophic probe fails. Use diagnostic fallbacks and finish the vertical run.

# BLOCK A — SIMULATION AND SEARCH

## 11. Search operating modes

Determine and record one of these modes:

### `ONLINE_SEARCH_MODE`

The packaged agent can legally and safely simulate visible-state continuations inside the submission environment without reading hidden information.

### `OFFLINE_TEACHER_MODE`

Reliable forward simulation exists only in the local simulator. Search generates training targets offline; the submitted learned agent does not depend on the search simulator.

### `HYBRID_MODE`

A limited subset of online transitions is safe/package-feasible, while broader search is used only offline.

Do not force online search when the competition interface does not support it. The pipeline must continue through offline search teacher and policy/value training.

## 12. Simulator/search adapter

Implement the minimum adapter required to:

- clone or reconstruct a search state;
- enumerate legal visible actions;
- apply an action;
- advance to the next decision;
- detect attack/end-turn/terminal state;
- serialize/hash visible state;
- redact inaccessible hidden information;
- measure node and clone latency;
- replay a selected first action through the real agent interface.

Do not build a universal game engine. Reuse the competition simulator and existing project code where valid.

## 13. Pivotal-decision detector and candidate generation

The exact baseline action is always retained.

Routine or forced decisions may immediately use the baseline. Search is focused on:

- search-card target choices;
- bench choices;
- evolution choices;
- energy attachment targets;
- switch/retreat choices;
- gust and attack targets;
- attack choice;
- action ordering where multiple complete-turn lines differ.

Generate no more than 3–5 credible actions per decision in the scaled configuration. Candidate generation may use:

- baseline ranking;
- legality and dominance filters;
- Mega Lucario deck/resource semantics;
- policy logits after the model exists.

Do not prune the baseline action.

## 14. Bounded current-turn search

Implement beam search or best-first search over the remainder of the current turn.

Scaled default caps:

- beam width: 8;
- maximum nodes per searched decision: 256–512;
- maximum action depth: 10–12 atomic decisions;
- stop at attack, end-turn, terminal, depth, node, or time budget;
- deterministic tie-breaking in registered deterministic mode;
- visible-state transposition/dominance cache;
- baseline fallback on timeout, unsupported state, or empty search result.

Do not implement full information-set MCTS, a multi-turn opponent tree, or generic multi-deck search in c017.

## 15. Heuristic leaf evaluator

Record every feature and weight in a versioned configuration.

At minimum evaluate:

- terminal win/loss;
- prizes taken and remaining;
- immediate knockout and game-winning lethal;
- active attacker readiness;
- backup attacker readiness;
- energy efficiency and stranded energy;
- critical remaining attackers, evolution pieces, energy, search, recovery, and gust resources;
- bench liability and likely prize concession;
- opponent visible next-turn threat;
- hand/board quality;
- future search and prize-route viability.

One consolidated repair pass may change weights only when the first integrated run exposes a high-impact evaluation error. No weight sweep.

## 16. Search probes

Run and preserve:

- **P01 clone/reconstruction parity:** matched visible successor states and legal actions;
- **P02 hidden-information access audit:** static and runtime access report;
- **P03 action replay legality:** selected first action encodes and replays legally;
- **P04 throughput/latency:** clone, node, decision, and projected match compute;
- **P05 baseline inclusion/candidate coverage:** baseline action retained and pivotal alternatives exercised;
- **P06 tactical fixtures:** lethal, target, attachment, benching, evolution, resource, and sequencing cases;
- **P07 determinism/repeatability:** fixed state/seed repeated traces;
- **P08 identical-seed baseline-vs-search smoke:** raw game identity-safe results.

These probes do not individually gate later blocks. They determine trust and submission eligibility.

Preserve sampled search traces with:

- root state hash;
- legal and candidate actions;
- baseline action;
- expanded lines;
- feature-level leaf-score decomposition;
- chosen line;
- nodes/depth/latency;
- fallback reason when used.

# BLOCK B — SEARCH-GENERATED TRAJECTORIES

## 17. Trajectory generation opponents

Generate trajectories against a mixture including:

- frozen official Mega Lucario baseline;
- Dragapult control;
- official Iono;
- official Mega Abomasnow;
- heuristic search itself when operational;
- executable c016 local benchmark agents when already available without new broad reproduction work;
- historical promoted policies after curriculum begins.

Safe control is used only for legality/reliability, not as a strategic training majority.

## 18. Required trajectory schema

Every decision record must include:

- schema version;
- game/trajectory/decision ID;
- visible-state encoding and source state hash;
- deck and opponent identity;
- seat, turn, phase, and decision type;
- exact legal actions and mask;
- baseline action;
- search-selected action;
- candidate actions;
- candidate line scores and normalized policy target;
- heuristic leaf value;
- search depth, nodes, latency, and fallback status;
- final game outcome;
- source code/config/checkpoint hashes;
- taint/trust metadata.

For beam search, create the policy target from a registered transformation of candidate line scores, such as temperature-softmax. Record the temperature and preserve hard top-1 labels.

Split train/validation/test by entire games, never by individual decisions from the same game.

## 19. Trajectory probes

Run:

- **P09 schema and round-trip reconstruction**;
- **P10 legality/mask/action identity consistency**;
- **P11 hidden-feature and split-leakage audit**;
- **P12 terminal outcome and game-log reconciliation**.

The full trajectory dataset may be stored outside the result ZIP only when size requires it, but results must include complete manifests, hashes, schemas, representative samples, every final-evaluation trajectory, and exact paths. Include compressed full data when practical.

# BLOCK C — POLICY/VALUE MODEL

## 20. Model implementation

Use the project’s custom PyTorch/CUDA stack. Do not add an external RL framework.

Reuse the strongest generic encoder/action implementation already present when it correctly represents the selected deck and legal actions. Extend only fields demonstrably missing for Mega Lucario/search decisions.

Build one compact shared-backbone policy/value model:

- policy head predicts the search-derived legal-action distribution;
- value head predicts final outcome in `[-1, 1]`;
- optional auxiliary value target may use normalized search leaf evaluation, but final outcome remains primary;
- legal-action masking is mandatory;
- deck/opponent context may be included only from visible or fixed public information.

No architecture tournament. One registered model configuration and one primary seed.

## 21. Supervised search distillation

Train on search trajectories before PPO curriculum.

Required losses:

- masked policy cross-entropy or KL to the search policy target;
- value regression to final outcome;
- optional small auxiliary leaf-value loss;
- recorded entropy and legal top-k metrics.

Save:

- initialization;
- best validation checkpoint;
- final checkpoint;
- optimizer/scheduler/scaler state;
- exact config and RNG states.

## 22. Model probes

Run:

- **P13 CUDA/training smoke:** finite losses, real CUDA use, throughput;
- **P14 checkpoint exact reload:** identical inference after save/reload;
- **P15 held-out policy metrics:** top-1, top-k, KL/CE, by decision category;
- **P16 value metrics:** MSE, correlation, calibration, constant-baseline comparison;
- **P17 action-mask legality:** zero illegal top-1 after masking;
- **P18 source-state/feature audit:** no hidden-information input.

High action agreement is a model-integrity result, not proof of strong gameplay.

# BLOCK D — BASELINE-ANCHORED PPO CURRICULUM

## 23. Training algorithm

Continue from the best search-distilled checkpoint using the existing custom PyTorch PPO/action implementation.

Allowed stabilization mechanisms:

- PPO clipped objective;
- value loss and entropy bonus;
- legal-action masks;
- optional KL anchor to the distilled policy;
- gradient clipping;
- exact checkpoint/resume;
- mixed precision when numerically safe.

Do not create a second RL framework or redesign the action space unless the integrated smoke proves the current representation technically unusable.

## 24. Frozen curriculum identities

Freeze and hash:

- `BASELINE_ANCHOR`: exact submitted official Mega Lucario package;
- `DRAGAPULT_CONTROL`;
- `FIELD_IONO`;
- `FIELD_ABOMASNOW`;
- any already executable strong benchmark opponent used;
- distilled starting checkpoint;
- every promoted historical checkpoint.

Evaluation must resolve identities explicitly. Never positional-zip unordered worker results.

## 25. Curriculum schedule

Self-play share means games against the latest candidate plus frozen promoted historical policies.

| Stage | Total self-play | Baseline anchor | Fixed field/historical non-self | Promotion condition |
|---|---:|---:|---:|---|
| S0 Distilled anchor | 0% | 45% | 55% | candidate ≥ 50% vs baseline; field no worse than distilled start by >3 pp; reliability clean |
| S1 Limited self-play | 10% | 35% | 55% | candidate ≥ 53% vs baseline; field no worse than best previous by >2 pp |
| S2 Moderate self-play | 30% | 25% | 45% | candidate ≥ 56% vs baseline; field at least baseline package field score |
| S3 Strong self-play | 50% | 20% | 30% | candidate ≥ 60% vs baseline; field improves over best prior by ≥2 pp; beats one prior promoted checkpoint |
| S4 Maximum allowed | 70% | 10% | 20% | optional; only after S3 remains broad-field stable |

Never use 100% latest-policy self-play.

Evaluate at registered game intervals, suggested every 10,000 actual training games. Each curriculum evaluation should include both seats and candidate-independent seeds, with approximately:

- 200 games versus baseline anchor;
- 300 games across the fixed field;
- 100 games versus selected historical policy when applicable.

The first evaluation may use smaller counts during smoke. Stage advancement cannot occur at game zero or by comparing a policy with itself.

## 26. Conservative fallback schedule

If live evaluation is stale, unavailable, or inconclusive, do not stop the integrated run. Continue with a diagnostic fallback schedule capped at 30% self-play:

```text
0–20k games: 0% self-play
20–50k games: 10% self-play
50k+ games: 20–30% self-play
```

Every transition must record exactly one reason:

```text
PERFORMANCE_PROMOTION
FALLBACK_SCHEDULE
SMOKE_FIXTURE
RECOVERY_AFTER_DEFECT
```

Only `PERFORMANCE_PROMOTION` is evidence that the curriculum strategically succeeded. Checkpoints produced under stale or identity-corrupted evaluation are tainted until re-evaluated correctly.

## 27. Curriculum probes

Run:

- **P19 transition fixtures:** stay, promote, reject field regression, reject reliability, no game-zero self-comparison;
- **P20 checkpoint freshness:** current hash changes and stale cache cannot satisfy promotion;
- **P21 opponent-mixture audit:** planned versus actual games, identities, seats, failures;
- **P22 exact continuation:** model, optimizer, scaler, scheduler, global/Python/NumPy/CUDA RNG, opponent sampler, curriculum state, data cursor;
- **P23 promotion arithmetic:** exact thresholds, no max/median/significance bug, identity-safe aggregation;
- **P24 policy diversity/collapse:** action entropy, repeated-action rates, cross-play against prior checkpoints.

Curriculum probe failures normally taint promotion claims but do not stop training. Continue under the conservative fallback schedule and preserve evidence.

# BLOCK E — GUIDED SEARCH AND PACKAGE CANDIDATES

## 28. Candidate stages

Produce and preserve at minimum:

1. `BASELINE_OFFICIAL_LUCARIO`;
2. `SEARCH_HEURISTIC` when search operates;
3. `POLICY_DISTILLED`;
4. `POLICY_CURRICULUM_BEST`;
5. `SEARCH_POLICY_ORDERED` when online/hybrid search operates;
6. `SEARCH_POLICY_VALUE_GUIDED` when value guidance operates.

A later stage does not replace an earlier trusted stage automatically.

## 29. Policy/value guidance

When online/hybrid search is feasible:

- policy logits rank/prune credible actions;
- baseline action remains included;
- learned value evaluates leaves;
- heuristic score remains available as fallback and comparison;
- use one registered heuristic/value blend, not a sweep.

When only offline-teacher mode is feasible:

- `POLICY_CURRICULUM_BEST` is the primary learned submission candidate;
- search remains the offline teacher and evaluator;
- do not pretend the package contains online search.

## 30. Guided-search probes

Run:

- **P25 identical-leaf evaluator comparison:** heuristic versus value ranking on the same leaves;
- **P26 policy ordering efficiency:** node reduction and retained-best-line rate;
- **P27 guided-search legality/latency/fallback**;
- **P28 package/runtime dependency audit**;
- **P29 checkpoint/config/source/deck/package hash reconciliation**.

# CAMPAIGN PASS B — CONSOLIDATED DIAGNOSIS AND ONE REPAIR

## 31. Defect triage

After the first complete smoke, rank defects by downstream impact.

Select at most three defects for one consolidated repair pass. Priority order:

1. hidden information, legality, identity, package/source mismatch;
2. trajectory/action-mask corruption;
3. stale checkpoint or curriculum identity;
4. search transition/evaluator defects that invalidate training labels;
5. model inference/training mismatch;
6. performance-only weaknesses.

Do not repair low-impact fixture aesthetics while a higher-impact integration defect remains.

Required outputs:

```text
results/repair/FIRST_PASS_DEFECT_RANKING.md
results/repair/first_pass_defects.json
results/repair/repair_plan.json
results/repair/repair_diff.patch
results/repair/post_repair_rerun_manifest.json
```

## 32. Rerun scope

Rerun from the earliest affected milestone only.

Examples:

- curriculum-only defect: reuse trusted search trajectories and distilled checkpoint;
- trajectory action-ID defect: regenerate trajectories and every dependent model;
- hidden-information search defect: online search candidate remains non-submittable; rebuild redacted/offline teacher path and regenerate dependent labels;
- package-only defect: rebuild and revalidate the same frozen candidate without strategic change.

No second broad repair pass. Minor syntax/package corrections are allowed only when they do not change strategy or invalidate evaluated identity.

# CAMPAIGN PASS C — SCALED RUN AND FINAL DECISION

## 33. Scaled execution

After the consolidated repair, run the scaled configuration using the remaining time/compute budget.

Preserve:

- every training interval summary;
- all promoted and best checkpoints;
- actual completed game counts;
- opponent identities and seat balance;
- curriculum stage history;
- search/data/model config hashes;
- early-stop reason.

Stop curriculum early when three consecutive registered evaluations produce no new best broad-field score and no meaningful baseline improvement. Preserve the best prior checkpoint.

## 34. Common final panel

Freeze the final panel and seeds before scoring final candidates.

Minimum opponents:

- exact submitted official Mega Lucario baseline;
- Dragapult control;
- official Iono;
- official Mega Abomasnow;
- heuristic search when trusted and not the candidate itself;
- at least one already executable stronger local public benchmark when available without new reproduction work;
- finalist cross-play.

Do not use c014/c015 or safe control as hard competitive blockers. Safe control remains a reliability probe.

Use both seats and identity-safe aggregation. Recommended final budget is 500–1,000 games per serious finalist across the panel, adjusted to fit time. Do not spend thousands of games distinguishing tiny differences after a clear winner exists.

Report for every candidate:

- baseline-anchor rate;
- Dragapult rate;
- fixed-field mean and per-opponent rates;
- finalist cross-play;
- reliability and latency;
- tactical error rates;
- trust/taint status;
- package feasibility;
- source/checkpoint/package hashes.

## 35. Registered selection rule

A candidate is submission-eligible only when:

- permission and attribution are resolved;
- no hidden information is used;
- zero invalid actions/exceptions/timeouts in clean package validation;
- evaluation identity and checkpoint freshness are trusted;
- package matches evaluated source/config/deck/checkpoint;
- latency is within official limits with safety margin.

Among eligible candidates, rank lexicographically:

1. broad fixed-field score;
2. score versus Dragapult;
3. score versus frozen baseline;
4. direct finalist cross-play;
5. tactical-error reduction;
6. lower p99 latency.

Do not force the most sophisticated candidate to win.

A post-baseline candidate is considered a meaningful local improvement when it achieves at least one:

- ≥ +3 percentage points broad fixed-field over baseline without a >5-point collapse on any major opponent;
- ≥ +5 points versus Dragapult or a pre-registered high-value opponent without broad regression;
- clear tactical-error reduction plus non-inferior broad field;
- direct finalist cross-play ≥55% with broad field non-inferior.

These are submission decision aids, not excuses to hide external results.

## 36. Automatic submission policy

### Submission A — baseline

Mandatory at contract start after minimal package safety validation.

### Submission B — heuristic search

Upload when `SEARCH_HEURISTIC` is trusted, package-safe, and meaningfully improves the baseline under §35. Do not wait for curriculum completion.

### Submission C — final trained/guided candidate

Upload when a trusted `POLICY_CURRICULUM_BEST`, `SEARCH_POLICY_ORDERED`, or `SEARCH_POLICY_VALUE_GUIDED` candidate meaningfully improves the strongest previously submitted c017 stage.

When no post-baseline stage clears the local improvement and submission-safety conditions, do not upload a knowingly invalid or clearly weaker package. Preserve all evidence and finish `PARTIAL` with the baseline reference and exact best experimental stage.

Use unique descriptions and never overwrite prior package artifacts. Poll status for a bounded interval. `PENDING` public score is acceptable after a non-null accepted reference.

Allow one mechanical retry per package only after fixing and fully revalidating a package-only defect. Strategic changes require a new package/version and new evaluation identity.

# RESULTS, SOURCE, AND AUDITABILITY

## 37. Mandatory result tree

Create at minimum:

```text
results/
  SUMMARY.md
  STATUS.json
  ACCEPTANCE_CHECKLIST.md
  DECISION_BOARD.md

  probes/
    P00_baseline_submission/
    P01_clone_parity/
    ...
    P29_package_hash_reconciliation/
    P30_end_to_end_smoke/

  integration/
    SMOKE_SUMMARY.md
    integration_graph.json
    interface_versions.json
    smoke_artifact_manifest.json

  search/
    configs/
    tactical_fixtures/
    sampled_node_traces/
    latency/
    fallback_events.jsonl.gz

  trajectories/
    schema.json
    manifests/
    representative_samples/
    integrity/

  training/
    configs/
    logs/
    checkpoints/
    curriculum_history.jsonl
    opponent_mix_history.jsonl
    evaluation_snapshots/
    resume_probes/

  final_panel/
    protocol.json
    seeds.json
    raw_games.jsonl.gz
    candidate_results.json
    selection_decision.json

  packages/
    baseline/
    heuristic_search/
    policy_distilled/
    curriculum_best/
    guided_search/

  submissions/
    baseline_submission.json
    heuristic_search_submission.json
    final_submission.json
    status_snapshots.jsonl

  repair/
    FIRST_PASS_DEFECT_RANKING.md
    first_pass_defects.json
    repair_plan.json
    repair_diff.patch
    post_repair_rerun_manifest.json

  failures/
    exceptions/
    timeouts/
    hidden_information/
    identity_mismatches/
    tainted_artifacts.json

  source/
    complete_repository_source.zip
    c017_competition_source_bundle.zip
    git_diff.patch
    source_manifest.json
    hashes.sha256
    environment.txt
    dependency_lock.txt
    milestones/
      M00_c016_start/
      M01_baseline_submitted/
      M02_full_smoke/
      M03_post_repair/
      M04_scaled_training_best/
      M05_final_candidates/
      M06_submitted_packages/

  git/
    initial_head.txt
    final_head.txt
    initial_status.txt
    final_status.txt
    branch.txt
    log.txt
```

## 38. Complete source requirement

`results/source/complete_repository_source.zip` must contain the complete repository source at final HEAD, excluding only:

- `.git/`;
- virtual environments;
- caches and compiled files;
- credentials/secrets;
- unrelated large datasets and generated game data.

It must include all code required to inspect and reproduce c017.

`results/source/c017_competition_source_bundle.zip` must include at minimum:

- baseline candidate and attribution;
- simulator/search adapter;
- pivotal-decision detector;
- candidate generator;
- search engine and leaf evaluator;
- trajectory writer/reader/schema;
- state encoder and action representation;
- policy/value model;
- supervised trainer;
- PPO loop;
- curriculum scheduler and opponent sampler;
- evaluator and identity-safe aggregation;
- package builder and submission entrypoint;
- every probe and test;
- all configs;
- exact deck files;
- report and validator code.

Source snapshots at milestones must tie artifacts to exact tree/config/checkpoint hashes. The source used to build each submitted package must be preserved even when later code differs.

## 39. Raw evidence requirement

Reports are not substitutes for raw evidence.

Preserve:

- game-level records;
- action-level trajectory samples;
- sampled search trees/node traces;
- legal masks and candidate scores;
- complete training logs;
- curriculum transitions;
- actual opponent counts;
- checkpoint hashes;
- package validation logs;
- Kaggle responses;
- exceptions, timeouts, divergence, and taint records;
- exact probe inputs and outputs.

Large datasets may use manifests plus hashes and external paths only when embedding is impractical, but final validation data, representative failure cases, and all code must be included.

## 40. Evidence validator

Implement a c017-specific content validator. It must fail or downgrade evidence integrity when it detects:

- copied c014/c015/c016 identifiers or stale contract titles in c017 reports;
- null required identities/hashes;
- zero-opportunity success claims;
- changed denominators without both original and corrected definitions;
- unordered-result positional identity mapping;
- stale checkpoint evaluation used for promotion;
- game-zero self-comparison promotion;
- planned opponent mix reported as actual mix;
- hidden features in model/search input;
- package/source/config/deck/checkpoint hash mismatch;
- submitted archive differs from clean-validated archive;
- `PASS` when baseline was not accepted;
- `PASS` when no post-baseline trusted submission exists;
- missing complete source bundles;
- modified historical c005–c016 files;
- `SKIPPED` or `NOT_APPLICABLE` counted as acceptance-criterion pass.

Run the validator after all final files exist and preserve its raw output.

# STATUS AND ACCEPTANCE

## 41. Component status model

`STATUS.json` must report separately:

- execution status for every block;
- trust status for every block/candidate;
- probe counts by status;
- exact taint graph;
- baseline submission reference/status/score;
- search mode;
- search games/nodes/latency;
- trajectory counts;
- supervised training metrics;
- curriculum games, stages, transitions, actual mixtures;
- best checkpoints;
- final candidate rankings;
- every package and submission hash/reference;
- external scores when available;
- exact blocking issues and next action.

Example distinction:

```json
{
  "heuristic_search_execution": "COMPLETED",
  "heuristic_search_trust": "TRUSTED",
  "curriculum_execution": "COMPLETED_WITH_FALLBACK",
  "curriculum_trust": "DIAGNOSTIC_ONLY",
  "guided_search_execution": "COMPLETED",
  "guided_search_trust": "TAINTED"
}
```

## 42. Acceptance criteria

There are eight criteria. Do not count `SKIPPED`, `NOT_EXERCISED`, or `NOT_APPLICABLE` as passes.

### AC-01 — Baseline freeze, package, and accepted submission

Exact official Mega Lucario source/deck verified; clean package validated; automatic upload accepted; non-null reference recorded.

### AC-02 — Complete thin end-to-end execution

Every major interface from baseline through final evaluator/package executes at least once, with integration graph and artifacts. Tainted execution may earn `PARTIAL`, not `PASS`.

### AC-03 — Search implementation and observability

Bounded search/offline teacher implemented; search mode declared; probes/traces/latency/fallback evidence preserved; no hidden-info claim without proof.

### AC-04 — Trajectory and policy/value system

Search-labelled dataset, schema/integrity evidence, compact CUDA policy/value model, exact reload, and held-out metrics produced.

### AC-05 — Baseline-anchored curriculum

PPO curriculum executes with registered stages or documented conservative fallback; actual opponent mixtures, freshness, resume, and transition evidence preserved.

### AC-06 — Final candidates, common panel, and honest selection

All viable intermediate/final candidates evaluated identity-safely on frozen seeds; trusted and tainted candidates separated; selection rule applied exactly.

### AC-07 — Strongest trustworthy post-baseline submission

At least one post-baseline candidate is clean-extraction validated and automatically submitted with an accepted reference. When no trustworthy candidate exists, AC-07 fails and overall status cannot be `PASS`.

### AC-08 — Complete source/evidence/Git integrity

Full repository source, focused source bundle, milestone snapshots, raw evidence, manifests/hashes, Git evidence, immutability verification, and content validator all pass.

## 43. Overall status

### `PASS`

Only when:

- AC-01 through AC-08 pass;
- baseline submission is accepted;
- complete integrated pipeline runs;
- at least one post-baseline trusted candidate is submitted and accepted;
- no unresolved submission-safety defect affects that package;
- full source/evidence validation passes.

### `PARTIAL`

Use when meaningful integrated work and baseline submission exist but:

- no post-baseline candidate is trustworthy/strong enough to submit;
- later stages are tainted;
- curriculum/guided search fails while an earlier stage remains valid;
- some ACs fail.

### `FAIL`

Use when the baseline cannot be preserved/submitted and the integrated pipeline does not produce auditable code/evidence, or when evidence integrity/source capture is fundamentally missing.

Never use operational completion alone to claim `PASS`.

## 44. Final decision board

At completion classify:

- external baseline;
- heuristic search;
- distilled policy;
- curriculum policy;
- guided search;
- Dragapult control;

as:

```text
CHAMPION
CHALLENGER
ARCHIVE
DIAGNOSTIC_ONLY
NON_SUBMITTABLE
```

Preserve at most one active champion and one active challenger.

The final report must name exactly one next action tied to the largest remaining externally relevant defect. Do not propose a new broad framework.

## 45. Explicit prohibitions

Do not:

- stop after each probe to perfect it;
- create separate contracts or branches for individual blocks;
- build another deterministic agent from scratch;
- build full information-set MCTS;
- build a universal multi-deck search framework;
- run an architecture or seed tournament;
- use an external RL framework;
- use hidden simulator information in submitted decisions or training inputs;
- train only against the current policy;
- permit game-zero curriculum promotion;
- trust summaries over raw evidence;
- submit a package with unresolved legality, hidden-info, identity, timeout, permission, or hash defects;
- omit code needed to reproduce a failure;
- rewrite historical statuses;
- claim the last pipeline stage is best merely because it is last.

## 46. Definition of done

c017 is done when the 72-hour campaign ends and all of the following are true:

- the previous Mega Lucario baseline has an accepted external submission reference or a fully evidenced unavoidable failure;
- the complete vertical pipeline has executed at least once;
- one consolidated repair pass has been completed or explicitly unnecessary;
- the scaled run and common final panel are complete within budget;
- the strongest trustworthy stage has been submitted when eligible;
- every probe, raw artifact, code version, checkpoint, config, package, submission response, taint, and failure required above is preserved;
- full final source and milestone source snapshots are included and validated;
- Git commits and final reports are complete;
- the final status is honest.
