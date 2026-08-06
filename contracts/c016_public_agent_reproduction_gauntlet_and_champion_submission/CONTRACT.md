# c016 — Public-Agent Reproduction Gauntlet and Champion Submission

## 1. Objective

Use the exact c014 and c015 evidence to correct the project’s over-simplification error, reproduce several strong current public competition agents as faithfully as competition rules and source permissions allow, benchmark them on one common local gauntlet, select the strongest credible candidate by a pre-registered decision rule, package it, and submit one new champion candidate automatically.

This is an execution-and-selection contract. It is not another broad meta report, not another from-scratch priority agent, and not a Dragapult PPO continuation.

## 2. Winning-oriented success definition

The contract succeeds only when all of the following are true:

1. c014 and c015 are ingested from raw artifacts rather than trusted summaries;
2. current competition facts and public-agent sources are refreshed and snapshotted;
3. public-code reuse, attribution, and submission permission are resolved per candidate;
4. at least three materially different public candidates are reproduced and locally executable, unless fewer than three survive documented permission or technical gates;
5. all candidates are evaluated on the same pre-registered screening and final gauntlet;
6. the selected candidate passes both reproduction-integrity and competitive-selection gates;
7. the exact validated candidate archive is uploaded automatically and an accepted Kaggle submission reference is recorded;
8. the results are content-validated against raw evidence and cannot receive `PASS` merely because a package was legal or an upload was accepted.

A candidate score may still be `PENDING` when c016 closes. An accepted reference is mandatory for `PASS`, but an accepted reference alone is never sufficient.

If no candidate passes the competitive-selection gate, do not upload a weak package merely to complete the contract. Finish `PARTIAL` with the exact best candidate, failed gate, and next action.

## 3. Strategic correction fixed before execution

c014 and c015 proved that rapid packaging and submission now work. They did not prove competitive strength.

Treat the current evidence as follows:

- **Dragapult control:** temporary internal champion only because it remains the strongest confirmed package owned by the project; it is not a winning target.
- **c014 custom Archaludon/Cinderace:** operationally valid but competitively weak; preserve it as a control and as evidence that a simplistic rewrite does not reproduce a strong public Archaludon agent.
- **c015 custom Iono/Bellibolt:** archive as an implementation branch; its pre-registered anti-meta thesis was falsified locally and its reporting integrity was defective. Preserve it as a control and negative lesson only.
- **Anti-meta branch:** unassigned until a real current target is established from credible public or external evidence.

Do not modify historical c014 or c015 status files to rewrite history. Record the corrected strategic classification in new c016 evidence.

The central c016 rule is:

> Do not replace a rich public implementation with a smaller from-scratch priority table and call it a reproduction.

## 4. User decisions fixed before execution

- The main objective is winning the competition, not maximizing contract completion rate.
- Fast submissions remain important, but only when the submission is a credible competitive experiment.
- c016 may use exact public competition code only when reuse and submission are permitted and attribution requirements are satisfied.
- When exact code cannot legally be submitted, it may be used only as a local benchmark when permitted; one clean-room, semantically faithful reproduction may be built if feasible.
- No upload is required when every candidate fails the competitive gate.
- Claude Code is authorized and required to upload the exact selected c016 archive automatically once every mandatory gate passes.
- A pending public score is acceptable after an accepted c016 submission reference is recorded.

These decisions may not be weakened during execution.

## 5. Dynamic starting state and branch creation

c016 starts from the final committed c015 state.

Expected parent branch:

```text
contract/c015_anti_meta_deck_agent_v0
```

Expected c015 final HEAD from the uploaded results:

```text
6c5e602b820e20320b4775e379fc51928fcba9a9
```

Treat that hash as an expected value, not as permission to ignore the repository. Before editing, record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -12 --oneline
```

Locate c015’s exact final commit from its `STATUS.json` and Git history. If the current checkout is not that commit, move only by a safe branch checkout; do not reset, clean, rebase, or destroy unrelated work.

Create:

```text
contract/c016_public_agent_reproduction_gauntlet_and_champion_submission
```

from the exact c015 final HEAD. Commit messages must begin with `c016:`.

Preserve dirty and untracked user files. Do not absorb unrelated files merely to make Git clean.

## 6. Absolute immutability

Do not modify any file under c005 through c015. Read-only access is allowed.

Preserve exactly:

- all historical contracts and results;
- c014 and c015 submitted archives and submission records;
- all Dragapult checkpoints, controls, source bundles, and package artifacts;
- public-source snapshots already captured by c014;
- unrelated user changes.

c016 must create new files, new candidate work directories, new package names, and a new Kaggle description.

## 7. Scope and anti-overengineering constraints

c016 has one primary implementation change:

> Establish a strong public-agent baseline by faithful reproduction, common evaluation, and one champion submission.

Allowed:

- current public-source and competition-fact refresh;
- license/permission/attribution audit;
- exact extraction of public package payloads;
- isolated adapters required to run candidates in the local simulator;
- one clean-room faithful reproduction when direct submission reuse is not permitted;
- exact public search/expectimax logic when it is already part of a permitted candidate;
- common screening and final gauntlet;
- package validation and one automatic submission;
- content-aware evidence validation.

Forbidden:

- another simplified deterministic expert written from scratch;
- PPO, RL, distillation, residual learning, or any training run;
- inventing new MCTS, expectimax, rollout, or search logic for c016;
- generic multi-deck frameworks or universal rule engines;
- changing a candidate’s deck or strategy before its exact baseline is measured;
- combining multiple public agents into an ensemble;
- mass Claude labeling or Claude as a strategic teacher;
- optimizing c014 or c015 custom agents;
- more than one clean-room candidate implementation;
- more than one c016 Kaggle strategic submission, except one mechanical retry allowed by §19;
- claiming a public score, benchmark, or permission that cannot be evidenced.

Candidate-specific glue is acceptable. Do not build abstractions beyond what is necessary to execute the candidates.

## 8. Time box

Target one working day and one overnight maximum.

Suggested limits:

- current facts, source discovery, and permission matrix: maximum 2 hours;
- candidate extraction/reproduction: maximum 6 hours;
- screening, final gauntlet, package, submission, and reporting: remaining execution window.

Do not spend the full day debating tiny confidence intervals. Do not submit before the fidelity and competitive gates are complete.

# PHASE 0 — Ingest and correct the operating truth

## 9. Raw c014/c015 ingest

Read the full result trees:

```text
contracts/c014_public_meta_baseline_and_rapid_submission/results/
contracts/c015_anti_meta_deck_agent_v0/results/
```

Do not rely solely on `SUMMARY.md` or `STATUS.json`. Re-derive at minimum:

- exact package hashes and submission references;
- local matchup rates from raw matchup files;
- c014 public mining elapsed time;
- c015 delta-check elapsed time;
- c015 thesis threshold and actual score versus c014;
- c015 zero-opportunity Mechanism B issue;
- copied/null/mismatched c015 report fields;
- current Dragapult public score from the latest local submission listing;
- available public-source snapshots and embedded package payloads.

Create:

```text
results/artifacts/PRIOR_RESULTS_AUDIT.md
results/artifacts/prior_results_audit.json
results/test_logs/prior_results_ingest.txt
```

The new audit must classify each historical branch separately on:

- operational execution;
- evidence integrity;
- competitive strength;
- current branch role.

Do not alter historical files.

# PHASE 1 — Refresh public candidates and resolve reuse

## 10. Current competition-fact refresh

Verify through official or authenticated competition interfaces where available:

- exact competition slug and active category;
- deadline in UTC, JST, and Europe/Rome;
- submission package requirements;
- submission limits;
- runtime and file-size limits;
- current team submission list and latest scores;
- current public leaderboard top range;
- current public episode datasets and code notebooks.

Every fact must have:

- source URL or command;
- access timestamp;
- evidence label: `OFFICIAL_CURRENT`, `PUBLIC_REPRODUCIBLE`, `PUBLIC_CLAIM`, or `UNVERIFIED`;
- preserved source output or snapshot when permitted.

Required outputs:

```text
results/artifacts/CURRENT_COMPETITION_FACTS.md
results/artifacts/current_competition_facts.json
results/test_logs/current_fact_refresh.txt
```

## 11. Candidate discovery

Use c014’s existing snapshots first, then perform a bounded fresh search for stronger or newer public packages.

Existing leads include, but are not mandates:

- the public Archaludon agent claiming 75% versus a 1300+ Starmie;
- the Strong Start Baseline V10 claiming LB 950+;
- public meta-snapshot notebooks containing embedded package-ready agents;
- public rule-based Alakazam material;
- a prize/resource-tracking Starmie/Froslass agent;
- a 1084.5 baseline;
- current BattleCore or anti-meta public profiles;
- any newer public package with stronger reproducible evidence.

Do not trust title claims as measured truth. Preserve them as `PUBLIC_CLAIM` until independently reproduced or externally verified.

Create an inventory of at least four candidate leads when available. Each entry must include:

- candidate ID;
- source author and URL;
- access timestamp;
- notebook/file hashes;
- claimed deck and score/benchmark;
- exact package payload availability;
- exact deck-list availability;
- algorithm type;
- network dependency at inference;
- expected runtime;
- source freshness;
- evidence quality;
- permission status;
- disposition: `ADVANCE`, `BENCHMARK_ONLY`, or `REJECT`.

Required outputs:

```text
results/artifacts/PUBLIC_AGENT_INVENTORY.md
results/artifacts/public_agent_inventory.json
results/artifacts/public_source_manifest.sha256
results/artifacts/public_source_snapshots/
```

## 12. Reuse, attribution, and permission matrix

Before copying, modifying, packaging, or uploading any public implementation, inspect:

- competition rules on public code and team sharing;
- notebook metadata and declared licence;
- explicit author permission or attribution notice;
- whether the source is a competition-public notebook;
- whether the candidate embeds third-party code with separate terms.

Classify every candidate:

1. `SUBMISSION_REUSE_ALLOWED` — exact code/package may be submitted with documented attribution;
2. `LOCAL_BENCHMARK_ONLY` — may be executed locally but not uploaded or redistributed;
3. `CLEAN_ROOM_ALLOWED` — ideas/algorithm may be independently reimplemented without copying source text;
4. `REJECTED_PERMISSION` — permission is insufficient or conflicting.

Absence of a licence is not automatically permission. Do not infer legal rights from visibility alone.

For any submitted candidate, include attribution exactly as required and preserve a source-to-package file map.

Required outputs:

```text
results/artifacts/REUSE_PERMISSION_MATRIX.md
results/artifacts/reuse_permission_matrix.json
results/test_logs/reuse_permission_audit.txt
```

If fewer than two candidates are legally usable for either submission reuse or clean-room reproduction, finish `BLOCKED` or `PARTIAL` honestly rather than violating permissions.

# PHASE 2 — Faithful candidate reproduction

## 13. Candidate advancement

Advance at least three materially different candidates to local execution when permissions and source availability permit.

At least two advanced candidates must be exact public implementations or exact public package payloads. At most one may be a clean-room reproduction.

A candidate is materially different when either its deck archetype or its core decision algorithm differs meaningfully. Cosmetic wrappers around the same payload are one candidate.

For each advanced candidate, create an isolated directory under:

```text
results/artifacts/candidates/<candidate_id>/
```

with:

- exact source snapshot references and hashes;
- extracted or reproduced Python source;
- exact `deck.csv` and hash;
- candidate manifest;
- attribution file;
- build instructions;
- package archive when permitted;
- static dependency audit;
- semantic feature inventory;
- known deviations from source.

## 14. Reproduction fidelity gate

Each exact candidate must satisfy:

- source files or embedded payload decoded without silent truncation;
- candidate deck hash matches the public source or documented source output;
- algorithmically material functions are preserved;
- no replacement of planning, tracking, matchup rules, or damage calculations with static priorities;
- only compatibility patches are allowed before baseline measurement;
- every compatibility patch is documented line-by-line;
- exact package or local source completes smoke games legally;
- no network dependency at inference time.

A clean-room candidate must satisfy:

- no copied source text beyond allowed interfaces, identifiers, or factual card data;
- complete semantic specification of the public algorithm;
- implementation covers every material module in that specification;
- behavior parity is measured on at least 100 shared legal states when the public source can be run locally;
- top-1 action agreement target at least 90%, or every disagreement is categorized and the candidate is not called faithful;
- no simplification of search, tracking, prize logic, target logic, or matchup overrides merely to finish quickly.

Classify fidelity as:

- `EXACT`;
- `FAITHFUL_CLEAN_ROOM`;
- `PARTIAL_REPRODUCTION`;
- `FAILED`.

Only `EXACT` or `FAITHFUL_CLEAN_ROOM` candidates may be selected for submission.

Required outputs per candidate:

```text
candidate_manifest.json
REPRODUCTION_NOTES.md
reproduction_fidelity.json
attribution.md
static_dependency_report.json
smoke_results.json
```

Global outputs:

```text
results/artifacts/REPRODUCTION_FIDELITY.md
results/artifacts/reproduction_fidelity_summary.json
results/test_logs/candidate_smoke_tests.txt
```

# PHASE 3 — Common screening and final gauntlet

## 15. Pre-register the evaluation before running candidates

Create the evaluation specification before candidate results are known.

The common panel should include, when technically available:

- frozen Dragapult control;
- official Iono sample agent;
- Mega Lucario control;
- Mega Abomasnow control;
- c014 custom Archaludon package;
- c015 custom Iono package;
- deterministic safe control;
- direct candidate cross-play among finalists.

Do not change the panel or ranking rule after seeing scores unless a technical defect invalidates an opponent. Any change requires a written amendment before rerunning.

Required output:

```text
results/artifacts/EVALUATION_PROTOCOL.md
results/artifacts/evaluation_protocol.json
```

## 16. Stage A — screening

For every advanced candidate:

- run at least 40 games against the deterministic safe control;
- run at least 80 games against Dragapult;
- represent both seats equally;
- use fixed, candidate-independent seed lists;
- measure legality, termination, latency, score rate, and fallback behavior.

Screening hard gates:

- zero invalid selections;
- zero uncaught exceptions;
- zero timeouts;
- deterministic replay on a fixed sample;
- no hidden-information access;
- no inference-time network access;
- extracted-package or package-equivalent execution;
- score rate at least 80% against the deterministic safe control unless a documented simulator/deck asymmetry explains failure.

Advance the best three candidates by the pre-registered ranking rule. If only two candidates pass, advance both. If fewer than two pass, finish `PARTIAL` and do not upload.

## 17. Stage B — common final panel

For each finalist, run at least:

- 200 games against Dragapult, 100 per seat;
- 100 games against official Iono, 50 per seat;
- 100 games against Mega Lucario, 50 per seat;
- 100 games against Mega Abomasnow, 50 per seat;
- 100 games against c014 custom, 50 per seat;
- 100 games against c015 custom, 50 per seat;
- 50 additional games against safe control if Stage A safe rate was below 95%.

For the top two finalists, additionally run:

- at least 300 direct cross-play games, balanced by seat;
- at least 200 independent-seed confirmation games against Dragapult;
- at least 300 independent-seed strategic-field confirmation games split across official Iono, Mega Lucario, and Mega Abomasnow.

Run the frozen Dragapult control once on the same independent official-opponent seed lists so path B compares candidates and Dragapult on an identical protocol.

Use identity-safe result aggregation. Never positionally zip unordered worker results to candidate labels.

Record Wilson intervals for major rates, but use them for uncertainty disclosure rather than endless adjudication.

## 18. Pre-registered ranking and competitive gate

Rank finalists lexicographically in this order:

1. passes reproduction fidelity (`EXACT` or `FAITHFUL_CLEAN_ROOM`);
2. passes all reliability and package-feasibility hard gates;
3. score rate versus Dragapult on independent confirmation;
4. mean score rate across official Iono, Mega Lucario, and Mega Abomasnow on independent confirmation;
5. direct cross-play versus the other finalist;
6. lower p99 latency;
7. stronger current public evidence quality.

Do not replace this with an unregistered composite score.

The selected candidate must pass all base conditions:

- at least 90% score rate against deterministic safe control over all safe games;
- at least 65% against c014 custom over at least 100 games;
- at least 65% against c015 custom over at least 100 games;
- zero reliability violations;
- fidelity `EXACT` or `FAITHFUL_CLEAN_ROOM`.

It must also pass at least one strength path:

### Strength path A — direct champion improvement

- at least 55% versus Dragapult over at least 400 confirmation games;
- Wilson 95% lower bound above 50%.

### Strength path B — broad-field challenger

- at least 48% versus Dragapult over at least 400 confirmation games;
- at least 55% mean score rate across official Iono, Mega Lucario, and Mega Abomasnow over at least 600 total confirmation games;
- not more than 10 percentage points worse than Dragapult on any two official opponents.

### Strength path C — exact high-signal public calibration

Use only when local opponents are demonstrably unrepresentative and the candidate is `EXACT`:

- current source provides a package-ready candidate and a specific public score or matchup claim of at least 900-equivalent evidence;
- the claim is labelled `PUBLIC_CLAIM`, not treated as fact;
- local reproduction matches at least one source-published matchup or behavior benchmark within 10 percentage points over at least 200 games;
- candidate achieves at least 50% versus Dragapult or at least 55% strategic-field mean;
- independent evidence-quality review explicitly approves submission as a calibration candidate.

If no candidate passes A, B, or C, do not upload. Set `competitive_gate: FAIL`, overall `PARTIAL`, and preserve the best candidate package for the next contract.

Required outputs:

```text
results/artifacts/screening_results.csv
results/artifacts/final_gauntlet_results.csv
results/artifacts/crossplay_results.csv
results/artifacts/latency_report.json
results/artifacts/reliability_report.json
results/artifacts/selection_decision.json
results/artifacts/SELECTION_DECISION.md
results/artifacts/competitive_gate.json
results/test_logs/common_gauntlet.txt
```

# PHASE 4 — Package and submit one champion candidate

## 19. Exact c016 package

Build one inference-only archive from the selected candidate without strategic modification after selection.

Name it:

```text
results/artifacts/submission_J_public_champion_v0.tar.gz
```

Package requirements:

- `main.py` and exact `deck.csv` at the required archive location;
- exact selected candidate source and static data;
- required attribution file when package rules permit extra files;
- official runtime/SDK files only as needed;
- no credentials, public-source notebooks, opponent agents, tests, logs, caches, or Git metadata;
- no inference-time network access;
- archive hash and source-to-package mapping recorded.

Extract into a clean temporary directory and run at least 200 package games:

- 100 against Dragapult, balanced by seat;
- 50 against official Iono, balanced by seat;
- 50 against deterministic safe control, balanced by seat.

Package hard gates:

- zero invalid selections;
- zero exceptions;
- zero timeouts;
- deterministic replay;
- dependency audit passes;
- package results are within 10 percentage points of the source-run results for the same seed/opponent protocol;
- selected source and deck hashes match the selection record.

Required outputs:

```text
results/artifacts/submission_J_public_champion_v0.tar.gz
results/artifacts/submission_J_manifest.json
results/artifacts/submission_J_validation.json
results/artifacts/source_to_package_map.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
results/test_logs/package_validation.txt
```

## 20. Mandatory automatic upload after all gates

When and only when reproduction fidelity, competitive selection, and package validation all pass, upload the exact validated archive automatically.

Use a unique description:

```text
c016 public-champion-v0 <candidate-id> <fidelity> <short-git-sha>
```

Before upload:

1. list current team submissions;
2. record c014, c015, and Dragapult rows when still present;
3. enforce duplicate-description and package-hash guards;
4. confirm the exact archive path and SHA-256;
5. confirm the reuse/attribution classification permits submission.

After upload:

1. capture command, stdout, stderr, exit code, and timestamp;
2. retrieve the non-null submission reference;
3. poll status for at most 20 attempts at approximately 30-second intervals;
4. stop at complete, scored, rejected, or the bound;
5. record score as `PENDING` when still processing;
6. preserve the exact listing row.

If the first upload is rejected solely for a mechanical package defect, fix only that defect, repeat package validation, and retry once. Do not change deck or strategy in the retry.

A non-null accepted c016 reference is mandatory for `PASS`.

Required outputs:

```text
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

# PHASE 5 — Decision board and evidence integrity

## 21. Updated branch board

Create a new decision board with at least:

1. selected c016 public champion candidate;
2. Dragapult temporary control;
3. c014 custom Archaludon;
4. c015 custom Iono;
5. runner-up c016 public candidate.

Allowed roles:

- `CHAMPION_CANDIDATE`;
- `CHALLENGER`;
- `CONTROL`;
- `ARCHIVE`;
- `PENDING_EXTERNAL`.

Do not declare the c016 candidate final champion solely because the upload was accepted. Use `PENDING_EXTERNAL` until external score is available unless local evidence already establishes the internal champion role.

The board must identify exactly one next action:

- wait for c016 external score and compare;
- or fix one named reproduction/package defect;
- or promote the runner-up if c016 is externally weak.

Do not propose a new deck family in the same contract.

Required outputs:

```text
results/artifacts/DECISION_BOARD.md
results/artifacts/decision_board.json
results/artifacts/next_action.json
```

## 22. Content-aware result validation

Create a c016-specific validator that re-derives all headline claims from raw artifacts.

It must fail when any of the following occurs:

- a report title or contract ID says c014 or c015 where c016 is required;
- selected candidate, deck, source, target, or hashes are null when required;
- a score denominator differs between raw and reported evidence;
- an execution rate is claimed when opportunities are zero;
- candidate labels are mapped by unordered position;
- package hash differs from the uploaded file;
- a `PUBLIC_CLAIM` is reported as verified fact;
- a permission class does not permit the selected upload;
- historical files were modified;
- `PASS` is claimed without fidelity, competitive, package, and accepted-reference gates.

Zero opportunities must be reported as `NOT_OBSERVED`, never 100%.

Required outputs:

```text
results/artifacts/evidence_validation.json
results/test_logs/evidence_validation.txt
```

# ACCEPTANCE CRITERIA

## AC-01 — Starting state, raw ingest, and immutability

Pass only when c016 starts from the exact c015 final HEAD, records initial Git state, audits c014/c015 from raw artifacts, preserves unrelated work, and proves c005–c015 immutability.

## AC-02 — Current facts, candidate inventory, and permission matrix

Pass only when current competition facts are refreshed, at least four public candidate leads are inventoried when available, all sources are snapshotted and hashed, and every candidate receives an evidence and reuse classification before code is copied or packaged.

## AC-03 — Faithful candidate reproduction

Pass only when at least three materially different candidates are locally executable when permissions permit, at least two are exact public implementations, no more than one is clean-room, and every finalist is classified `EXACT` or `FAITHFUL_CLEAN_ROOM` with documented compatibility patches and no strategic simplification.

## AC-04 — Pre-registered common screening and final gauntlet

Pass only when the evaluation protocol is frozen before scores are known, fixed seed lists and both seats are used, Stage A and Stage B game minimums are met, identity-safe aggregation is proven, and all reliability/latency evidence is preserved.

## AC-05 — Selection and competitive gate

Pass only when the lexicographic ranking rule is applied exactly, the selected candidate passes every base condition and one registered strength path, public claims remain correctly labelled, and no post-selection strategic modification occurs.

## AC-06 — Clean c016 package validation

Pass only when the exact submission J archive, manifest, hashes, source-to-package map, clean extraction, at least 200 package games, dependency audit, fidelity parity, and inference-only checks pass.

## AC-07 — Mandatory Kaggle submission

Pass only when Claude Code uploads the exact validated archive, permission allows submission, duplicate/hash guards pass, a non-null accepted c016 submission reference is recorded, and bounded status polling records a score or `PENDING`.

## AC-08 — Evidence integrity, decision board, source bundle, and Git completion

Pass only when the c016-specific content validator passes, the updated decision board and one next action are complete, all reports are derived from raw evidence, the source bundle validates from clean extraction, and implementation commits and final Git state are recorded.

# REQUIRED RESULTS STRUCTURE

```text
contracts/c016_public_agent_reproduction_gauntlet_and_champion_submission/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── COMMANDS_RUN.md
├── FILES_CHANGED.md
├── GIT_REPORT.md
├── artifacts/
│   ├── PRIOR_RESULTS_AUDIT.md
│   ├── prior_results_audit.json
│   ├── CURRENT_COMPETITION_FACTS.md
│   ├── current_competition_facts.json
│   ├── PUBLIC_AGENT_INVENTORY.md
│   ├── public_agent_inventory.json
│   ├── public_source_manifest.sha256
│   ├── REUSE_PERMISSION_MATRIX.md
│   ├── reuse_permission_matrix.json
│   ├── REPRODUCTION_FIDELITY.md
│   ├── reproduction_fidelity_summary.json
│   ├── EVALUATION_PROTOCOL.md
│   ├── evaluation_protocol.json
│   ├── screening_results.csv
│   ├── final_gauntlet_results.csv
│   ├── crossplay_results.csv
│   ├── latency_report.json
│   ├── reliability_report.json
│   ├── selection_decision.json
│   ├── SELECTION_DECISION.md
│   ├── competitive_gate.json
│   ├── submission_J_public_champion_v0.tar.gz
│   ├── submission_J_manifest.json
│   ├── submission_J_validation.json
│   ├── source_to_package_map.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── DECISION_BOARD.md
│   ├── decision_board.json
│   ├── next_action.json
│   ├── evidence_validation.json
│   ├── c016.patch
│   ├── c016_python_source_bundle.zip
│   ├── c016_python_source_manifest.json
│   ├── candidates/
│   │   └── <candidate_id>/
│   │       ├── candidate_manifest.json
│   │       ├── REPRODUCTION_NOTES.md
│   │       ├── reproduction_fidelity.json
│   │       ├── attribution.md
│   │       ├── static_dependency_report.json
│   │       ├── smoke_results.json
│   │       ├── deck.csv
│   │       └── source/
│   ├── public_source_snapshots/
│   └── source_snapshot/
├── test_logs/
│   ├── prior_results_ingest.txt
│   ├── current_fact_refresh.txt
│   ├── reuse_permission_audit.txt
│   ├── candidate_smoke_tests.txt
│   ├── common_gauntlet.txt
│   ├── package_validation.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   ├── evidence_validation.txt
│   ├── immutability_verification.txt
│   ├── source_bundle_validation.txt
│   └── final_git_status.txt
└── failures/
```

Candidate source directories may contain only legally retainable material. When redistribution is not permitted, include hashes, source URLs, extraction commands, and local path references rather than copied source in the shareable source bundle.

# STATUS AND DECISIONS

`STATUS.json` must include at least:

```json
{
  "contract": "c016_public_agent_reproduction_gauntlet_and_champion_submission",
  "status": "PASS",
  "operational_status": "PASS",
  "evidence_integrity_status": "PASS",
  "competitive_gate_status": "PASS",
  "acceptance_criteria_total": 8,
  "acceptance_criteria_passed": 8,
  "acceptance_criteria_failed": 0,
  "initial_branch": "contract/c015_anti_meta_deck_agent_v0",
  "initial_head": "...",
  "final_branch": "contract/c016_public_agent_reproduction_gauntlet_and_champion_submission",
  "final_head": "...",
  "implementation_commits": [],
  "candidate_leads": 0,
  "candidates_executable": 0,
  "candidates_exact": 0,
  "candidates_clean_room": 0,
  "selected_candidate_id": "...",
  "selected_candidate_source": "...",
  "selected_fidelity": "EXACT",
  "selected_deck_sha256": "...",
  "strength_path": "A",
  "score_rate_vs_dragapult": 0.0,
  "strategic_field_score_rate": 0.0,
  "score_rate_vs_c014": 0.0,
  "score_rate_vs_c015": 0.0,
  "training_games": 0,
  "screening_games": 0,
  "final_gauntlet_games": 0,
  "package_validation_games": 0,
  "invalid_actions": 0,
  "exceptions": 0,
  "timeouts": 0,
  "package_sha256": "...",
  "reuse_permission_class": "SUBMISSION_REUSE_ALLOWED",
  "kaggle_upload": "SUBMITTED",
  "kaggle_submission_ref": "...",
  "kaggle_submission_status": "PENDING",
  "public_score": null,
  "next_action": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

Use `PASS` only when all eight acceptance criteria pass, the selected candidate clears the competitive gate, and a non-null accepted c016 submission reference exists.

Use `PARTIAL` when useful candidates and evidence exist but candidate count, fidelity, competitive gate, package, permission, or upload acceptance is incomplete.

Use `BLOCKED` when competition access, simulator/runtime access, source permission, or repository state prevents meaningful execution.

A legal package with an accepted upload but failed competitive or evidence-integrity gate is `PARTIAL`, never `PASS`.

# SOURCE BUNDLE

Create and validate:

```text
results/artifacts/c016_python_source_bundle.zip
```

Include:

- every c016 Python source and test created or executed;
- exact candidate manifests, decks, compatibility patches, adapters, and package builder;
- candidate source only when redistribution is permitted;
- URLs, hashes, extraction commands, and attribution for non-redistributable source;
- evaluation protocol, fixed seed lists, raw result schemas, and identity-safe aggregation code;
- current-fact and permission evidence;
- contract, command, inputs, and references;
- dependency and machine snapshots;
- Git status, patch, initial/final HEAD, and commit list;
- manifests, hashes, validation outputs, and sanitized Kaggle evidence.

Exclude:

- credentials, tokens, cookies, Kaggle config, or secrets;
- virtual environments and caches;
- source whose licence forbids redistribution;
- unrelated historical binaries and checkpoints;
- opponent packages not required for audit and already preserved elsewhere.

Validate from a clean extraction and produce:

```text
results/artifacts/c016_python_source_manifest.json
```

# FINAL OPERATING PRINCIPLE

c016 exists to establish the first genuinely strong public baseline owned by the project.

The required order is:

```text
permission and source fidelity
→ exact candidate reproduction
→ common gauntlet
→ pre-registered competitive gate
→ exact package
→ submit once
→ external comparison
```

Do not reward speed by lowering fidelity. Do not reward fidelity by ignoring strength. Do not reward an accepted upload by calling a weak experiment a success.
