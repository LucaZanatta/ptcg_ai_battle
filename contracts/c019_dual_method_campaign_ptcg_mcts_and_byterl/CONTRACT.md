# c019 — Dual Method Campaign: PTCG-ISMCTS and PTCG-ByteRL

## 0. Executive mandate

c019 is a new large execution contract. It implements two recognizable, method-faithful card-game AI pipelines as independent PTCG agents:

```text
A. Hearthstone-derived imperfect-information MCTS
B. ByteRL-derived end-to-end recurrent RL + OSFP
```

The existing c018 project code is retained only as shared simulator, evaluation, packaging, submission, and evidence infrastructure. Replace its defective “search” and “curriculum” blocks; do not continue their checkpoints or labels.

The pure branches must remain independent:

```text
PTCG observation/API ──┬── PTCG-ISMCTS ── standalone package/submission
                       └── PTCG-ByteRL ── standalone package/submission
```

While the pure branches execute, implement only small switchable adapters that allow the project pipeline to consume proven outputs later. Hybrid work must not delay pure agents or become a third research program.

## 1. Winning questions

c019 answers three concrete questions:

1. Does a faithful imperfect-information PUCT/MCTS agent using the official forward API beat the frozen deck-specific baseline?
2. Does a faithful single-machine ByteRL/OSFP adaptation learn a strong fixed-deck PTCG policy from scratch?
3. Do ByteRL priors or values improve the MCTS branch cheaply enough to justify later hybrid work?

The contract must not answer these questions with implementation names, file existence, training loss alone, or weak proxy controls. It requires real common-panel gameplay and external submissions when credible.

## 2. Starting state and Git

Expected parent branch:

```text
contract/c018_complete_integrated_search_learning_curriculum_campaign
```

Expected c018 final commit:

```text
4cbae35888b21cbfccb6ebf4f5f5bfc5e05bd757
```

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --all --decorate -40 --oneline
```

Read c018 STATUS, SUMMARY, source bundles, final panel, defects, and commits. Resolve the actual latest c018 code/result-generation parent and record all candidates in `results/git/parent_resolution.md`.

Create:

```text
contract/c019_dual_method_campaign_ptcg_mcts_and_byterl
```

Commit messages begin with `c019:`.

Do not reset, clean, rebase, force-push, delete unrelated files, or modify c005-c018 artifacts.

Prefer c019-specific files:

```text
tools/c019_*.py
cg/c019_*.py
tests/test_c019_*.py
```

Shared changes require regression tests.

## 3. Required source study before implementation

Read every source in `references/SOURCE_REFERENCES.md` and create:

```text
results/method_fidelity/source_snapshot_manifest.json
results/method_fidelity/method_translation.md
results/method_fidelity/ptcg_adaptations.json
```

`method_translation.md` must map source components to PTCG components line by line:

```text
Hearthstone hidden state → PTCG hand/deck/prize determinization
Hearthstone MCTS tree → official search_begin/search_step tree
ByteRL masked end-to-end action → PTCG dynamic legal-option scorer
ByteRL actor-learner → local CPU actors + RTX 5070 learner
ByteRL OSFP historical models → immutable PTCG checkpoint population
```

Do not begin scaled runs until the thin method-fidelity smokes exist, but do not spend more than four hours on reading/reporting before coding.

## 4. Fixed deck/base

Both pure branches use one frozen deck to separate method quality from deck changes.

Default:

- exact official Mega Lucario deck/package already submitted under reference `55011215`;
- original official agent remains local comparator and MCTS rollout/prior source.

A different existing baseline may replace it only under the two-hour rule in `DECISION_RULES.md`. No new deck implementation or deck tuning occurs in c019.

Record:

```text
results/common/deck_freeze.json
results/common/baseline_manifest.json
```

## 5. Time, compute, and concurrency

Hard maximum: **96 hours**, including at most three overnight runs.

Intended effort/compute allocation:

- MCTS: 40%
- ByteRL: 40%
- hybrid adapters: maximum 15%
- final packaging/evidence: minimum 5%

Use CPU/GPU concurrently when safe:

- ByteRL learner on RTX 5070;
- calibrated actor workers on CPU;
- MCTS implementation/evaluation on CPU when actor load leaves capacity;
- avoid oversubscription by recording actual CPU utilization, games/s, queue latency, MCTS nodes/s, and GPU utilization.

Do not wait for ByteRL to finish before evaluating/submitting MCTS. Do not wait for MCTS before beginning ByteRL.

## 6. Integration-first schedule

### Hours 0–4 — parent/source/deck/shared interface

- resolve parent;
- freeze deck/base;
- snapshot sources;
- implement/verify canonical observation and legal-action interfaces;
- prepare isolated output roots for both branches.

### Hours 4–16 — thin faithful smokes

MCTS smoke must show:

- legal determinization;
- branch-local policy memory;
- PUCT selection;
- non-root expansion;
- rollout;
- backup;
- multiple determinizations;
- clean native lifecycle.

ByteRL smoke must show:

- dynamic masked legal-option policy;
- recurrent unroll;
- actor behavior logits/version;
- V-trace numerical pass;
- UPGO numerical pass;
- optimizer update;
- one complete OSFP LP and historical-checkpoint decision using real games.

Continue both branches even when the other fails. Record taint and apply one concentrated repair pass per branch after both smokes exist.

### Hours 16–48 — MCTS v0 and ByteRL learning periods

- scale method-faithful MCTS and run common-panel screening;
- start ByteRL actor-learner continuously;
- complete multiple real OSFP learning periods;
- package/submit MCTS immediately when its gate passes.

### Hours 48–84 — scale strongest valid configurations

- MCTS: increase simulations/determinizations only within match-clock safety;
- ByteRL: continue actual LPs, payoff updates, historical promotions, and evaluations;
- build standalone ByteRL package at milestone checkpoints;
- implement hybrid priors/value adapters while CPU/GPU jobs run, capped by budget.

### Hours 84–96 — final common panel and submissions

- freeze protocols before results;
- evaluate baseline, MCTS, ByteRL, and eligible hybrid smoke candidate;
- build clean packages;
- submit each credible pure branch independently;
- finalize source/evidence validator and decision board.

## 7. Shared PTCG core

Implement one canonical shared interface only where both methods genuinely need it:

- visible observation canonicalization;
- legal-option canonicalization and round trip;
- card metadata/embedding inputs;
- current-player perspective transformation;
- game/trajectory IDs;
- evaluator identity and package entrypoints.

Do not build a generic multi-game framework.

The MCTS branch may use additional hidden-state priors/determinizations. The ByteRL branch must never receive hidden sampled state as observation.

## 8. Branch A — PTCG-ISMCTS

Implement every mandatory property in `METHOD_FIDELITY.md`.

### 8.1 State-consistent rollout policy

Refactor the frozen baseline’s module/global state into explicit cloneable branch memory. With search disabled, reproduce baseline action choices and comparable gameplay. Search overrides must update branch memory according to the action actually executed.

### 8.2 Legal information-set determinizations

Build a visible-information tracker from current observation and public logs. For every sampled opponent profile/deck:

- subtract revealed cards from a legal deck multiset;
- sample opponent hand/deck/prizes without replacement;
- sample own hidden prizes/deck order consistently;
- validate exact multiplicities/counts;
- reject impossible worlds.

Use multiple determinizations for pivotal decisions. The true local opponent hidden zones/deck must never be accessed in submission mode.

### 8.3 Real PUCT tree

Use the official API:

```python
search_begin
search_step
search_release
search_end
```

At every depth:

- selection via PUCT;
- progressive expansion of real legal actions;
- child successor from `search_step`;
- rollout/leaf evaluation;
- backup of value/visits.

No root-only branching. No hardcoded option index. No static action ranking presented as MCTS.

Initial registered configuration, subject to one latency calibration:

```text
c_puct = 1.5
max simulations per determinization = 128
initial determinizations = 4
max tree depth = 16 atomic decisions
rollout cutoff = attack/end-turn/terminal or budget
progressive widening k = 1.5, alpha = 0.5
```

The baseline action receives a prior advantage but every credible legal action retains nonzero exploration probability. Forced select contexts may expand all legal options.

### 8.4 Rollout and leaf value

Primary v0:

- branch-local baseline rollout;
- terminal outcome when reached;
- otherwise PTCG heuristic leaf features including prize route, lethal/KO, active and backup attacker readiness, energy route, critical resources, board liability, and visible threat.

Version/configure the evaluator. Do not tune a large weight search. Preserve score decomposition in traces.

### 8.5 Chance and transpositions

Detect repeated action/state outcomes. Record stochastic outcome hashes. Implement chance/redirect handling sufficient to avoid overwriting distinct outcomes.

Use a transposition table only when a stable visible+determinization state hash is proven. Failure to implement transpositions does not invalidate v0; falsely claiming node sharing does.

### 8.6 MCTS execution floors

For method-fidelity completion:

- at least 5,000 searched live decisions;
- at least 500,000 total simulations or native successor expansions;
- at least 1,000 decisions using multiple determinizations;
- at least 100 complete sampled tree traces;
- at least 800 common-panel games for baseline versus MCTS combined;
- both seats and fixed identity-safe seeds.

When match-clock cost prevents these targets, report actuals and status `PARTIAL`; never lower counts silently.

### 8.7 MCTS package/submission

Build standalone `PTCG_ISMCTS_V0` package containing no ByteRL dependency. Submit immediately when `DECISION_RULES.md` gate passes. Score may remain pending.

## 9. Branch B — PTCG-ByteRL

Implement every mandatory property in `METHOD_FIDELITY.md`.

### 9.1 Scope

PTCG deck construction is frozen outside the model. Implement the battle policy only. This is the explicit PTCG adaptation of ByteRL’s end-to-end battle decision process.

The primary model starts from fresh random weights. Do not initialize from c018 distilled/PPO/search labels. Do not require MCTS data.

### 9.2 Observation/action network

Build a recurrent masked policy/value network:

- card embeddings and scalar features;
- own visible hand/active/bench/discard/prize counts;
- opponent visible active/bench/discard and counts;
- damage, HP, energy, status, tools, stage, positions;
- current turn and selection context;
- current legal options with typed references;
- LSTM hidden size 256;
- dynamic legal-option logits;
- value head.

The simulator’s sequential selection contexts are the autoregressive decomposition. Maintain recurrent state across atomic decisions and reset only at correct boundaries.

### 9.3 Actor-learner

Implement custom PyTorch CPU actor/GPU learner:

- versioned behavior policies;
- FIFO queue;
- fixed-length recurrent unrolls with burn-in when needed;
- behavior logits/probabilities;
- V-trace target;
- UPGO auxiliary loss;
- V-trace/PPO-clipped policy objective described in the Hearthstone paper;
- value and entropy losses;
- gradient clipping and finite checks;
- sample reuse 2.

Start from source hyperparameters in `METHOD_FIDELITY.md`. Calibrate batch size/actor count once for the RTX 5070 and 12-core CPU. Record every deviation.

### 9.4 OSFP

Implement Algorithm 1 structure from the source:

- immutable `H`;
- actual learning periods;
- current self-play probability `p`;
- payoff-driven sampling from `H`;
- actual G/C updates;
- threshold `xi`;
- forced add after max LP count;
- payoff tables and promotion history.

Register one payoff sampling function before scaled training. Predetermined self-play stage percentages are prohibited.

### 9.5 ByteRL execution floors

For method-fidelity completion:

- at least 60,000 actual simulator games;
- target 120,000–200,000 when throughput permits;
- at least 20,000 optimizer steps;
- at least 5 complete OSFP learning periods;
- at least 2 immutable historical checkpoint additions, one of which should be performance-based when learning succeeds;
- at least 1,000 actual games involving historical checkpoints;
- at least 800 common-panel/final checkpoint evaluation games across ByteRL milestones;
- complete actor staleness/importance-ratio and loss logs.

If performance never triggers promotion, forced OSFP additions may satisfy implementation evidence but not strategic convergence evidence.

### 9.6 ByteRL package/submission

Build standalone `PTCG_BYTERL_V0` package with recurrent inference and exact state reset. It must not depend on MCTS or search API.

Submit immediately when the ByteRL credibility gate passes. Do not upload a catastrophically weak model for calibration.

## 10. Existing pipeline and lightweight hybrid adapters

While pure branches run, replace c018 fake block interfaces with proper switchable providers:

```text
MCTS engine = c019 PTCG-ISMCTS
policy/value provider = c019 PTCG-ByteRL
opponent scheduler = c019 OSFP
```

Allowed c019 hybrid tests:

1. ByteRL priors in MCTS with heuristic leaf value.
2. ByteRL leaf value with baseline priors, only after calibration passes.
3. Combined priors/value only if 1 or 2 helps.

MCTS visit targets may be written to schema, but c019 does not require training ByteRL from MCTS data.

Hybrid implementation+debug+evaluation is capped at 15% of campaign resources and one repair pass. It must not delay pure packages/submissions.

## 11. Common evaluation panel

Freeze before final results.

Required opponents:

- exact frozen baseline;
- Dragapult control;
- official Iono;
- official Mega Abomasnow;
- up to two already-executable strong permitted public/meta agents when available without new implementation.

Safe/random agents are reliability checks only and do not block promotion.

Use:

- candidate-independent fixed seeds;
- balanced seats;
- identity-safe aggregation;
- raw game records;
- Wilson or exact intervals;
- latency and fallback reports.

Primary ranking:

1. external score evidence;
2. common-panel field score;
3. direct score versus frozen baseline/Dragapult;
4. worst meaningful matchup;
5. package reliability and latency.

## 12. Probes, taint, and repair

Run all probes in `PROBE_MATRIX.md`.

A probe failure normally:

- records exact input/output/traceback;
- marks dependent artifacts tainted;
- does not stop the other branch;
- does not trigger a miniature redesign project.

Each pure branch gets one concentrated repair pass after its thin smoke. Later fixes are limited to submission blockers or a single high-impact correctness defect.

## 13. Packaging and submissions

Maximum c019 uploads: two, one per pure branch. Obey current official limits.

Do not resubmit identical Mega Lucario baseline.

Every submitted package must pass:

- clean extraction;
- isolated environment import;
- both-seat games;
- zero illegal actions/crashes/timeouts;
- package/repository parity;
- exact source/checkpoint/deck manifest;
- permission/attribution checks;
- cumulative time safety.

Continue result generation while ratings are pending.

## 14. Acceptance criteria

### AC-01 — Parent, sources, deck, and shared interface

Parent resolution, source snapshots, clean-room/license records, method translation, same-deck freeze, canonical action/observation round trip.

### AC-02 — Method-faithful PTCG-ISMCTS

All mandatory MCTS fidelity properties implemented and runtime-validated; floors met or honestly partial.

### AC-03 — MCTS evaluation/package/submission decision

Common panel, standalone extracted package, honest promotion decision, automatic accepted submission when gate passes.

### AC-04 — Method-faithful PTCG-ByteRL model and learner

Dynamic recurrent policy/value, real actor queue, V-trace/UPGO/PPO-clipped updates, numerical tests, real games and changed checkpoints.

### AC-05 — Method-faithful OSFP

Historical pool, payoff sampling, G/C table, real LPs, threshold/forced promotion semantics, immutable checkpoints.

### AC-06 — ByteRL evaluation/package/submission decision

Milestone/final common panel, standalone recurrent package, honest promotion decision, automatic accepted submission when gate passes.

### AC-07 — Lightweight modular pipeline integration

Switchable priors/value/visit-target adapters, capped work, no contamination of pure branches, comparative smoke evidence.

### AC-08 — Full evidence, source, Git, validator, and decision board

Complete results schema, full source bundles and milestones, raw evidence, method-fidelity/evidence validator, honest status and roles.

## 15. Overall status

`PASS` requires:

- both pure methods pass method-fidelity validation;
- both are evaluated and package-feasible;
- at least one new c019 candidate is accepted as a submission;
- complete source/evidence validator passes.

`PARTIAL` applies when:

- one method is faithful and complete but the other is incomplete/invalid;
- both are faithful but neither is competitively credible enough to submit;
- a minimum execution floor is missed;
- evidence is complete enough to audit.

`FAIL` applies when:

- neither method is faithfully implemented;
- both branches are contaminated by shared invalid data;
- full code/raw evidence is missing;
- results cannot be audited;
- reports deliberately rename old c018 blocks as the requested methods.

Competitive status is separate from contract status. A method-faithful 20% agent is a competitive failure and must be reported as such.

## 16. Prohibited work

- no third algorithm;
- no new deck family or deck tuning;
- no continuation of c018 failed models;
- no MCTS training-label dependency in the primary ByteRL branch;
- no ByteRL dependency in pure MCTS;
- no full hybrid training campaign;
- no generic multi-game framework;
- no external RL framework;
- no “MCTS” without PUCT, non-root expansion, rollout, and backup;
- no “ByteRL” with ordinary PPO and scheduled self-play;
- no fake/virtual games, planned opponent counts reported as actual, unchanged checkpoints presented as progress, or package existence presented as strength.

## 17. Final deliverable and decision

Finish with:

- exact MCTS and ByteRL method-fidelity statuses;
- exact simulations/games/optimizer/LP/payoff counts;
- common-panel ranking;
- external submission references/statuses;
- Champion/Challenger/Diagnostic/Archive board;
- whether hybrid priors/value helped or hurt and why;
- exactly one next externally relevant action based on evidence.
