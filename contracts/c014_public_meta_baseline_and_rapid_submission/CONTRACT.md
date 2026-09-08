# c014 — Public Meta Baseline and Rapid Submission

## 1. Objective

Mine current public competition evidence for no more than 4–6 hours, select one publicly evidenced and automation-friendly deck archetype, implement one deterministic deck-specific expert, validate and package it, upload it to Kaggle automatically, and finish with an accepted submission reference.

This contract also creates a concise project wrap-up through c013 so the old fixed-Dragapult program is closed as a completed research phase rather than silently abandoned.

## 2. Success definition

The contract succeeds when all of the following are true:

1. one current public-evidence snapshot and selection memo exist;
2. one new non-Dragapult deck-agent pair is package-feasible and deterministic;
3. compact legality, reliability, latency, package, and strategy-coherence gates pass;
4. Claude Code uploads the exact validated archive to Kaggle;
5. an accepted submission reference is recorded;
6. the public rating may be `PENDING` when the contract closes;
7. all c005–c013 files and historical checkpoints remain immutable;
8. a complete c014 source/evidence bundle is produced.

An accepted submission reference is sufficient to close the contract. Do not wait indefinitely for scoring. Poll only for a bounded period and record the score/status as `PENDING` when necessary.

## 3. User decisions fixed before execution

- Claude Code is explicitly authorized and required to upload the submission automatically after all mandatory reliability and package gates pass.
- Starmie/Froslass is only a public lead to investigate. It is not a predetermined selection.
- A different archetype must be selected when fresher or stronger public evidence supports it.
- Submission acceptance/reference completes the external part of the contract even if the rating is not yet available.
- c014 must wrap up the project history through c013 and end with one meaningful submission.

These decisions may not be weakened during execution.

## 4. Starting state

Repository context supplied with this contract was captured from:

- branch: `contract/c013_fixed_deck_policy_combination_and_learnability`
- HEAD: `a7d78dd56b7d4a9b75c5e5fa2e6828fc3bdfb477`
- context archive SHA-256: `85035b70ee60cce451c8e7c14085fa46449355e2a3bac02983a16ae3faab328b`

The working tree contains unrelated untracked historical contract material. Preserve it. Do not delete, overwrite, normalize, or absorb unrelated user files merely to make Git clean.

Before editing, record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
```

Create a new branch:

```text
contract/c014_public_meta_baseline_and_rapid_submission
```

Commit messages must begin with `c014:`.

## 5. Absolute immutability and preserved controls

Do not modify any file under contracts c005 through c013. Do not overwrite or relabel their results.

Preserve as historical evidence and controls:

- frozen Dragapult teacher and deck from c005;
- `SOUP13_SOUP+P1_822` as the teacher/Lucario specialist;
- `P0_711` as the broad-field/Iono/Abomasnow specialist;
- `C012_SOUP_622_633` as the prior stable reference;
- S622, S633, P1_822, P1_833, and selected historical policies;
- all existing source bundles, raw evidence, package archives, and submission records.

Dragapult is evaluation/control only in c014. Do not run PPO, continue a neural checkpoint, adjudicate soup versus P0, or submit an old Dragapult checkpoint as the c014 result.

## 6. Scope and anti-overengineering constraints

c014 has one primary implementation change:

> Build the deterministic expert core for one selected non-Dragapult deck.

Allowed implementation work:

- exact deck list and deck validation;
- opening/setup priorities;
- search and card-play priorities;
- benching rules;
- evolution ordering;
- energy attachment;
- attack choice;
- target choice;
- promotion/fallback behavior;
- minimal deck-required prize/resource tracking;
- deck-specific logging and tests;
- packaging and submission tooling needed for this agent.

Forbidden work:

- PPO or any new training run;
- generic multi-deck frameworks;
- MCTS, expectimax, rollout search, or other selective search;
- learned residuals, distillation, or neural architecture changes;
- Claude strategic-teacher labeling;
- implementation of the anti-meta branch;
- more than one active new deck-agent implementation;
- broad refactors not required for the c014 package;
- tuning against the final compact panel after results are seen.

Duplication is acceptable when it is the fastest safe route. A small deck-specific module is preferred over a universal abstraction.

## 7. Time and execution budget

The contract is one rapid execution packet and should fit within one working day plus one bounded overnight run at most.

- Public mining: hard time-box of 4–6 elapsed hours.
- Implementation: one deterministic v0 only.
- Local validation: 500–1,000 total games, including package-extracted games.
- Training games: exactly 0.
- New deck families implemented: exactly 1.
- Major implementation changes: exactly 1.
- Kaggle uploads: exactly 1 unless the first upload is rejected for a purely mechanical packaging defect; one corrected retry is then allowed and must be documented.

Do not extend public mining because evidence is imperfect. At the cap, select the best supported feasible archetype and continue.

# PHASE 0 — Current competition and public-evidence snapshot

## 8. Verify current competition facts

Use current official competition pages, Kaggle CLI/API, public notebooks, public datasets, and public discussions. Record access time in Europe/Rome and UTC.

Verify and save evidence for:

- exact competition slug and title;
- current simulation deadline and timezone conversion to Europe/Rome;
- current daily submission limit;
- current packaging/runtime rules and timeout limits;
- current leaderboard or available public-score evidence;
- latest public top-agent episode datasets;
- latest relevant public notebooks and discussions;
- current public deck archetypes and any publicly reported ratings;
- whether public code/data usage is competition-permitted.

Do not trust the handoff’s older deadline, submission limit, ratings, or archetype claims without re-checking them.

Save URLs, titles, authors, publication/update dates, access timestamps, and a local snapshot or quoted factual extract where permitted. Hash downloaded source files. Never include credentials, session cookies, private notebook content, or prohibited material.

Required outputs:

```text
results/artifacts/public_sources.json
results/artifacts/public_source_manifest.sha256
results/artifacts/CURRENT_COMPETITION_FACTS.md
results/artifacts/public_source_snapshots/
```

When a page cannot be snapshotted, record the URL, access time, visible facts used, and the reason.

## 9. Select one deck-agent target

Investigate at minimum:

- the strongest current public-evidenced rule-agent/deck lead;
- Starmie/Froslass as an unverified starting lead;
- at least one materially different public archetype;
- one provisional anti-meta candidate that is not implemented in c014.

Use a compact selection table with these dimensions:

1. strength of current public evidence;
2. automation friendliness and branching factor;
3. availability and legality of an exact deck list;
4. deterministic sequencing clarity;
5. package/runtime feasibility;
6. matchup relevance to the current public meta;
7. implementation risk within one day.

Select exactly one deck. Freeze:

- exact deck list and hash;
- one-sentence branch thesis;
- expected default game plan;
- expected difficult matchup or failure mode;
- public sources supporting the choice;
- one provisional anti-meta thesis for c015, without implementation.

Required outputs:

```text
results/artifacts/META_SELECTION.md
results/artifacts/meta_selection.json
results/artifacts/selected_deck.csv
results/artifacts/selected_deck.sha256
results/artifacts/ANTI_META_PROVISIONAL.md
```

The selected deck must not be Dragapult.

# PHASE 1 — Deterministic expert v0

## 10. Implement one deck-specific expert

Implement the smallest coherent deterministic expert for the selected deck. The agent must use semantic game information available through the official environment and must always preserve a legal deterministic fallback.

At minimum, encode and document:

- initial setup and active/bench priorities;
- search-target priorities;
- turn-order/card-play priorities;
- bench-space and liability rules;
- evolution ordering;
- attachment target and energy conservation;
- attack selection;
- target selection;
- promotion after knockout;
- forced/multi-select handling;
- deck-required prize/resource tracking;
- deterministic fallback for unknown or malformed states.

The logic must be inspectable. Avoid unexplained card-ID-only rule tables when semantic names/effects are available. Card IDs may be used internally but must be mapped to names in the rule documentation.

Add focused unit/integration tests for the selected deck’s highest-risk decision categories. Do not create a universal rule engine.

Required outputs include:

```text
results/artifacts/DECK_AGENT_THESIS.md
results/artifacts/RULES.md
results/artifacts/rule_coverage.json
results/artifacts/decision_trace_samples.jsonl.gz
```

# PHASE 2 — Compact local validation

## 11. Reliability and legality gate

Run 500–1,000 total games across direct and extracted-package validation, with both seats represented approximately equally.

The compact panel must include:

- frozen Dragapult control;
- at least two available official/public-style deterministic baselines representing different archetypes when technically available;
- deterministic safe/random control;
- selected agent self-play only as a plumbing check, not as strength evidence.

Mandatory hard gates:

- zero invalid selections;
- zero uncaught exceptions;
- zero environment timeouts;
- all scheduled games terminate or are explicitly classified by the simulator;
- deterministic replay on a fixed seed/state sample;
- both seats tested;
- package-feasible imports only;
- p99 decision latency at most 250 ms and maximum decision latency below the currently verified competition limit;
- no hidden-information access;
- no dependency on network access at inference time.

Strength is diagnostic, not a narrow promotion gate. Do not block submission merely because the v0 does not beat every local baseline.

## 12. Strategy-coherence gate

Audit at least 50 sampled decisions across the main categories. The thesis must be visibly executed in actual games.

Record:

- setup success rate;
- intended attacker prepared rate;
- illegal/empty bench liability incidents;
- attachment-to-intended-attacker rate;
- attack/target decisions consistent with the thesis;
- fallback frequency and reasons;
- top three observed loss categories;
- one single next loss mode for the following contract.

Submission is blocked only by incoherence that makes the stated deck thesis absent from gameplay, not by ordinary imperfections.

Required outputs:

```text
results/artifacts/reliability_report.json
results/artifacts/latency_report.json
results/artifacts/matchup_matrix.csv
results/artifacts/strategy_coherence.json
results/artifacts/STRATEGY_COHERENCE.md
results/artifacts/local_games.jsonl.gz
```

# PHASE 3 — Package, validate, and submit

## 13. Build the exact package

Build one archive containing only what inference requires:

- `main.py` entry point;
- exact selected `deck.csv`;
- deterministic expert and fallback code;
- official runtime/SDK files required by the environment;
- static semantic rule/config data required by the selected deck.

Exclude:

- credentials and Kaggle config;
- training data and checkpoints;
- opponent agents;
- evaluation logs;
- public source snapshots;
- Git metadata;
- tests and development-only tools;
- unnecessary libraries and caches.

Record archive SHA-256, size, file manifest, exact deck hash, exact source commit, and package construction command.

Extract into a clean temporary directory and run at least 100 games from the extracted package, both seats, against at least three available opponents. All mandatory hard gates from §11 still apply.

Required outputs:

```text
results/artifacts/submission_H_public_meta_v0.tar.gz
results/artifacts/submission_H_manifest.json
results/artifacts/submission_H_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
```

The `H` label distinguishes this new deck-agent submission from earlier A–G package history.

## 14. Mandatory automatic upload

When and only when the package and hard reliability gates pass, Claude Code must upload the exact validated archive automatically.

Use a unique description containing:

```text
c014 public-meta-v0 <selected-archetype> <short-git-sha>
```

Before upload, list existing submissions and apply a duplicate-description/hash guard. Do not upload an unvalidated or different archive.

After upload:

1. capture stdout/stderr and exit code;
2. retrieve the submission reference from the API/CLI listing;
3. poll status for a bounded maximum of 20 attempts at approximately 30-second intervals;
4. stop polling when complete, scored, rejected, or the bound is reached;
5. when still processing, record rating/status as `PENDING` and finish;
6. preserve the exact listing row and timestamp.

A non-null accepted submission reference is mandatory for `PASS`. A public score is not mandatory.

If the upload is rejected because of a purely mechanical package defect, repair only that defect, repeat extracted-package validation, and make at most one corrected upload. Record both attempts. Do not change strategic logic during the retry.

If credentials, Kaggle service, network, or competition availability externally block upload, set `PARTIAL` or `BLOCKED` honestly and preserve the validated package plus exact retry command. Do not claim `PASS`.

Required outputs:

```text
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

# PHASE 4 — Wrap-up and next decision

## 15. Project wrap-up through c013

Create `results/PROJECT_WRAPUP_THROUGH_C013.md` that concisely records:

- the c005–c013 fixed-Dragapult research arc;
- what infrastructure remains useful;
- corrected c013 status and Pareto policy roles;
- why c014 pivots to deck-agent co-design;
- the exact c014 selected deck-agent thesis;
- the c014 package hash and Kaggle submission reference;
- current score or `PENDING`;
- the three-branch operating model;
- the champion/challenger/archive rule;
- the single next loss mode;
- why no more blind Dragapult PPO is authorized.

Do not rewrite history as a failure. Treat c005–c013 as completed infrastructure and evidence that informed the pivot.

Also produce a one-row decision board for c014 and preserve the Dragapult control row:

```text
results/artifacts/DECISION_BOARD.md
results/artifacts/decision_board.json
```

# ACCEPTANCE CRITERIA

## AC-01 — Starting state, Git, dependencies, and immutability

Pass only when branch/HEAD/status are recorded, a c014 branch is created, required simulator/package/Kaggle tooling is checked, unrelated user changes are preserved, and hashes prove c005–c013 were not modified.

## AC-02 — Current public evidence and deck selection

Pass only when current competition facts are verified, public mining is time-boxed to 4–6 hours, source evidence is preserved, at least three candidate leads are compared, exactly one non-Dragapult deck is selected and frozen, and one unimplemented anti-meta thesis is recorded.

## AC-03 — Deterministic expert implementation

Pass only when the selected deck-agent implements the required deterministic decision categories, has a legal fallback, uses no forbidden training/search/Claude work, and focused tests and semantic rule documentation pass.

## AC-04 — Compact legality, reliability, latency, and coherence validation

Pass only when 500–1,000 total games are completed across both seats and the required panel, all hard gates pass, deterministic replay is demonstrated, strategy coherence is audited, and exactly one next loss mode is selected.

## AC-05 — Clean package validation

Pass only when the exact submission archive, manifest, hashes, clean extraction, at least 100 extracted-package games, dependency audit, and inference-only content checks pass.

## AC-06 — Mandatory Kaggle submission

Pass only when Claude Code uploads the exact validated archive, records a non-null accepted submission reference, applies a duplicate guard, captures bounded status polling, and records either the score or `PENDING`.

## AC-07 — Wrap-up, evidence integrity, source bundle, and Git completion

Pass only when the project wrap-up, decision board, concise summary/status, commands, files changed, Git report, raw evidence, failure disclosures, patch, and validated `c014_python_source_bundle.zip` are complete and implementation commits are recorded.

# REQUIRED RESULTS STRUCTURE

```text
contracts/c014_public_meta_baseline_and_rapid_submission/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── COMMANDS_RUN.md
├── FILES_CHANGED.md
├── GIT_REPORT.md
├── PROJECT_WRAPUP_THROUGH_C013.md
├── artifacts/
│   ├── public_sources.json
│   ├── public_source_manifest.sha256
│   ├── CURRENT_COMPETITION_FACTS.md
│   ├── public_source_snapshots/
│   ├── META_SELECTION.md
│   ├── meta_selection.json
│   ├── selected_deck.csv
│   ├── selected_deck.sha256
│   ├── ANTI_META_PROVISIONAL.md
│   ├── DECK_AGENT_THESIS.md
│   ├── RULES.md
│   ├── rule_coverage.json
│   ├── decision_trace_samples.jsonl.gz
│   ├── reliability_report.json
│   ├── latency_report.json
│   ├── matchup_matrix.csv
│   ├── strategy_coherence.json
│   ├── STRATEGY_COHERENCE.md
│   ├── local_games.jsonl.gz
│   ├── submission_H_public_meta_v0.tar.gz
│   ├── submission_H_manifest.json
│   ├── submission_H_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── DECISION_BOARD.md
│   ├── decision_board.json
│   ├── next_loss_mode.json
│   ├── c014.patch
│   ├── c014_python_source_bundle.zip
│   ├── c014_python_source_manifest.json
│   └── source_snapshot/
├── test_logs/
│   ├── dependency_verification.txt
│   ├── immutability_verification.txt
│   ├── public_mining.txt
│   ├── deck_validation.txt
│   ├── unit_tests.txt
│   ├── integration_tests.txt
│   ├── local_validation.txt
│   ├── package_validation.txt
│   ├── kaggle_submission.txt
│   ├── kaggle_submission_retrieval.txt
│   ├── source_bundle_validation.txt
│   └── final_git_status.txt
└── failures/
```

Conditional absence is allowed only for public score fields while the submission is accepted but still processing. The submission reference and validated archive are never optional for `PASS`.

# STATUS AND DECISIONS

`STATUS.json` must include at least:

```json
{
  "contract": "c014_public_meta_baseline_and_rapid_submission",
  "status": "PASS",
  "acceptance_criteria_total": 7,
  "acceptance_criteria_passed": 7,
  "acceptance_criteria_failed": 0,
  "initial_branch": "...",
  "initial_head": "...",
  "final_branch": "contract/c014_public_meta_baseline_and_rapid_submission",
  "final_head": "...",
  "implementation_commits": [],
  "public_mining_elapsed_hours": 0.0,
  "selected_archetype": "...",
  "branch_thesis": "...",
  "selected_deck_sha256": "...",
  "training_games": 0,
  "local_validation_games": 0,
  "package_validation_games": 0,
  "invalid_actions": 0,
  "exceptions": 0,
  "timeouts": 0,
  "package_sha256": "...",
  "kaggle_upload": "SUBMITTED",
  "kaggle_submission_ref": "...",
  "kaggle_submission_status": "PENDING",
  "public_score": null,
  "next_loss_mode": "...",
  "anti_meta_provisional": "...",
  "blocking_issues": [],
  "known_limitations": []
}
```

Use `PASS` only when all seven criteria pass and the accepted submission reference exists. A `PENDING` score does not reduce `PASS`.

Use `PARTIAL` when useful work and a validated package exist but a mandatory criterion, including upload acceptance, is incomplete.

Use `BLOCKED` when simulator/runtime assets, an exact legal deck, required Kaggle access, or preserved repository state prevents meaningful execution.

# SOURCE BUNDLE

Create and validate:

```text
results/artifacts/c014_python_source_bundle.zip
```

It must contain:

- every Python source and test created or executed for c014;
- exact deck list and rule configuration;
- package builder and submission wrapper;
- public source index and permitted snapshots;
- contract, command, inputs, and references;
- dependency and machine snapshots;
- Git status, patch, initial/final HEAD, and commit list;
- result schemas, manifests, hashes, and concise reports;
- sanitized Kaggle command/output and submission listing evidence.

Exclude credentials, Kaggle tokens/config, cookies, secrets, virtual environments, caches, unrelated large files, and earlier checkpoint binaries already preserved elsewhere.

Validate the bundle from a clean extraction and produce `c014_python_source_manifest.json`.

# FINAL CLAUDE CODE RESPONSE

Return exactly this concise structure:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Public mining elapsed:
Selected archetype:
Branch thesis:
Deck SHA-256:
Local validation games:
Invalid actions / exceptions / timeouts:
Package archive:
Package SHA-256:
Kaggle upload:
Submission reference:
Submission status:
Public score:
Next single loss mode:
Provisional anti-meta thesis:
Source bundle:
Known limitations:
```
