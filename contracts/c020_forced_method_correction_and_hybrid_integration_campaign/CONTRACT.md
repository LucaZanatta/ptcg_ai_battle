# c020 — Forced Method Correction and Hybrid Integration Campaign

## 0. Executive mandate

c020 is a new, integrated execution contract starting from c019. It does **not** choose a new strategy, a new deck, or a third method. It must correct the exact defects discovered in c019, rerun both corrected pure methods, and integrate the corrected components into the existing hybrid within the same campaign.

The fixed architecture is:

```text
A. Corrected PTCG information-set MCTS
B. Corrected PTCG ByteRL / OSFP
C. Modular hybrid using corrected A + B
```

Claude has no discretion to replace these methods with simpler substitutes, switch decks, continue defective checkpoints, omit mandatory hybrid modes, or submit unrelated official agents.

The campaign answers four questions:

1. Does corrected information-set MCTS, with a tactical PTCG evaluator and conservative overrides, beat the frozen Mega Lucario baseline?
2. Does corrected ByteRL, with slot-aware state, exact recurrent unrolls, autoregressive multi-select, and period-correct OSFP, learn a materially stronger policy than c019 ByteRL and approach the frozen baseline?
3. Do corrected ByteRL policy priors or values improve corrected MCTS?
4. Which trustworthy standalone or hybrid package is strongest and deserves immediate submission?

## 1. Starting state and immutability

Expected parent branch:

```text
contract/c019_dual_method_campaign_ptcg_mcts_and_byterl
```

Expected c019 final commit:

```text
55c14c83e8bddc0bd40f510605538735790ae20c
```

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --all --decorate -50 --oneline
```

Resolve the actual latest c019 code/result-generation commit. If a later c019 descendant exists, select it only when it is a legitimate c019 correction and document the resolution in:

```text
results/git/parent_resolution.md
```

Create:

```text
contract/c020_forced_method_correction_and_hybrid_integration_campaign
```

Commit messages begin with `c020:`.

Do not modify c005–c019 artifacts, rewrite history, reset unrelated work, rebase, force-push, clean the repository, or remove untracked user files.

Prefer c020-specific files:

```text
cg/c020_*.py
starter_kit/c020_*.py
tools/c020_*.py
tests/test_c020_*.py
```

Shared changes are allowed only when required and must have regression tests.

## 2. Frozen deck, controls, and checkpoints

The deck is fixed for c020:

- exact official Mega Lucario deck used in c019;
- exact official Mega Lucario agent as the frozen baseline and rollout/prior source;
- no deck edits;
- no alternative official-agent submission;
- no public-agent replacement;
- no anti-meta branch.

Freeze these controls before implementation:

```text
BASELINE_OFFICIAL_MEGA_LUCARIO
C019_PIMC_PUCT_CONTROL
C019_BYTERL_CONTROL
C019_HYBRID_CONTROL
```

Record exact source hashes, model hashes, configs, package manifests, and c019 gameplay summaries in:

```text
results/controls/control_manifest.json
```

The c019 ByteRL weights must **not** initialize corrected ByteRL. Corrected ByteRL starts from fresh random weights because its observation/action/recurrent semantics change.

## 3. Hard time box and resource allocation

Hard maximum: **96 hours**, including at most three overnight runs.

Target allocation:

- corrected MCTS: 35%;
- corrected ByteRL: 40%;
- mandatory hybrid H0–H4: 15%;
- final evaluation, packaging, submissions, source/evidence: 10%.

Use resources concurrently:

- GPU learner while CPU actors run;
- MCTS implementation/evaluation on reserved CPU capacity;
- hybrid adapters while ByteRL trains;
- no branch waits unnecessarily for the other.

Do not extend c020 into another contract merely because one block is almost working.

## 4. Integration-first execution order

The order below is mandatory.

### Phase 0 — source audit and forced-change map, maximum 3 hours

Read:

- all c019 source and results named in `references/C019_AUDIT_FINDINGS.md`;
- all algorithm sources in `references/SOURCE_REFERENCES.md`;
- `MANDATORY_CHANGES.md` and `IMPLEMENTATION_GUIDE.md`.

Create:

```text
results/implementation/forced_change_map.md
results/implementation/c019_to_c020_file_map.json
```

Every mandatory change must map to concrete source files, functions/classes, tests, runtime artifacts, and status.

Do not spend more than three hours writing analysis before coding.

### Phase 1 — implement all mandatory corrections

Implement every mandatory MCTS, ByteRL, OSFP, and hybrid change in `MANDATORY_CHANGES.md`.

No scaled run yet.

### Phase 2 — complete thin integrated smoke

Run one complete end-to-end smoke containing:

```text
corrected MCTS
→ corrected ByteRL actor/unroll/learner
→ one complete corrected OSFP period
→ H0, H1, H2, H3, H4 hybrid modes
→ common-panel smoke
→ package smokes
```

Probes run throughout. Most failed probes taint outputs but do not stop the complete smoke. Only failures that make execution technically impossible may cause a minimal compatibility fallback.

### Phase 3 — one consolidated repair pass

After the complete smoke, rank defects by downstream impact. Fix at most five root defects in one consolidated repair pass.

Do not repeatedly polish one block while the rest waits. Do not start a second repair cycle.

### Phase 4 — scale corrected pure branches in parallel

- scale corrected MCTS searches/evaluations;
- restart corrected ByteRL from fresh random weights and run real actors, V-trace/UPGO learner, OSFP periods, historical population, and milestone evaluations;
- package and submit a pure branch immediately when its gate passes.

### Phase 5 — mandatory corrected hybrid integration

Using the strongest corrected pure checkpoints/configurations, run H0–H4 exactly as specified in `MANDATORY_CHANGES.md`.

Do not invent extra modes or hyperparameter sweeps.

### Phase 6 — frozen final panel, packages, and submissions

Freeze the identity-safe panel before seeing final results. Compare:

```text
BASELINE_OFFICIAL_MEGA_LUCARIO
C019_PIMC_PUCT_CONTROL
C019_BYTERL_CONTROL
C019_HYBRID_CONTROL
C020_CORRECTED_MCTS
C020_CORRECTED_BYTERL
C020_H0
C020_H1
C020_H2
C020_H3
C020_H4
```

Build clean extracted packages for every credible materially distinct candidate. Automatically submit each candidate that passes its registered gate. Accepted submission reference closes the submission step even when score remains `PENDING`.

## 5. Branch A — corrected information-set MCTS

All requirements in `MANDATORY_CHANGES.md §A` are mandatory.

### Required c020 identity

The c019 method is retained and labelled honestly as:

```text
C019_PIMC_PUCT_CONTROL
```

The corrected method may use `ISMCTS` only when determinizations share information-set action statistics as required by A1. Otherwise status is `METHOD_FIDELITY_FAIL` and it cannot be promoted as corrected ISMCTS.

### Mandatory starting configuration

One latency calibration may reduce but not enlarge the following default:

```text
c_puct = 1.5
determinizations = 4
simulations per decision = 128 total across determinizations
max depth = 16 atomic actions
rollout stop = attack / end-turn / terminal / time budget
credible root actions = baseline + up to 3 alternatives
value perspective = root player
```

The configuration must respect the cumulative ten-minute match clock with safety margin.

### Required MCTS outputs

- shared information-set table;
- legal determinizations and rejection records;
- branch-local baseline memory traces;
- selection/expansion/rollout/backup traces;
- leaf feature decomposition;
- override confidence and veto reason;
- baseline-retained versus overridden outcomes;
- latency and native lifecycle logs;
- standalone package.

## 6. Branch B — corrected ByteRL / OSFP

All requirements in `MANDATORY_CHANGES.md §B` are mandatory.

### Fresh training

Start corrected ByteRL from a new registered random initialization. Do not load c019 ByteRL model or optimizer weights.

The c019 checkpoint remains a control only.

### Fixed source defaults

Unless one hardware calibration changes them before scaled training:

```text
recurrent hidden size = 256
gamma = 1.0
learning rate = 7e-5
entropy coefficient = 0.01
sample reuse = 2
V-trace rho/c clipping = source-paper values already registered in c019
OSFP current-self-play probability p = 0.6
OSFP performance threshold xi = 0.55
force-add only after more than c = 6 periods without valid promotion
```

Any calibration change must be registered once and not tuned after final-panel results.

### Required ByteRL outputs

- slot-aware observation schema;
- per-option target-linked encoding;
- autoregressive complete multi-select records;
- initial recurrent states at every unroll boundary;
- actor/learner same-state probability checks;
- V-trace/UPGO fixtures and live metrics;
- period-local OSFP G/C tables;
- frozen checkpoint evaluations and promotions;
- immutable historical population;
- actual completed opponent mix;
- standalone package.

## 7. Branch C — mandatory modular hybrid

The hybrid is mandatory in c020 but remains a small integration layer. It may not become a separate training framework.

Implement and evaluate exactly:

```text
H0 = corrected MCTS + baseline priors + tactical heuristic value
H1 = corrected MCTS + corrected ByteRL priors + tactical heuristic value
H2 = corrected MCTS + baseline priors + corrected ByteRL value
H3 = corrected MCTS + corrected ByteRL priors + corrected ByteRL value
H4 = corrected MCTS + corrected ByteRL priors + one preregistered heuristic/value blend
```

All search nodes must carry branch-local ByteRL recurrent state. Calling corrected ByteRL with `state=None` at every search node is forbidden.

H2–H4 must execute at smoke scale even when value admission fails, but they are non-promotable until the value admission test passes.

No H5. No search-data retraining loop. No MCTS-visit auxiliary training in c020 beyond schema production.

## 8. Probe and debugging policy

Probes are observability instruments, not eighteen blocking mini-contracts.

Probe statuses:

```text
PASS
WARN
FAIL_TAINTED
NOT_EXERCISED
```

The first full integrated smoke must continue after most probe failures. A downstream artifact records `tainted_by` probe IDs.

Only these defects block submission of the affected package:

- hidden-information leakage;
- illegal actions;
- crashes/timeouts or unsafe match clock;
- impossible determinizations used in decisions;
- evaluator/candidate identity corruption;
- package/source mismatch;
- unresolved reuse/license issue;
- recurrent/action-probability mismatch in the packaged ByteRL branch;
- submitted code differs from evaluated code.

A block may still execute diagnostically when its package is non-submittable.

## 9. Scale floors

A missed floor forces `PARTIAL`; it may not be called `PASS`.

### Corrected MCTS floors

- at least 5,000 live searched decisions;
- at least 500,000 real `search_step` expansions;
- at least 1,000 decisions with 4 legal determinizations attempted;
- at least 100 complete sampled tree traces;
- at least 500 recorded override opportunities and every actual override logged;
- at least 800 common-panel baseline-versus-corrected-MCTS games;
- at least 200 conservative-override ablation games.

### Corrected ByteRL floors

- at least 100,000 actual simulator training games after the corrected encoder/action/recurrent implementation;
- at least 30,000 optimizer steps;
- at least 6 complete corrected OSFP learning periods;
- at least 2 immutable historical additions from valid frozen-checkpoint evidence, unless no checkpoint reaches the registered threshold—in that case record zero honest promotions and force-add semantics separately;
- at least 2,000 games involving historical checkpoints;
- at least 1,000 evaluation games across milestones/common panels;
- at least 1,000 multi-select decisions when the environment naturally produces them, or every observed multi-select decision if fewer occur;
- recurrent initial state stored for 100% of mid-game unrolls.

### Hybrid floors

- H0–H4 all execute at smoke scale;
- H0–H4 each receive at least 200 final-panel games when promotable;
- non-promotable H2–H4 receive at least 40 diagnostic games each;
- every mode uses the exact same tree budget/seeds where comparison requires it.

## 10. Competitive gates and submissions

### Corrected MCTS gate

Eligible when all are true:

- method-fidelity status passes;
- package reliability passes;
- no hidden leakage;
- zero illegal actions/crashes/timeouts in package panel;
- baseline parity holds when search is disabled;
- field score is baseline +3 percentage points, or one important matchup is +5 without more than 2-point broad-field regression;
- conservative overrides show positive or non-negative value relative to retained baseline actions;
- match-clock margin is safe.

### Corrected ByteRL gate

Eligible when all are true:

- corrected semantic/recurrent/action probes pass;
- legal rate 100%;
- actual V-trace/UPGO updates and OSFP periods occurred;
- final checkpoint materially beats c019 ByteRL;
- final checkpoint beats its fresh initialization and at least two historical checkpoints, when available;
- field score is at least baseline +2 points, or direct score versus baseline is at least 55% without broad collapse.

### Hybrid gate

Hybrid compares against the stronger corrected pure parent, not merely the frozen baseline.

Eligible when:

- all used adapters pass admission;
- package reliability passes;
- field score is best pure parent +3 points; or
- important matchup is +5 without more than 2-point field regression; or
- strength is statistically/comparably retained with at least 30% lower search cost.

A more complex hybrid that only ties a pure parent at higher runtime is rejected.

### Submission behavior

Automatically upload every credible materially different package as soon as its gate passes. Do not wait for the other branch or the hybrid.

Do not submit official Iono, official Abomasnow, c019 controls, or any candidate known to fail its gate.

## 11. Acceptance criteria

### AC-01 — Parent, branch, controls, immutability

Correct parent resolved; c020 branch created; controls frozen; c005–c019 immutable; Git evidence complete.

### AC-02 — Forced MCTS corrections

Every A1–A8 change implemented and runtime-evidenced; c019 PIMC retained as control; corrected method label honest.

### AC-03 — Forced ByteRL corrections

Every B1–B8 change implemented; fresh weights; corrected recurrent/multi-select/V-trace/UPGO/OSFP semantics runtime-evidenced.

### AC-04 — Mandatory hybrid H0–H4

All five modes implemented, switchable, recurrent-state-consistent, and evaluated according to admission status.

### AC-05 — Complete smoke and one repair pass

Full vertical smoke executed before debugging; failures/taint preserved; exactly one consolidated repair pass documented.

### AC-06 — Scaled pure branches

MCTS and ByteRL scaled independently to their floors unless an explicit physical impossibility is proven; missed floor forces `PARTIAL`.

### AC-07 — Frozen common panel and ablations

Identity-safe registered panel compares controls, corrected pure branches, H0–H4, recurrent/override/evaluator ablations, and uses raw-game-derived results.

### AC-08 — Packages and automatic submissions

Every credible materially different candidate has clean extracted-package validation and automatic submission. Failed gates are recorded without substitute submissions.

### AC-09 — Complete code and raw evidence

All required source, milestone snapshots, models, checkpoints, traces, unrolls, payoff tables, raw games, configs, packages, hashes, and Git evidence exist under `results/`.

### AC-10 — Evidence validator and honest status

Validator detects the exact c019 defects listed in `references/C019_AUDIT_FINDINGS.md`; skipped/failed criteria cannot count PASS; final statuses separate execution, method fidelity, semantic correctness, competitive strength, and submission.

## 12. Prohibited substitutions and shortcuts

Claude may not:

- keep separate determinization trees and label them corrected ISMCTS;
- keep the c019 leaf evaluator;
- use option-zero or static continuation;
- omit branch-local memory;
- use unknown-opponent Dragapult default without explicit uncertainty mixture;
- override baseline without the conservative gate;
- pool active and bench Pokémon into one representation;
- omit energy types, positions, statuses, tools, or target references when available;
- continue c019 ByteRL weights;
- store only the first item/probability of a multi-select action;
- reset recurrent state at every mid-game learner unroll;
- compare target and behavior probabilities under different recurrent states;
- accumulate OSFP G/C across periods;
- promote from data generated by multiple evolving checkpoints;
- call ByteRL with `state=None` at every search node;
- skip H0–H4;
- add a fourth method;
- switch decks;
- submit unrelated official agents;
- turn probes into sequential mini-contract gates;
- run a second repair cycle;
- report a missing floor, skipped required mode, or failed semantic check as PASS.

## 13. Required final decision board

Assign:

```text
CHAMPION
CHALLENGER
DIAGNOSTIC
ARCHIVE
```

Roles follow external evidence first, then frozen-panel evidence. Package existence or sophistication does not confer a role.

The final report must state exactly:

- whether corrected MCTS improved over baseline and c019 MCTS;
- whether corrected ByteRL improved over fresh init and c019 ByteRL;
- which correction mattered most in each pure branch;
- whether H1, H2, H3, or H4 improved over H0 and the best pure parent;
- which packages were submitted and their references/statuses;
- exactly one next externally relevant action.

## 14. Overall status logic

`PASS` requires:

- all mandatory corrections implemented;
- H0–H4 executed;
- execution floors met;
- evidence validator passes;
- at least one new c020 candidate clears its gate and is submitted.

`PARTIAL` applies when the code/evidence campaign is substantially executed but a floor, semantic requirement, competitive gate, or submission is missed.

`FAIL` applies when the contract substitutes methods, omits major mandatory blocks, lacks auditable source/evidence, or the claimed execution is materially false.
