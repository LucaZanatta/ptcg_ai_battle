# c018 — Complete Integrated Search, Learning, and Curriculum Campaign

## 0. Executive mandate

c018 is a **new execution contract**, not an amendment to c017.

c017 remains preserved as an honest failed/partial experiment. c018 starts from the final c017 committed state, reuses only valid infrastructure, replaces the invalid search and curriculum implementations, and executes the intended vertical system with real simulator successors, real training games, real optimizer updates, and real candidate packages.

The integrated target is:

```text
accepted frozen baseline from c017
→ official-API forward search
→ real search-labelled trajectories
→ supervised policy/value distillation
→ actual baseline-anchored PPO curriculum
→ policy/value-guided forward search
→ common final panel
→ automatic submission of the strongest trustworthy post-baseline candidate
```

This is one large integration-first campaign. Probes provide visibility and taint tracking; they are not miniature approval projects. The first thin end-to-end run must execute every interface early. After that, perform one consolidated repair pass, scale the trustworthy path, and submit the strongest trustworthy stage.

The contract must not report simulated counters, planned opponent draws, unchanged checkpoints, static action bonuses, or file existence as evidence that search or training occurred.

---

## 1. Winning hypothesis

> The exact official Mega Lucario baseline provides legal deck-specific routine play and a stable fallback. The official native search API can produce real successor states for bounded current-turn planning. Real search decisions can supervise a compact policy/value model. Actual PPO games under a baseline-anchored self-play curriculum can improve long-horizon play without collapsing broad-field strength. Policy/value guidance can then improve the same real forward-search planner. The best trustworthy intermediate or final stage should produce a package-safe external challenger stronger than the frozen baseline or the Dragapult control.

The contract is allowed to finish with heuristic search as the best candidate. It is not required to promote the most sophisticated stage. It is required to implement the intended system honestly and submit the strongest trustworthy post-baseline candidate when one exists.

---

## 2. Non-negotiable corrections from c017

### 2.1 Real search definition

A c018 search node is valid only when its successor observation was produced by the official native search interface:

```python
search_begin(...)
search_step(search_id, select)
search_release(search_id)
search_end()
```

`env.clone()`, a static option-type score, a baseline action ranking, or a handcrafted bonus table is **not forward search**.

At least one search trace must contain:

- one root from `search_begin`;
- at least two distinct child states from `search_step` when alternatives exist;
- at least one line of depth greater than one atomic decision;
- simulator-produced successor observations and legal options;
- correct release/end lifecycle evidence.

Do not conclude that forward search is impossible because `kaggle_environments.env.clone()` shares native state. That mechanism is prohibited for c018 search.

### 2.2 Real training definition

A c018 curriculum game exists only when a real simulator game completed and its transitions were consumed by an optimizer update.

A training stage may report `TRAINED` only when all are true:

```text
actual_completed_games > 0
optimizer_steps > 0
checkpoint_hash_after != checkpoint_hash_before
finite policy/value losses exist
```

Randomly drawing opponent categories, incrementing a counter, evaluating an unchanged checkpoint, or copying the same checkpoint under new filenames is not training.

### 2.3 Real guided-search definition

Policy/value-guided search exists only when:

- the policy changes branch ordering or pruning inside real `search_step` trees;
- the value model evaluates simulator-produced leaf states;
- baseline/heuristic fallbacks remain available;
- identical-tree or fixed-root probes show which rankings changed.

A learned policy acting alone may be a separate candidate, but it is not guided search.

### 2.4 c017 data trust

Treat c017 depth-zero search labels, the c017 distilled checkpoint, and the c017 curriculum reports as **diagnostic-only**.

Do not use c017 search labels as trusted training targets. Do not continue the c017 model as though it were a valid search-distilled initialization unless a small explicit ablation shows value; default to fresh initialization or a previously valid c011/c013 encoder initialization.

---

## 3. Fixed user decisions

1. c018 is a full continuation/completion campaign, not a narrow patch.
2. Build the full vertical system in one contract.
3. Use the official native search API for all claimed forward search.
4. Run a thin end-to-end real-output smoke before optimization.
5. Probes are non-blocking by default; downstream execution may reveal upstream defects.
6. Failed probes taint dependent artifacts instead of automatically stopping the campaign.
7. Only submission-safety defects block submission of an affected candidate.
8. Perform at most one consolidated repair pass after the first complete smoke.
9. Use actual simulator games and optimizer updates for the curriculum.
10. Increase self-play based primarily on performance against the frozen baseline, with broad-field and reliability guards.
11. Preserve and rank every credible intermediate stage.
12. Submit the strongest trustworthy post-baseline stage, not necessarily the last stage.
13. Include the complete code, focused source bundle, milestone source snapshots, raw probes, traces, trajectories, checkpoints, configs, packages, hashes, and Git evidence under `results/`.
14. Do not silently reduce the campaign to a tiny demonstration. If minimum execution budgets cannot be met, report `BUDGET_NOT_EXECUTED` and the contract cannot be `PASS`.
15. Do not create another RL framework, universal simulator, generic multi-deck MCTS platform, or architecture tournament.

---

## 4. Starting state and Git

### 4.1 Expected parent

Expected parent branch:

```text
contract/c017_end_to_end_search_learning_curriculum_campaign
```

The c017 artifacts contain a final-HEAD discrepancy:

- c017 `STATUS.json` reports `6e60056340c5656dd11e1930a060d9b9d99a43de`;
- c017 `results/git/final_head.txt` may report `930b8f9cfb5c4c369255db66b84db95c362f3060`.

Do not blindly trust either file. Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --all --decorate -25 --oneline
```

Read c017 `STATUS.json`, `SUMMARY.md`, source bundle, Git log, and c017 commits. Resolve the actual latest c017 commit that contains the completed c017 code and result-generation changes. Record the discrepancy and the chosen parent in:

```text
results/git/c017_parent_resolution.md
results/git/parent_candidates.json
```

Create:

```text
contract/c018_complete_integrated_search_learning_curriculum_campaign
```

from that resolved c017 commit.

Commit messages begin with `c018:`.

Do not reset, clean, rebase, force-push, delete unrelated files, or absorb unrelated dirty work.

### 4.2 Historical immutability

Everything under c005 through c017 is read-only.

Do not modify historical contracts, historical result directories, submitted archives, public-source snapshots, checkpoints, or prior reports.

Prefer c018-specific files such as:

```text
tools/c018_*.py
cg/c018_*.py
tests/test_c018_*.py
```

Shared modules may be extended only when necessary and only with regression tests preserving earlier behavior.

---

## 5. Baseline anchor and prior submission

The frozen baseline is the exact c017-submitted official Mega Lucario package.

Expected evidence:

```text
candidate: official_mega_lucario
submission reference: 55011215
baseline package: submission_J_official_mega_lucario_baseline.tar.gz
source main SHA-256: ab8563b67b88b3666c2ff9c308505085a84fdac676c194c5b484d8544478c3b2
deck SHA-256: 406e2e9bd6ae82b8008b16ee64ffcbb58e4a50cd6bc36e33ae655456c6b9afee
```

Reverify the package, source, deck, attribution, and accepted submission reference. Poll and record current score/status snapshots when available.

Do **not** submit the identical baseline again unless the prior accepted reference or package is missing/invalid. The c017 baseline submission satisfies the “submit previous baseline” requirement. c018 must preserve it as:

- fixed deterministic fallback;
- fixed curriculum anchor;
- local comparator;
- external calibration point.

Required outputs:

```text
results/baseline/baseline_verification.json
results/baseline/baseline_package_manifest.json
results/submissions/baseline_existing_submission.json
results/submissions/status_snapshots.jsonl
```

---

## 6. Time, compute, and upload envelope

Hard maximum: **72 hours**, including up to two overnight runs.

Use the available RTX 5070 and custom PyTorch/CUDA stack directly.

Maximum c018 uploads: **two post-baseline submissions**:

1. trusted heuristic-search candidate;
2. strongest trusted trained or guided-search candidate.

Obey the official daily limit when lower.

### 6.1 Minimum execution floors

The following are minimums for an overall `PASS`, unless a documented technical failure makes the stage impossible:

- at least 200 real `search_begin` roots;
- at least 5,000 real `search_step` calls across smoke and scaled search;
- at least 10,000 trusted search-labelled decisions before scaled distillation;
- at least 20,000 actual PPO curriculum games before claiming curriculum evidence;
- at least 1,000 optimizer steps total across supervised/PPO training;
- at least 600 real final-panel games across eligible candidates and meaningful opponents;
- at least one accepted post-baseline c018 submission.

Targets, when runtime permits:

- 30,000–60,000 trusted search-labelled decisions;
- 40,000–100,000 actual curriculum games;
- 1,200–2,000 final-panel games.

Do not substitute virtual counts for these floors. If a floor is missed, record the exact reason in `BUDGET_EXECUTION.json`; the contract may still be `PARTIAL` with useful candidates.

---

## 7. Integration-first execution doctrine

### Pass A — thin real-output vertical

Build and execute the entire pipeline with deliberately small but **real** outputs:

```text
official search root
→ multi-step successor trace
→ real search trajectory
→ supervised optimizer step
→ actual PPO game and optimizer step
→ guided-search inference
→ evaluator
→ package smoke
```

Suggested smoke scale:

- 20–40 real search roots;
- 200–500 `search_step` calls;
- 500–1,500 real search-labelled decisions;
- 1–2 supervised epochs;
- 200–500 actual PPO games;
- 20–50 guided-search games;
- 10 clean-extraction package games.

Do not optimize components during Pass A. The purpose is to expose interface defects.

### Pass B — consolidated diagnosis and repair

After Pass A:

1. rank all defects by downstream impact;
2. select at most three high-impact defects;
3. perform one consolidated repair pass;
4. rerun from the earliest affected milestone only.

Do not spend hours perfecting low-impact probe discrepancies.

### Pass C — scaled trustworthy path

Scale only artifacts that are trusted enough for their intended use.

A tainted teacher may still drive a diagnostic smoke. It may not drive large-scale training or promotion claims until repaired or explicitly isolated.

### Pass D — final comparison and submission

Rank every trusted package-safe stage. Submit the strongest eligible stage. A failed later stage must not suppress a strong earlier stage.

---

## 8. Probe and taint doctrine

Each probe records:

```text
PASS
WARN
FAIL_TAINTED
NOT_EXERCISED
```

Each artifact records:

- source commit/tree hash;
- config hash;
- deck and checkpoint hash;
- direct probe dependencies;
- `trust_status`: `TRUSTED`, `TAINTED`, `DIAGNOSTIC_ONLY`, `NON_SUBMITTABLE`;
- `tainted_by` probe IDs;
- allowed uses: debugging, training, evaluation, packaging, submission.

### 8.1 Default after a probe failure

Unless further execution is technically impossible:

1. save exact inputs, outputs, traceback, state hash, and source/config hashes;
2. mark dependent artifacts tainted;
3. apply only the smallest compatibility fallback required to continue;
4. finish the first vertical run;
5. defer substantive repair to Pass B.

### 8.2 Submission blockers

The following block submission of the affected candidate:

1. actual or suspected hidden-information leakage;
2. illegal actions or invalid action encoding;
3. crashes, memory corruption, leaks, or unacceptable match-time risk;
4. candidate/opponent identity corruption;
5. stale or wrong checkpoint used for promotion;
6. submitted package differs from evaluated source/config/deck/checkpoint;
7. unresolved reuse/attribution permission;
8. clean extraction/import failure;
9. search state lifecycle leaks that can accumulate during a match;
10. evidence claiming real search/training when the required native calls or optimizer updates did not occur.

Weak performance, low policy agreement, noisy value calibration, fixture misses, curriculum non-promotion, or moderate nondeterminism do not automatically stop the pipeline.

---

# CAMPAIGN A — OFFICIAL-API FORWARD SEARCH

## 9. Official search API adapter

Implement a c018 adapter around the official starter-kit API:

```python
from cg.api import (
    to_observation_class,
    search_begin,
    search_step,
    search_release,
    search_end,
)
```

Use the repository’s actual import path when different, but the native functions above are mandatory.

The adapter must:

- receive the exact observation passed to the agent;
- convert it to the official `Observation` dataclass without altering `search_begin_input`;
- construct legal predicted hidden-card lists from visible information and registered public deck/profile assumptions;
- call `search_begin` once per determinization/root;
- call `search_step` for every explored edge;
- preserve parent/child search IDs;
- release discarded states promptly;
- call `search_end` after each root search;
- expose successor observations, legal selections, terminal/turn transitions, and timings;
- never access simulator-private hidden state to construct predictions.

Implement explicit context management so cleanup occurs on success, timeout, exception, and fallback.

## 10. Hidden-state determinization

`search_begin` requires predicted hidden cards. Implement a visible-information-only determinization sampler.

### 10.1 Own cards

Use the fixed 60-card deck list and subtract cards legally visible to the agent:

- hand;
- active and bench;
- discard/lost/revealed zones;
- known searched/revealed cards;
- known prizes when revealed.

Sample remaining own deck and own prize assignments consistent with counts.

### 10.2 Opponent cards

Construct opponent predictions using only:

- observed opponent cards;
- public registered deck profiles;
- visible discard/board/reveal information;
- a deterministic archetype classifier;
- a generic legal fallback profile when confidence is insufficient.

Local evaluation may know the opponent identity for reporting, but promotion results must use a `BLIND_PROFILE` mode that does not directly pass the hidden true deck/hand/prize state into search.

Optional `KNOWN_PROFILE` results may be reported separately as an upper-bound diagnostic. They cannot decide promotion.

### 10.3 Determinization count

Smoke: one determinization.

Scaled search:

- routine decisions: one determinization;
- pivotal decisions: target 2–8 determinizations within the match-time budget.

Aggregate root action values across determinizations. Record seed, profile, sampled hidden lists’ hashes, and no raw secret data beyond what is allowed in local audit artifacts.

## 11. Candidate actions and pivotal decisions

The frozen baseline action is always included.

Search is focused on:

- Trainer/search target choices;
- bench choices;
- evolution choices;
- energy attachment targets;
- switch/retreat choices;
- gust and attack targets;
- attack selection;
- action ordering when complete-turn lines differ.

Routine and forced decisions may use the baseline immediately.

Generate at most 3–6 credible select arrays per node in scaled mode. Handle multi-select decisions correctly. Reuse existing action encoders only when identity and legality are verified.

## 12. Real bounded current-turn planner

Implement beam search or best-first search over real successor states.

Default scaled configuration:

- beam width: 8;
- node budget: 256–512 real `search_step` edges per pivotal decision;
- maximum action depth: 10–12 atomic decisions;
- stop at attack, end-turn, terminal, turn ownership change, depth, node, or time budget;
- deterministic tie-breaking in registered deterministic mode;
- transposition/dominance cache using visible successor state plus decision metadata;
- baseline fallback on timeout, unsupported effect, no valid result, or lifecycle error.

The planner must compare complete turn continuations. A root-only ranker cannot be named `SEARCH_HEURISTIC`.

## 13. Match-time controller

The competition uses a whole-match time budget. Implement:

- cumulative search time tracking per game;
- per-decision soft budget;
- hard reserve for future decisions and baseline fallback;
- adaptive reduction of determinizations/nodes when the game budget is being consumed;
- zero search at forced/routine decisions when unnecessary;
- recorded median/p95/p99 decision and full-match agent time.

Use conservative defaults initially, then use measured throughput to set a registered package configuration. Do not disable online search merely because the local environment exposes no per-action timeout.

## 14. Heuristic leaf evaluator

Every evaluated leaf must be a simulator-produced successor observation.

Record versioned feature definitions and weights. At minimum include:

- terminal win/loss;
- prizes taken this turn and remaining prize route;
- immediate knockout and game-winning lethal;
- attack damage relative to target HP/weakness/resistance;
- active attacker readiness and survival;
- backup attacker readiness;
- energy efficiency and stranded energy;
- remaining attackers, evolution pieces, energy, search, recovery, and gust resources;
- bench liability and likely prize concession;
- opponent visible next-turn threat;
- hand/board quality;
- future search/evolution options.

Use one registered weight set. The consolidated repair pass may change weights only when traces expose a high-impact evaluator error. No sweep.

## 15. Search probes

Run the following alongside the pipeline:

### P01 — native API root and lifecycle

- real `search_begin` succeeds on representative states;
- `search_begin_input` is preserved;
- child IDs are distinct where expected;
- every allocated state is released or ended;
- repeated searches do not leak memory or corrupt `agent_ptr`.

### P02 — real successor and branch proof

For representative pivotal states:

- at least two legal alternatives create distinct successor observations;
- at least one trace reaches depth >1;
- legal options evolve after actions;
- no trace is a static root-score list.

### P03 — hidden-information audit

- static scan of c018 search code;
- runtime record of every field used to build determinizations;
- blind-profile versus known-profile separation;
- no actual hidden simulator arrays passed into the submission-realistic search path.

### P04 — legality, replay, and baseline fallback

- selected first action replays legally through the real interface;
- baseline action is never accidentally pruned;
- timeout/exception/unsupported state returns the baseline action;
- zero illegal top-1 actions.

### P05 — tactical fixtures and traces

Include fixtures for:

- missed lethal;
- wrong attack/target;
- energy attachment route;
- evolution timing;
- bench liability;
- resource reservation;
- search-card sequencing.

Preserve root observation, candidate selects, real successor summaries, leaf feature decomposition, chosen line, nodes/depth/time, and acceptable/dominated line labels.

### P06 — throughput and match-time safety

Record roots/s, steps/s, memory, decision latency, full-match agent time, fallback rate, node counts, and determinization counts.

These probes determine trust and packaging eligibility but do not stop the first vertical smoke unless execution becomes impossible.

---

# CAMPAIGN B — REAL SEARCH CANDIDATE AND TRAJECTORIES

## 16. Heuristic-search candidate

Create:

```text
BASELINE_OFFICIAL_LUCARIO
SEARCH_HEURISTIC_REAL
```

`SEARCH_HEURISTIC_REAL` must use the official API and real multi-step successor states.

Evaluate with candidate-independent seeds and balanced seats against:

- Dragapult control;
- frozen baseline anchor;
- official Iono;
- official Mega Abomasnow;
- at least one additional already executable meaningful opponent when available without broad new infrastructure.

Promotion/submission signal for heuristic search:

- at least +3 percentage points on registered broad field with no serious matchup collapse; or
- at least +5 points on one pre-registered important matchup with field non-inferiority; or
- a major reduction in registered tactical errors with no broad-field regression and credible external information value.

Do not use safe-control or c014 thresholds as hard competitive gates. Safe control is reliability-only.

If trusted and package-safe, automatically build and submit the heuristic-search package as the first c018 upload. Record accepted reference and continue while score is pending.

## 17. Search-generated trajectory schema

Every real search-labelled decision must include:

- schema version;
- game/trajectory/decision ID;
- visible root encoding and root hash;
- opponent profile mode and determinization hashes;
- seat, turn, phase, decision type;
- exact legal options/select arrays and mask;
- baseline action;
- search-selected action;
- candidate root actions;
- aggregated action values across determinizations;
- candidate line summaries;
- normalized policy target and registered temperature;
- heuristic leaf values;
- search depth, nodes, latency, fallback reason;
- final game outcome;
- source/config/deck/checkpoint hashes;
- trust/taint metadata.

Split train/validation/test by whole games.

## 18. Trajectory trust and scale

Thin smoke trajectories may be tainted and used only to test interfaces.

Scaled distillation data must come from `TRUSTED` real search traces. Minimum 10,000 trusted decisions; target 30,000–60,000.

Generate against a mixture including:

- frozen baseline;
- Dragapult;
- official Iono;
- official Mega Abomasnow;
- heuristic search self-play when stable;
- historical promoted c018 policies later.

Safe control may be used only for legality/reliability.

## 19. Trajectory probes

### P07 — schema, legality, identity

- every selected action is legal;
- masks/options correspond to the same root;
- search IDs cannot be confused with game/action IDs;
- candidate/opponent identities are explicit;
- round-trip reconstruction succeeds.

### P08 — outcome and split integrity

- terminal outcomes reconcile with raw games;
- no game crosses train/validation/test;
- no hidden features enter the encoding;
- source/config hashes resolve to preserved code.

---

# CAMPAIGN C — POLICY/VALUE DISTILLATION

## 20. Model

Use the existing custom PyTorch/CUDA infrastructure. Do not add an external RL framework.

Build one compact shared-backbone model:

- policy head predicts the real-search action distribution under legal masking;
- value head predicts final outcome in `[-1, 1]`;
- optional auxiliary target may use normalized real-search leaf values;
- visible deck/opponent context may be used only when legal and reproducible.

No architecture or seed tournament. One registered model and one primary seed.

Do not default to the c017 distilled checkpoint. Start fresh or from a previously valid encoder initialization. Record the choice and rationale.

## 21. Supervised training

Train on trusted real-search trajectories.

Required logs:

- optimizer-step count;
- policy loss/KL or cross-entropy;
- value loss;
- entropy;
- gradient norms;
- learning rate;
- throughput;
- GPU utilization/memory;
- validation top-1/top-k and value metrics;
- pre/post checkpoint hashes.

Save initialization, best validation, final, optimizer, scheduler, scaler, RNG states, and exact config.

## 22. Distillation probes

### P09 — actual update proof

Require:

```text
optimizer_steps > 0
initial_hash != final_hash
finite gradients and losses
```

### P10 — reload and held-out metrics

- exact inference after save/reload;
- legal masked top-1;
- top-1/top-k/KL by decision category;
- value MSE/correlation/calibration versus constant baseline;
- no train/test game leakage.

Gameplay promotion is not inferred from imitation metrics alone.

---

# CAMPAIGN D — ACTUAL PPO CURRICULUM

## 23. PPO implementation

Continue from the best valid search-distilled checkpoint using the project’s existing custom PyTorch PPO/action stack.

Required mechanics:

- actual simulator rollouts;
- legal-action masks;
- clipped PPO policy objective;
- value loss;
- entropy bonus;
- optional KL anchor to the distilled policy;
- gradient clipping;
- exact checkpoint/resume;
- mixed precision only when stable.

Do not create a second training framework.

## 24. Frozen identities

Freeze and hash:

- `BASELINE_ANCHOR`: exact official Mega Lucario package;
- `DRAGAPULT_CONTROL`;
- `FIELD_IONO`;
- `FIELD_ABOMASNOW`;
- any additional fixed field opponent;
- distilled initialization;
- every promoted historical checkpoint.

Use identity-safe aggregation. Never positional-zip unordered worker results.

## 25. Curriculum schedule

Self-play means games against the latest candidate and frozen promoted c018 checkpoints.

| Stage | Self-play | Baseline anchor | Fixed field/historical | Promotion condition |
|---|---:|---:|---:|---|
| S0 Search-distilled | 0% | 50% | 50% | ≥50% vs baseline; field no worse than start by >3 pp; reliability clean |
| S1 Limited | 10% | 40% | 50% | ≥53% vs baseline; field no worse than best prior by >2 pp |
| S2 Moderate | 30% | 30% | 40% | ≥56% vs baseline; field at least baseline package field score |
| S3 Strong | 50% | 20% | 30% | ≥60% vs baseline; field improves best prior by ≥2 pp; beats one promoted checkpoint |
| S4 Maximum | 70% | 10% | 20% | optional; only when S3 remains broad-field stable |

Never use 100% latest-policy self-play.

Evaluate at least every 5,000 actual completed training games. Scaled evaluation target per checkpoint:

- 200 games vs baseline anchor;
- 300 games across fixed field;
- 100 games vs historical checkpoint when applicable;
- balanced seats and candidate-independent seeds.

No promotion at game zero. No policy compared with itself as evidence.

## 26. Conservative fallback schedule

If evaluation is temporarily unavailable or inconclusive, continue diagnostically with actual games under:

```text
0–10k games: 0% self-play
10k–25k: 10%
25k+: 20–30% maximum
```

Every transition records one reason:

```text
PERFORMANCE_PROMOTION
FALLBACK_SCHEDULE
SMOKE_ONLY
RECOVERY_AFTER_DEFECT
```

Only `PERFORMANCE_PROMOTION` supports a strategic curriculum claim.

## 27. Curriculum proof requirements

For every interval preserve:

- actual completed game IDs and raw outcomes;
- actual opponent identities and seat counts;
- planned versus actual mixture;
- rollout transitions consumed;
- optimizer-step counts;
- policy/value/entropy/KL losses;
- gradient norms;
- checkpoint hashes before/after;
- evaluation checkpoint path and content hash;
- promotion calculation and reason;
- current and historical opponent checkpoint IDs.

## 28. Curriculum probes

### P11 — real game/update proof

The validator must reject `TRAINED` when:

- no real raw games exist;
- optimizer steps are zero;
- checkpoint hash did not change;
- reported game counts are only planned draws.

### P12 — freshness and identity

- content-addressed checkpoint paths;
- no stale path-based hash cache;
- evaluation uses current weights;
- explicit candidate/opponent identities;
- no game-zero promotion;
- correct mean/median/significance arithmetic.

### P13 — exact continuation

Restore and verify:

- model, optimizer, scheduler, scaler;
- Python/global/NumPy/CUDA RNG;
- local generator;
- opponent sampler;
- curriculum stage;
- trajectory/rollout cursor.

### P14 — mixture and collapse

- planned versus actual opponents;
- policy entropy and repeated-action rates;
- illegal action rate;
- cross-play against prior checkpoints;
- field collapse detection.

---

# CAMPAIGN E — POLICY/VALUE-GUIDED REAL SEARCH

## 29. Candidate stages

Preserve at minimum:

1. `BASELINE_OFFICIAL_LUCARIO`;
2. `SEARCH_HEURISTIC_REAL`;
3. `POLICY_DISTILLED_REAL_SEARCH`;
4. `POLICY_CURRICULUM_BEST`;
5. `SEARCH_POLICY_ORDERED_REAL`;
6. `SEARCH_POLICY_VALUE_GUIDED_REAL`.

A stage that is unavailable or tainted receives an explicit `NOT_PRODUCED.json` or `NON_SUBMITTABLE.json`; it is not silently omitted.

## 30. Guidance integration

For real official-API search:

- policy logits rank or prune candidate root/child actions;
- baseline action remains included;
- value evaluates simulator-produced leaves;
- heuristic evaluator remains fallback and comparison;
- use one registered heuristic/value blend;
- preserve identical-root traces comparing heuristic and learned rankings.

Do not claim guidance when the model is only used as a standalone agent.

## 31. Guided-search probes

### P15 — identical-root guidance comparison

On the same roots and generated successor states, compare:

- heuristic ordering;
- policy ordering;
- heuristic leaf values;
- learned values;
- selected first action;
- final outcome where available.

### P16 — latency and fallback

Measure policy inference, value inference, native search steps, full decision, full match, fallback rate, and memory.

### P17 — gameplay comparison

Use identical seeds and seats to compare:

- baseline;
- heuristic search;
- distilled policy;
- best curriculum policy;
- policy-ordered search;
- policy/value-guided search.

---

# CAMPAIGN F — FINAL PANEL, PACKAGING, AND SUBMISSION

## 32. Common final panel

Freeze before the final run:

- candidate identities and exact source/config/deck/checkpoint hashes;
- opponent identities;
- seed lists;
- seat assignment;
- game counts;
- scoring and tie-break rules;
- latency protocol.

Meaningful opponents:

- Dragapult control;
- frozen official Mega Lucario baseline;
- official Iono;
- official Mega Abomasnow;
- at least one additional executable current/meta benchmark when already available.

Safe control is reliability-only.

Minimum total final-panel games for `PASS`: 600. Target: 1,200–2,000.

Rank only trusted package-safe candidates by:

1. broad meaningful field;
2. Dragapult;
3. baseline anchor;
4. cross-play against strongest c018 stage;
5. tactical errors;
6. full-match latency and fallback rate.

Do not use c014/c015 or safe-control arbitrary thresholds as blockers.

## 33. Package candidates

Build clean inference packages for every eligible stage that could plausibly be selected:

- heuristic real search;
- best standalone trained policy;
- best guided real search.

Each package must be validated from clean extraction and tied to exact source/config/deck/checkpoint hashes.

Required package tests:

- imports without repository path leakage;
- no network access;
- all dependencies included/permitted;
- zero illegal actions/exceptions/timeouts in at least 100 both-seat games across meaningful opponents;
- full-match time safety;
- submitted archive hash equals evaluated archive hash.

## 34. Submission rules

### Submission 1 — heuristic real search

Automatically submit when:

- real official-API multi-step search is proven;
- trust and package gates pass;
- local evidence provides a meaningful improvement or credible high-information challenger signal.

Suggested archive:

```text
submission_K_c018_real_heuristic_search.tar.gz
```

### Submission 2 — strongest trained/guided candidate

Automatically submit when it is trusted, package-safe, and meaningfully stronger than the strongest prior c018 stage.

Suggested archive:

```text
submission_L_c018_guided_search.tar.gz
```

A score may remain `PENDING`; accepted reference completes the submission step.

Do not upload a candidate known to be catastrophically weaker or tainted by a submission blocker.

---

## 35. Required results tree and full code

All c018 evidence lives under:

```text
contracts/c018_complete_integrated_search_learning_curriculum_campaign/results/
```

Required structure:

```text
results/
  SUMMARY.md
  STATUS.json
  ACCEPTANCE_CHECKLIST.md
  DECISION_BOARD.md
  BUDGET_EXECUTION.json

  baseline/
  configs/
  integration/
  probes/
    P01_native_search_lifecycle/
    P02_real_successor_branching/
    P03_hidden_information/
    P04_legality_fallback/
    P05_tactical_fixtures/
    P06_search_latency/
    P07_trajectory_integrity/
    P08_outcome_split_integrity/
    P09_actual_distillation_updates/
    P10_model_reload_metrics/
    P11_actual_ppo_updates/
    P12_checkpoint_freshness_identity/
    P13_exact_continuation/
    P14_mix_collapse/
    P15_guidance_comparison/
    P16_guided_latency/
    P17_final_gameplay/
    P30_end_to_end_real_smoke/
    P90_evidence_validator/

  search/
    roots/
    traces/
    lifecycle/
    determinizations/
    latency/
    fixtures/
    raw_games/

  trajectories/
    schema.json
    manifests/
    representative_samples/
    trusted/
    diagnostic/
    integrity/

  models/
    distillation/
    curriculum/
    guided/

  training/
    configs/
    checkpoints/
    optimizer_states/
    logs/
    raw_rollouts/
    evaluations/
    curriculum_history.jsonl
    opponent_mix_history.jsonl
    resume_probes/

  final_panel/
  packages/
  submissions/
  failures/
  artifacts/
  git/

  source/
    complete_repository_source.zip
    c018_competition_source_bundle.zip
    git_diff.patch
    source_manifest.json
    hashes.sha256
    environment.txt
    dependency_lock.txt
    inspection/
    milestones/
      M00_parent/
      M01_real_search/
      M02_distilled/
      M03_curriculum/
      M04_guided_search/
      M05_submitted/
```

### 35.1 Complete repository source

`complete_repository_source.zip` must contain the final repository tree excluding only:

- `.git/`;
- virtual environments;
- caches;
- credentials/secrets;
- unrelated very large datasets.

### 35.2 Focused competition source bundle

`c018_competition_source_bundle.zip` must include:

- all c018 search API adapter code;
- determinization/archetype profile code;
- candidate generation and planner;
- heuristic evaluator;
- trajectory writer/reader;
- encoders and action representation;
- policy/value model;
- supervised trainer;
- PPO trainer and curriculum scheduler;
- evaluator and identity-safe aggregation;
- package builder and entrypoint;
- tests/probes;
- configs;
- exact deck list and attribution;
- source manifests and hashes.

### 35.3 Plain inspection copies

Copy the key c018 source files uncompressed under:

```text
results/source/inspection/
```

This is mandatory so ChatGPT can inspect the actual implementation directly without relying only on reports.

### 35.4 Milestone snapshots

Each milestone snapshot must tie code, config, model, trajectory, package, and result hashes together. The final submitted package must resolve to `M05_submitted` exactly.

---

## 36. Evidence validator

Implement a c018-specific content validator. It must fail on:

- stale c017/c016 contract identifiers in c018 final reports;
- `SEARCH` claims without real `search_begin/search_step` counts and successor traces;
- search nodes produced only by static scoring;
- `TRAINED` claims with zero optimizer steps, no raw games, or unchanged checkpoint hashes;
- planned opponent mix reported as actual games;
- duplicated checkpoint files counted as progression;
- hidden-information access in submission-realistic search;
- zero-denominator success rates;
- denominator changes hidden between raw and final reports;
- unordered result identity mapping;
- game-zero promotion or self-comparison;
- stale checkpoint promotion;
- package/source/config/deck/checkpoint mismatch;
- evaluated package differing from uploaded archive;
- skipped criteria counted as passed;
- missing full source bundles or inspection copies;
- modified historical contracts/results;
- overall `PASS` without an accepted post-baseline c018 submission;
- `PASS` when minimum real execution floors were missed without an allowed documented technical impossibility.

The validator must derive its claims from raw data, not trust `STATUS.json` or summary prose.

---

## 37. Acceptance criteria

### AC-01 — parent resolution, immutability, and baseline anchor

- resolve actual c017 parent safely;
- preserve c005–c017 immutably;
- verify baseline package and accepted reference 55011215;
- record Git and baseline evidence.

### AC-02 — real official-API forward search

- use `search_begin/search_step/search_release/search_end`;
- produce multi-step real successor traces;
- implement blind-profile determinizations, lifecycle cleanup, fallback, and time control;
- no hidden-information leakage.

### AC-03 — integrated real-output smoke and probes

- execute search → trajectories → supervised update → actual PPO update → guided search → evaluator → package smoke;
- record all probe statuses and taint dependencies;
- complete one consolidated repair pass.

### AC-04 — trusted heuristic-search candidate

- evaluate real heuristic search against the frozen panel;
- preserve raw games and tactical traces;
- package and automatically submit when the registered trust/competitive gate passes;
- otherwise record an honest non-submission decision.

### AC-05 — real search trajectories and supervised policy/value training

- minimum trusted trajectory scale when technically feasible;
- real optimizer updates and changed hashes;
- CUDA use, reload, legality, held-out policy/value evidence.

### AC-06 — actual PPO curriculum

- actual simulator games and optimizer updates;
- baseline-anchored self-play stages with field guards;
- checkpoint freshness, identity-safe evaluation, exact continuation, actual mixture logs;
- no virtual game counters.

### AC-07 — guided search, final panel, package, and submission

- integrate policy/value with real search when feasible;
- freeze and run common final panel;
- package eligible candidates;
- automatically submit the strongest trusted post-baseline stage when meaningful;
- accepted reference may have score `PENDING`.

### AC-08 — full source, raw evidence, Git, and validator

- complete repository source zip;
- focused c018 source bundle;
- plain inspection copies;
- milestone snapshots;
- all raw probes/games/traces/rollouts/logs/checkpoints/configs/packages/submission responses;
- content validator passes its own consistency audit;
- honest final status and one next action.

---

## 38. Final status semantics

### `PASS`

Requires all of:

- real official-API multi-step search implemented;
- actual supervised and PPO optimizer updates with changed checkpoints;
- minimum real execution floors met or exceeded;
- no unresolved submission blocker in the selected candidate;
- at least one accepted post-baseline c018 submission;
- full source/evidence bundle complete;
- evidence validator passes;
- all acceptance criteria genuinely pass.

### `PARTIAL`

Use when the integrated campaign produced useful trusted intermediate code/evidence or a credible submission but one or more required advanced stages failed, were tainted, or minimum floors were missed.

Examples:

- trusted heuristic search submitted, but PPO failed;
- real search works offline but online package is unsafe; distilled policy submitted;
- guided search tainted, heuristic search remains strongest;
- training is real but does not improve gameplay.

### `FAIL`

Use when:

- official-API search was not genuinely implemented;
- training remained virtual or unchanged;
- no trustworthy post-baseline candidate exists;
- evidence/source is insufficient to audit;
- or results falsely claim search/training/submission success.

Do not convert failed required criteria into `N/A` passes.

---

## 39. Decision board

Final board must classify every stage as:

```text
CHAMPION
CHALLENGER
ARCHIVE
DIAGNOSTIC
NON_SUBMITTABLE
```

External evidence outranks local elegance.

Until a post-baseline c018 agent proves otherwise:

- Dragapult remains the temporary externally confirmed champion/control;
- official Mega Lucario remains a calibration challenger;
- c017 depth-zero ranker and distilled policy remain diagnostic/archive.

The final report must choose exactly one next externally relevant action. It may not recommend a generic infrastructure contract.

---

## 40. Prohibited behavior

Do not:

- modify c017 results to make c018 look complete;
- use `env.clone()` as c018 forward search;
- call a static action bonus ranker search;
- train at scale on c017 depth-zero labels;
- report planned draws as training games;
- create fake checkpoint progress by copying files;
- promote from stale or same-policy game-zero evaluation;
- access actual hidden state in the submission-realistic search path;
- create full information-set MCTS, generic multi-deck framework, or new RL framework;
- run architecture/seed sweeps;
- stop the first integrated smoke for non-catastrophic probe perfection;
- silently shrink the campaign below minimum floors and still claim `PASS`;
- submit a known catastrophically weak or tainted candidate;
- omit code, raw evidence, or milestone source required for audit.

---

## 41. Required final summary

`SUMMARY.md` must state plainly:

1. whether real official-API forward search ran;
2. actual `search_begin` and `search_step` counts;
3. whether multi-step search improved the baseline;
4. trajectory scale and trust status;
5. actual supervised optimizer steps and checkpoint change;
6. actual PPO games, optimizer steps, self-play stages, and promotions;
7. whether guided search genuinely used policy/value inside real trees;
8. final-panel results for every trusted candidate;
9. every upload reference and latest score/status snapshot;
10. strongest trustworthy package;
11. exact failed/tainted stages;
12. Champion/Challenger/Archive board;
13. exactly one next externally relevant action.

