# c015 — Anti-Meta Deck-Agent v0

## 1. Objective

After c014 has produced a validated public-meta-v0 package and an accepted Kaggle submission reference, ingest its evidence without waiting for its public score, freeze one explicit complementary anti-meta thesis, implement one materially different deterministic deck-specific expert, validate and package it, upload it to Kaggle automatically, and finish with an accepted c015 submission reference.

This is an execution contract, not a separate analysis phase.

## 2. Success definition

The contract succeeds when all of the following are true:

1. c014's validated package and accepted submission reference are verified;
2. one current target archetype and one distinct non-Dragapult anti-meta deck are frozen;
3. the branch has a one-sentence thesis with two concrete counter mechanisms;
4. one deterministic deck-specific expert is package-feasible and coherent;
5. compact legality, reliability, latency, package, and targeted-thesis checks pass;
6. Claude Code uploads the exact validated c015 archive to Kaggle;
7. a non-null accepted c015 submission reference is recorded;
8. c015's public score may be `PENDING` when the contract closes.

Do not wait for c014 scoring and do not create an intermediate analysis contract.

## 3. User decisions fixed before execution

- c015 is intentionally prepared before c014 finishes.
- c015 may begin only after c014 has a validated package and a non-null accepted Kaggle submission reference.
- c014 score `PENDING` is sufficient to begin.
- Claude Code is explicitly authorized and required to upload c015 automatically after all mandatory hard gates pass.
- An accepted c015 submission reference completes the external requirement even if the score remains `PENDING`.
- The c015 implementation must be a different anti-meta deck-agent, not another Dragapult policy iteration.

These decisions may not be weakened during execution.

## 4. Dynamic starting state and branch creation

c015 starts from the final committed c014 branch state, not from the older c013 context HEAD.

Expected parent branch:

```text
contract/c014_public_meta_baseline_and_rapid_submission
```

Before editing, record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -8 --oneline
```

Verify the c014 result preconditions in §7. Then create:

```text
contract/c015_anti_meta_deck_agent_v0
```

from the c014 final HEAD. Commit messages must begin with `c015:`.

If the current checkout is not the completed c014 branch, locate the exact c014 final commit from `c014/results/STATUS.json` and Git history. Do not guess or silently start from c013.

Preserve dirty/untracked user files. Do not clean, delete, normalize, or absorb unrelated work merely to make Git clean.

## 5. Absolute immutability and preserved artifacts

Do not modify any file under c005 through c014 except to read c014 results. Do not alter the c014 submitted package, deck, source bundle, status, or submission records.

Preserve:

- c014 selected meta-proven deck-agent and exact submission H archive;
- c014 public-source snapshot and selection memo;
- c014 accepted submission reference and current score/status;
- all c005–c013 historical policies, checkpoints, results, and source bundles;
- Dragapult controls and safe deterministic controls;
- unrelated user changes.

c015 must create new files, new package names, new evidence, and a new Kaggle description. It may reuse general simulator/package utilities only when doing so does not modify historical outputs.

## 6. Scope and anti-overengineering constraints

c015 has one primary implementation change:

> Build the deterministic expert core for one selected anti-meta deck that is materially different from c014.

Allowed work:

- ingest and validate c014 evidence;
- bounded current-evidence delta check;
- exact anti-meta deck list and validation;
- deck-specific setup, search, bench, evolution, attachment, attack, target, promotion, forced/multi-select, and fallback rules;
- minimal prize/resource/opponent-archetype tracking required by this exact deck thesis;
- focused deck-specific tests and decision traces;
- compact targeted matchup evaluation;
- package construction, validation, and automatic submission.

Forbidden work:

- PPO, policy continuation, distillation, or any training run;
- Dragapult as the c015 submitted deck;
- selecting the same archetype or exact deck hash as c014;
- generic multi-deck frameworks or universal rule engines;
- MCTS, expectimax, rollouts, or other search;
- learned residuals or neural architecture changes;
- Claude strategic-teacher labeling;
- re-adjudicating c012/c013 neural policies;
- waiting for c014 public scoring before implementation;
- broad meta mining beyond the bounded delta check;
- more than one active anti-meta implementation;
- more than one major strategic change in the submitted version.

Duplication is acceptable when it is faster and safer than abstraction.

## 7. Hard c014 start gate

Read:

```text
contracts/c014_public_meta_baseline_and_rapid_submission/results/
```

Verify all of the following:

1. `STATUS.json` exists and identifies the exact c014 final branch/HEAD;
2. `submission_H_public_meta_v0.tar.gz` exists;
3. the package SHA-256 matches c014 records;
4. c014 extracted-package validation passed its hard reliability gates;
5. c014 selected deck and deck hash are available;
6. `kaggle_submission_status.json` contains a non-null accepted submission reference;
7. the c014 public score may be null/`PENDING`;
8. c014's public sources, provisional anti-meta memo, matchup matrix, coherence report, and next-loss-mode evidence are readable.

Create:

```text
results/artifacts/C014_INGEST.md
results/artifacts/c014_ingest.json
results/test_logs/c014_precondition_check.txt
```

If any item 1–6 fails, set c015 to `BLOCKED`, explain exactly what is missing, create no implementation branch beyond documentation needed to preserve the block, and do not upload anything.

A merely pending score is not a block.

# PHASE 0 — Freeze one anti-meta thesis

## 8. Consume c014 evidence first

Use c014 as the primary evidence base. Extract:

- selected meta-proven archetype and exact deck hash;
- c014 branch thesis and intended game plan;
- strongest current public archetype identified during c014 mining;
- c014 provisional anti-meta candidate;
- c014 top three loss categories and selected next loss mode;
- c014 local matchup matrix and seat balance;
- current rules/deadline/submission limits already verified by c014;
- public sources and evidence-quality labels.

Do not repeat c014's full 4–6 hour public mining.

## 9. Bounded delta check, maximum 1–2 hours

Perform only a current delta check to identify material changes since c014's access timestamps:

- competition rules or deadline change;
- submission-limit change;
- newly available top-agent episode dataset;
- newly published high-signal public notebook/discussion;
- clearly changed dominant archetype evidence;
- c014 submission status/score update if already available.

Stop after 1–2 elapsed hours even when evidence remains incomplete. Record zero changes honestly when none are found.

Required outputs:

```text
results/artifacts/PUBLIC_DELTA_CHECK.md
results/artifacts/public_delta.json
results/artifacts/public_delta_sources.json
results/test_logs/public_delta_check.txt
```

## 10. Select exactly one target and one deck

Evaluate the c014 provisional anti-meta candidate plus at least one alternative from the already captured public evidence. This is a compact thesis decision, not a new open-ended deck survey.

Freeze exactly one:

- primary target archetype or strategy;
- distinct anti-meta deck archetype;
- exact legal deck list and hash;
- one-sentence branch thesis;
- two concrete counter mechanisms;
- expected complementarity with c014;
- expected difficult matchup;
- explicit thesis falsifier observable in local games.

Required thesis form:

> This deck should beat **TARGET X** because **MECHANISM A** and **MECHANISM B**, while covering c014's weakness to **Y**.

Hard distinctness rules:

- selected archetype must differ materially from c014;
- exact deck hash must differ from c014;
- selected deck must not be Dragapult;
- game plan cannot be a cosmetic variation of c014;
- deck must be automation-friendly enough for a coherent deterministic v0 in one day.

Required outputs:

```text
results/artifacts/ANTI_META_SELECTION.md
results/artifacts/anti_meta_selection.json
results/artifacts/anti_meta_deck.csv
results/artifacts/anti_meta_deck.sha256
results/artifacts/TARGET_ARCHETYPE.md
results/artifacts/ANTI_META_THESIS.md
```

# PHASE 1 — Deterministic anti-meta expert v0

## 11. Implement one deck-specific expert

Implement the smallest coherent deterministic expert for the frozen anti-meta deck. Preserve a legal deterministic fallback for every state.

At minimum, encode and document:

- opening setup and active/bench priorities;
- search-target priorities;
- turn-order/card-play sequencing;
- bench-space and liability rules;
- evolution ordering;
- attachment target and energy conservation;
- attack selection;
- target selection;
- promotion after knockout;
- forced and multi-select handling;
- minimal deck-required prize/resource tracking;
- only the opponent-archetype inference required by the anti-meta thesis;
- deterministic fallback for unknown, malformed, or uncovered states.

The two counter mechanisms must be visible in inspectable rule code and semantic documentation. Card IDs may be used internally but must be mapped to card names and rule purpose.

Add focused tests for the highest-risk decisions and both counter mechanisms. Do not create a universal abstraction.

Required outputs:

```text
results/artifacts/DECK_AGENT_THESIS.md
results/artifacts/RULES.md
results/artifacts/COUNTER_MECHANISMS.md
results/artifacts/rule_coverage.json
results/artifacts/decision_trace_samples.jsonl.gz
```

# PHASE 2 — Compact validation

## 12. Reliability, legality, and latency gate

Run 500–1,000 total games across direct and extracted-package validation, with both seats represented approximately equally.

The direct compact panel must include:

- at least one available implementation/baseline representing the primary target archetype;
- the exact c014 public-meta-v0 package or package-equivalent agent;
- frozen Dragapult control;
- deterministic safe/random control;
- anti-meta self-play only as a plumbing check.

When no faithful target implementation is technically available, use the closest public/official-style target proxy, disclose the limitation, and strengthen the decision-trace thesis audit. Do not fabricate a target agent.

Mandatory hard gates:

- zero invalid selections;
- zero uncaught exceptions;
- zero environment timeouts;
- all scheduled games terminate or are explicitly classified by the simulator;
- deterministic replay on a fixed seed/state sample;
- both seats tested;
- package-feasible imports only;
- p99 decision latency at most 250 ms and maximum below the currently verified competition limit;
- no hidden-information access;
- no network dependency at inference time.

Strength is diagnostic for v0. Do not block a stable, coherent, materially different submission solely because a noisy compact point estimate is below 50%.

## 13. Anti-meta thesis coherence and complementarity audit

Audit at least 60 sampled decisions, including at least 20 decision opportunities for each claimed counter mechanism when available.

Record:

- setup success rate;
- intended attacker prepared rate;
- attachment-to-intended-attacker rate;
- activation/opportunity rate for each counter mechanism;
- correct execution rate when each mechanism is available;
- target-selection consistency;
- bench liability incidents;
- fallback frequency and reasons;
- targeted matchup point estimates by seat;
- c014 versus target and c015 versus target on the same available proxy when technically possible;
- top three c015 loss categories;
- exactly one next loss mode.

The thesis passes coherence when the mechanics are present in the deck, implemented in the rules, and visibly executed in sampled games. Ordinary imperfect win rates do not by themselves fail v0.

Required outputs:

```text
results/artifacts/reliability_report.json
results/artifacts/latency_report.json
results/artifacts/matchup_matrix.csv
results/artifacts/targeted_matchup_comparison.csv
results/artifacts/strategy_coherence.json
results/artifacts/STRATEGY_COHERENCE.md
results/artifacts/complementarity_report.json
results/artifacts/COMPLEMENTARITY.md
results/artifacts/local_games.jsonl.gz
```

# PHASE 3 — Package, validate, and submit

## 14. Build the exact c015 package

Build one inference-only archive containing:

- `main.py` entry point;
- exact anti-meta `deck.csv`;
- deterministic expert and fallback code;
- official runtime/SDK files required by the environment;
- static semantic rule/config data required by this deck.

Exclude:

- credentials and Kaggle config;
- c014 implementation/package files not required by shared official runtime;
- training data and checkpoints;
- opponent agents;
- evaluation logs;
- public source snapshots;
- Git metadata;
- tests, development tools, caches, and unnecessary libraries.

Name the package:

```text
results/artifacts/submission_I_anti_meta_v0.tar.gz
```

Record archive SHA-256, size, file manifest, exact deck hash, exact source commit, and build command.

Extract into a clean temporary directory and run at least 100 games from the extracted package, both seats, against at least three available opponents including c014. All hard gates in §12 still apply.

Required outputs:

```text
results/artifacts/submission_I_anti_meta_v0.tar.gz
results/artifacts/submission_I_manifest.json
results/artifacts/submission_I_validation.json
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
```

## 15. Mandatory automatic upload

When and only when the package and hard gates pass, Claude Code must upload the exact validated archive automatically.

Use a unique description containing:

```text
c015 anti-meta-v0 <selected-archetype> vs <target-archetype> <short-git-sha>
```

Before upload:

1. list existing submissions;
2. confirm c014's submission remains recorded;
3. apply duplicate-description and package-hash guards;
4. confirm the archive about to upload is exactly `submission_I_anti_meta_v0.tar.gz` with the validated SHA-256.

After upload:

1. capture stdout/stderr and exit code;
2. retrieve the submission reference from the API/CLI listing;
3. poll status for a bounded maximum of 20 attempts at approximately 30-second intervals;
4. stop when complete, scored, rejected, or the bound is reached;
5. record score/status as `PENDING` when still processing;
6. preserve the exact listing row and timestamps.

A non-null accepted c015 submission reference is mandatory for `PASS`. A public score is not mandatory.

If the first upload is rejected solely for a mechanical package defect, repair only that defect, repeat extracted-package validation, and retry once. Do not change strategic logic in the retry.

If credentials, service, network, daily submission limit, or competition availability externally blocks upload, set `PARTIAL` or `BLOCKED` honestly and preserve the exact retry command. Never claim `PASS` without an accepted reference.

Required outputs:

```text
results/artifacts/kaggle_submission_status.json
results/artifacts/kaggle_submission_history.jsonl
results/artifacts/kaggle_submissions_after_submit.csv
results/test_logs/kaggle_submission.txt
results/test_logs/kaggle_submission_retrieval.txt
```

# PHASE 4 — Update the operating board

## 16. Branch decision board

Update the project decision board without prematurely choosing a champion from pending or one-shot evidence.

Required rows:

1. c014 meta-proven branch;
2. c015 anti-meta branch;
3. Dragapult control.

For each row record:

- stable version;
- current experiment;
- one-sentence thesis;
- package SHA-256;
- Kaggle submission reference;
- current status/score or `PENDING`;
- main observed weakness;
- next single change;
- branch role: `ACTIVE`, `CONTROL`, or `ARCHIVE`.

At c015 close:

- c014 and c015 normally remain `ACTIVE`;
- Dragapult remains `CONTROL`;
- do not declare `CHAMPION`/`CHALLENGER` until enough external or subsequent evidence exists;
- do not create a third new implementation branch.

Required outputs:

```text
results/artifacts/DECISION_BOARD.md
results/artifacts/decision_board.json
results/artifacts/next_loss_mode.json
```

# ACCEPTANCE CRITERIA

## AC-01 — c014 dependency, Git, and immutability

Pass only when the exact c014 final state is located, the validated package and accepted submission reference are verified, c015 branches from the c014 final HEAD, starting Git state is recorded, unrelated user changes are preserved, and hashes prove c005–c014 were not modified.

## AC-02 — Bounded evidence delta and anti-meta thesis freeze

Pass only when the public delta check is limited to 1–2 hours, c014 evidence is consumed first, the provisional candidate and at least one alternative are compared, exactly one target and one distinct legal non-Dragapult deck are frozen, and the one-sentence thesis contains two concrete counter mechanisms and a falsifier.

## AC-03 — Deterministic anti-meta expert implementation

Pass only when the exact deck-specific expert implements the required deterministic decision categories and both counter mechanisms, preserves a legal fallback, includes focused tests and semantic documentation, and performs no forbidden training/search/Claude/general-framework work.

## AC-04 — Compact legality, reliability, latency, thesis, and complementarity validation

Pass only when 500–1,000 total games cover both seats and the required panel, all hard gates pass, deterministic replay is demonstrated, at least 60 decisions are audited, counter mechanisms are visibly executed, complementarity is reported honestly, and exactly one next loss mode is selected.

## AC-05 — Clean package validation

Pass only when the exact submission I archive, manifest, hashes, clean extraction, at least 100 extracted-package games, dependency audit, inference-only content checks, and c014 distinctness checks pass.

## AC-06 — Mandatory Kaggle submission

Pass only when Claude Code uploads the exact validated archive, records a non-null accepted c015 submission reference, applies duplicate/hash guards, captures bounded status polling, and records either the public score or `PENDING`.

## AC-07 — Decision board, evidence integrity, source bundle, and Git completion

Pass only when the updated three-row decision board, concise summary/status, commands, files changed, Git report, raw evidence, limitations, failure disclosures, patch, and validated `c015_python_source_bundle.zip` are complete and implementation commits are recorded.

# REQUIRED RESULTS STRUCTURE

```text
contracts/c015_anti_meta_deck_agent_v0/results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── COMMANDS_RUN.md
├── FILES_CHANGED.md
├── GIT_REPORT.md
├── artifacts/
│   ├── C014_INGEST.md
│   ├── c014_ingest.json
│   ├── PUBLIC_DELTA_CHECK.md
│   ├── public_delta.json
│   ├── public_delta_sources.json
│   ├── ANTI_META_SELECTION.md
│   ├── anti_meta_selection.json
│   ├── anti_meta_deck.csv
│   ├── anti_meta_deck.sha256
│   ├── TARGET_ARCHETYPE.md
│   ├── ANTI_META_THESIS.md
│   ├── DECK_AGENT_THESIS.md
│   ├── RULES.md
│   ├── COUNTER_MECHANISMS.md
│   ├── rule_coverage.json
│   ├── decision_trace_samples.jsonl.gz
│   ├── reliability_report.json
│   ├── latency_report.json
│   ├── matchup_matrix.csv
│   ├── targeted_matchup_comparison.csv
│   ├── strategy_coherence.json
│   ├── STRATEGY_COHERENCE.md
│   ├── complementarity_report.json
│   ├── COMPLEMENTARITY.md
│   ├── local_games.jsonl.gz
│   ├── submission_I_anti_meta_v0.tar.gz
│   ├── submission_I_manifest.json
│   ├── submission_I_validation.json
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── kaggle_submission_history.jsonl
│   ├── kaggle_submissions_after_submit.csv
│   ├── DECISION_BOARD.md
│   ├── decision_board.json
│   ├── next_loss_mode.json
│   ├── c015.patch
│   ├── c015_python_source_bundle.zip
│   ├── c015_python_source_manifest.json
│   └── source_snapshot/
├── test_logs/
│   ├── c014_precondition_check.txt
│   ├── dependency_verification.txt
│   ├── immutability_verification.txt
│   ├── public_delta_check.txt
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

Conditional absence is allowed only for public score fields while the submission is accepted but still processing. The accepted c015 reference and validated archive are never optional for `PASS`.

# STATUS AND DECISIONS

`STATUS.json` must include at least:

```json
{
  "contract": "c015_anti_meta_deck_agent_v0",
  "status": "PASS",
  "acceptance_criteria_total": 7,
  "acceptance_criteria_passed": 7,
  "acceptance_criteria_failed": 0,
  "c014_final_head": "...",
  "c014_selected_archetype": "...",
  "c014_deck_sha256": "...",
  "c014_submission_ref": "...",
  "c014_submission_status": "PENDING",
  "initial_branch": "contract/c014_public_meta_baseline_and_rapid_submission",
  "initial_head": "...",
  "final_branch": "contract/c015_anti_meta_deck_agent_v0",
  "final_head": "...",
  "implementation_commits": [],
  "public_delta_elapsed_hours": 0.0,
  "target_archetype": "...",
  "selected_archetype": "...",
  "branch_thesis": "...",
  "counter_mechanisms": ["...", "..."],
  "anti_meta_deck_sha256": "...",
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
  "blocking_issues": [],
  "known_limitations": []
}
```

Use `PASS` only when all seven criteria pass and the accepted c015 submission reference exists. A `PENDING` score does not reduce `PASS`.

Use `PARTIAL` when useful work and a validated package exist but a mandatory criterion, including upload acceptance, is incomplete.

Use `BLOCKED` when c014's hard start gate fails or simulator/runtime/deck/Kaggle access prevents meaningful execution.

# SOURCE BUNDLE

Create and validate:

```text
results/artifacts/c015_python_source_bundle.zip
```

It must contain:

- every Python source and test created or executed for c015;
- exact anti-meta deck list and rule configuration;
- package builder and submission wrapper;
- c014 ingest summary and referenced c014 manifests/hashes, without duplicating large historical binaries unnecessarily;
- public delta source index and permitted snapshots;
- contract, command, inputs, and references;
- dependency and machine snapshots;
- Git status, patch, initial/final HEAD, and commit list;
- result schemas, manifests, hashes, and concise reports;
- sanitized Kaggle command/output and submission-listing evidence.

Exclude credentials, Kaggle tokens/config, cookies, secrets, virtual environments, caches, unrelated large files, and historical checkpoint binaries already preserved elsewhere.

Validate the bundle from a clean extraction and produce `c015_python_source_manifest.json`.

# FINAL CLAUDE CODE RESPONSE

Return exactly this concise structure:

```text
Contract:
Status:
Branch:
C014 final HEAD:
C014 submission reference/status:
Initial HEAD:
Final HEAD:
Implementation commits:
Public delta elapsed:
Target archetype:
Selected anti-meta archetype:
Branch thesis:
Counter mechanisms:
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
Source bundle:
Known limitations:
```
