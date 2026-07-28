# c021 — Source-Faithful MCGS and ByteRL Transfer Campaign

## 0. Executive mandate

c021 must implement, run, and analyze both:

```text
A. MCGS_2019_OFFICIAL_SOURCE_PORT
B. ByteRL LOCM→Hearthstone B0→B3 reference ladder
```

The methods have different strategic roles:

```text
MCGS   → primary competitive agent and submission path
ByteRL → faithful compute-limited method/component-discovery path
```

Neither role permits omission or a superficial mock implementation.

The campaign must answer:

1. Can the official 2019 competition-winning MCGS system be ported with source-level fidelity to PTCG?
2. Does faithful MCGS improve decisions and field results relative to the frozen official baseline and c020 search?
3. Which published ByteRL stages and components transfer to PTCG at available scale?
4. Does any admitted ByteRL component measurably improve faithful MCGS?
5. Which candidate, if any, is strong and trustworthy enough to submit?

## 1. Starting state

Expected parent:

```text
contract/c020_forced_method_correction_and_hybrid_integration_campaign
```

Expected c020 final result-generation commit:

```text
267ca81399d6ea3fc85d155f57ada92b119edf77
```

Before editing, capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --all --decorate -80 --oneline
```

Resolve the actual latest legitimate c020 descendant and document the decision in:

```text
results/git/parent_resolution.md
```

Create:

```text
contract/c021_source_faithful_mcgs_and_byterl_transfer_campaign
```

Commit messages begin with `c021:`.

Do not rewrite history, clean the repository, delete untracked user files, modify c005-c020 evidence, or overwrite earlier packages/checkpoints.

## 2. Frozen controls

Freeze exact identities and hashes for:

```text
BASELINE_OFFICIAL_MEGA_LUCARIO
CHAMPION_C005_DRAGAPULT
C020_CORRECTED_MCTS_CONTROL
C020_CORRECTED_BYTERL_CONTROL
C020_H1_PRIOR_HYBRID_CONTROL
```

Record source, deck, model, package, configuration, commit, and prior evaluation identities in:

```text
results/controls/control_manifest.json
```

No control may be silently regenerated from different code.

## 3. Reference authority

### MCGS authority order

1. Official 2019 competition source archive.
2. Choe and Kim paper.
3. Official competition metadata/results.
4. Author/source behavior observed in controlled execution.
5. Explicitly documented inference only when the above are silent.

### ByteRL authority order

1. Verified author-released source/configuration, if one is discovered.
2. LOCM ByteRL paper.
3. Hearthstone ByteRL improvements paper.
4. Official COG competition material.
5. Primary V-trace/IMPALA reference where ByteRL papers defer to it.
6. Explicitly documented inference only when all primary sources are silent.

c019/c020 code is negative evidence and infrastructure reuse only. It is not an algorithmic authority.

## 4. Hardware policy

No hardware-driven algorithm simplification is permitted.

Allowed scale changes:

- actor count;
- number of games/samples;
- learning periods reached;
- wall-clock duration;
- concurrent MCGS workers;
- number of MCGS simulations completed;
- batch realization through microbatching/gradient accumulation when mathematically equivalent.

Forbidden method changes include every substitution listed in `FIDELITY_RULES.md`.

A faithful but under-scaled ByteRL run must be reported as:

```text
BYTERL_METHOD=PASS
BYTERL_SCALE=COMPUTE_LIMITED
```

when appropriate. It must not be falsely reported as either a full reproduction or a method failure.

## 5. Time and resource policy

Hard campaign ceiling: 120 elapsed hours, excluding only explicit user interruption.

Target effort:

- 55% MCGS source audit, port, conformance, scaling, field evaluation, deployment;
- 30% ByteRL B0→B3 implementation, training and analysis;
- 10% one-at-a-time transfer tests;
- 5% final packaging, source capture, reporting and submissions.

MCGS receives full CPU during decisive throughput and final-panel runs. ByteRL may train concurrently only when it does not invalidate MCGS timing measurements.

Do not wait for paper-scale ByteRL convergence. Run the faithful system to the attainable scale and report the trajectory honestly.

## 6. Mandatory execution phases

### Phase 0 — parent/control freeze and source acquisition

- freeze controls;
- retrieve official MCGS source archive and paper;
- record URLs, retrieval times, SHA-256, archive inventory, license/permission evidence;
- search primary author channels for any released ByteRL code/configuration;
- record the ByteRL source search even when negative;
- create the initial source-fidelity ledger and unresolved-choice ledger.

No MCGS coding before the official source archive has been inventoried.

### Phase 1 — environment and hardware characterization

Measure without changing algorithms:

MCGS:

- `search_begin/search_step/search_release/search_end` cost;
- simulation/forward-step throughput;
- state serialization/hash cost;
- process scaling at 1, 2, 4, 8 and 12 physical-core workers;
- memory growth per graph node/edge/chance outcome.

ByteRL:

- environment games/hour and decisions/second;
- actor scaling at 4, 8, 12 and optionally 16 processes;
- queue production/consumption;
- learner examples/second;
- GPU utilization and memory;
- checkpoint and log storage rate.

These measurements choose scheduling only.

### Phase 2 — MCGS official-source conformance port

Implement `MCGS_2019_OFFICIAL_SOURCE_PORT` exactly as specified in `MANDATORY_IMPLEMENTATION.md`.

Create a source map from every relevant official source class/function and paper equation to PTCG code, tests, runtime traces and adaptation classification.

Run controlled fixture conformance before broad games.

The reference branch preserves known source/theoretical limitations. Corrections belong only in a separately named branch.

### Phase 3 — ByteRL B0→B3 implementation

Implement one shared codebase with explicit cumulative stage toggles/checkpoints:

```text
BR0
BR1
BR1_5
BR2
BR3
```

Every stage difference must be machine-verifiable. ByteRL starts from fresh random weights and includes an end-to-end PTCG deck-construction meta-environment plus battle.

Run exact numerical and recurrent fixtures before training.

### Phase 4 — complete thin integrated smoke

Run one complete smoke containing:

- MCGS source acquisition and ledger;
- MCGS complete selection/expansion/simulation/backup decision;
- chance/sparse/damped sampling;
- graph reuse across atomic decisions;
- ByteRL deck construction;
- ByteRL battle actor;
- complete autoregressive action;
- recurrent unroll and learner replay;
- V-trace and UPGO update;
- one bounded OSFP period/promotion decision;
- BR0 through BR3 configuration-delta checks;
- one external evaluation game per frozen control;
- package import/entrypoint smoke.

### Phase 5 — one consolidated repair pass

Rank all root defects after the complete smoke. Fix at most six highest-impact defects in one consolidated pass.

Do not repeatedly polish one method while the other remains unexecuted.

### Phase 6 — scale and analyze both methods

MCGS:

- scale search budgets and worker counts;
- run registered search-budget curves;
- run broad external field evaluation;
- compare reference branch against no-search baseline and c020 search;
- build legal/corrected branch only after reference conformance.

ByteRL:

- train BR0→BR3 with controlled stage budgets;
- preserve all learning curves, queue diagnostics and population evidence;
- evaluate milestones externally, not only against ByteRL history;
- analyze policy priors, representation, action decoder, recurrence, OSFP, deck construction and value.

### Phase 7 — one-at-a-time transfer laboratory

Only after both parent fidelity gates pass:

1. ByteRL policy priors into MCGS.
2. ByteRL value only if value admission passes.
3. Other components only when a preregistered isolated test exists.

No full hybrid with multiple simultaneous changes.

### Phase 8 — final identity-safe evaluation and submissions

Register the final panel before running it.

Automatically package and submit only candidates that pass the registered credible gate. Do not submit tainted, source-mismatched, non-legal, or clearly dominated packages.

### Phase 9 — canonical final source and reports

Generate source only from the exact final Git commit. Regenerate final summaries after all final-panel and submission artifacts exist. Run the report consistency validator.

## 7. Required final statuses

```text
SOURCE_FIDELITY
EXECUTION
MCGS_COMPETITIVE
BYTERL_METHOD
BYTERL_SCALE
TRANSFER
PACKAGE
SUBMISSION
OVERALL
```

Each status must be one of `PASS`, `PARTIAL`, `FAIL`, with `COMPUTE_LIMITED` allowed only for `BYTERL_SCALE` and clearly defined in `DECISION_RULES.md`.

Omitting either MCGS or ByteRL forces `OVERALL=FAIL`.
