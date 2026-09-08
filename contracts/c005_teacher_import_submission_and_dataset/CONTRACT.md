# c005 — Teacher Import, Submission A, and Distillation Dataset

## 1. Winning objective

Select, freeze, validate, and package the strongest legally reusable strategic teacher–deck pair currently available, then generate the first model-ready strategic dataset from that exact frozen teacher.

This contract must produce a real competition outcome:

1. A selected primary teacher with an exact frozen 60-card deck.
2. A selected backup teacher.
3. A validated Kaggle `submission.tar.gz` for Submission A.
4. An explicit `SUBMIT` or `DO NOT SUBMIT` decision.
5. A strategic trajectory dataset suitable for the first behavioral-cloning/distillation experiment.
6. A precise c006 training specification.

This contract must not pass by reusing random, deterministic-first-option, or other engineering-control agents as strategic teachers.

---

## 2. Research conclusion and provisional prior

Current public evidence supports this provisional ordering:

1. **Official Dragapult sample** — provisional first-choice teacher.
   - Dragapult and Lucario are reported as the strongest official sample tier.
   - Dragapult provides strategically rich decisions: setup, evolution, bench targeting, spread damage, prize mapping, and multi-turn planning.
   - Official sample provenance is preferable for a first public baseline submission.

2. **Official Mega Lucario sample** — mandatory official benchmark.
   - Reported in the same top official-sample tier.
   - More linear and potentially easier to distill.

3. **wmh/ptcg-abc Bellibolt** — mandatory competitive challenger when locally reproducible.
   - Public repository reports a ladder Elo of 836 and calls it its best result.
   - It is strategically simpler and may be easier to imitate.
   - The repository did not visibly include a license during research. It must not be submitted or copied into our training artifacts unless reuse rights are established. It may be used only as a locally executed benchmark when legally permitted.

4. **Official Mega Abomasnow and Iono samples** — required diversity candidates when runnable.

5. **Current public roster candidates** — discover and admit at most one additional candidate only when complete, reproducible, attributable, and legally reusable.

This ordering is a prior, not the final decision. The contract must execute the prescribed evaluation and may select another teacher when evidence justifies it.

---

## 3. Authoritative candidate sources

### Mandatory official Kaggle sample kernels

Attempt to acquire exact notebook source and output artifacts for:

```text
kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck
kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck
kiyotah/a-sample-rule-based-agent-dragapult-ex-deck
kiyotah/a-sample-rule-based-agent-iono-s-deck
```

Use Kaggle CLI/API where available. Record kernel metadata, version identifiers, retrieval time, file hashes, and exact commands.

### Mandatory public benchmark repository

Inspect and pin an immutable commit from:

```text
https://github.com/wmh/ptcg-abc
```

Candidate directories of interest:

```text
agents/bellibolt
agents/alakazam
agents/alakazam_mist
```

Do not assume submission reuse rights. Record repository license status and permitted use.

### Current public-roster discovery

Inspect current public evidence, including when accessible:

```text
makimakiai/ptcg-public-27-plus-sample-4-roster-update
prvsiyan/ptcg-ai-battle-field-audited-alakazam-v8
llccqq624/ptcg-meta-a-stable-submit
```

Admit at most one current public candidate beyond the mandatory official samples and benchmark repository candidates. It must have a complete matched deck and policy and clear reuse rights.

### Competition rules

Retrieve and archive the current competition rules relevant to:

- public code reuse
- external data/code
- team/public sharing
- submission packaging
- package size and runtime
- submission limits

If rules cannot be retrieved, record the blocker. Do not submit third-party non-official code without verified permission.

---

## 4. Dependencies

This contract depends on accepted source code from:

```text
c001
c002
c003
c004
```

Reuse:

- safe fallback
- schema-v2 lineage
- semantic replay
- candidate freezing
- strategic gauntlet runner
- reliability and latency reports
- statistical analysis

The c004 deterministic and random candidates remain engineering controls only.

If these dependencies are missing, set `BLOCKED`.

---

## 5. Scope

Expected implementation includes:

- Source acquisition scripts
- Candidate normalization/adapters
- License and rules audit
- Strategic candidate manifest
- Candidate source/deck freezing
- Strategic gauntlet execution
- Teacher selection analysis
- Submission archive builder and validator
- Optional Kaggle submission command
- Teacher trajectory capture
- Dataset validation and splitting
- Model-ready training-record export
- c006 training specification
- Tests and evidence

Compatibility adapters are allowed only when they preserve strategic behavior.

---

## 6. Non-goals

Do not implement:

- Strategic improvements to imported agents
- Deck mutations
- Our proprietary deck
- PPO/RL training
- Neural-policy training
- Search improvements
- LLM action labels
- Card-effect DSL
- Meta dashboard infrastructure
- Schema v3
- General refactoring unrelated to teacher selection or dataset production

Do not modify earlier contract results.

---

## 7. Phase A — Source acquisition, legal audit, and research report

### A1. Acquisition

Create a reproducible acquisition script that:

- Uses Kaggle CLI for official/public notebooks.
- Uses Git with pinned commit hashes for repositories.
- Does not commit credentials or tokens.
- Stores raw downloads outside committed source unless licensing permits.
- Calculates SHA-256 for all candidate source and deck files.
- Records failed retrieval attempts exactly.

### A2. Legal/reuse classification

Every candidate receives:

```text
OFFICIAL_REUSABLE
PUBLIC_REUSABLE_WITH_ATTRIBUTION
LOCAL_BENCHMARK_ONLY
REUSE_UNCLEAR
REUSE_PROHIBITED
```

Rules:

- Official Kaggle sample agents may be admitted for Submission A when competition rules permit.
- A public repository with no explicit license must not be copied into Submission A unless written permission or competition-specific reuse permission is found.
- `REUSE_UNCLEAR` candidates may be evaluated locally only if lawful access/use is clear, but cannot be selected for Submission A.
- Record attribution requirements.

### A3. Research report

Produce a dated report that distinguishes:

- Verified facts
- Author-reported ladder results
- Local c005 results
- Unverified claims
- Recency
- Source quality

Do not treat an author-reported Elo as independently verified.

---

## 8. Phase B — Strategic candidate admission and freeze

### B1. Minimum field

A `PASS` requires at least **three distinct strategic policies** on at least **three distinct deck archetypes**.

The admitted field must include, when runnable:

- Official Dragapult
- Official Mega Lucario
- At least one of:
  - Official Mega Abomasnow
  - Official Iono
  - legally reusable current public strategic candidate

Bellibolt should be admitted as a local benchmark if it runs and local use is permitted, but it cannot satisfy the Submission-A eligibility requirement without verified reuse rights.

Engineering controls do not count toward the minimum.

### B2. Candidate record

Every candidate record includes:

```json
{
  "candidate_id": "...",
  "display_name": "...",
  "archetype": "...",
  "source_type": "official_kaggle_sample",
  "source_reference": "...",
  "source_version": "...",
  "retrieved_at_utc": "...",
  "reuse_classification": "...",
  "agent": {
    "agent_id": "...",
    "agent_version": "...",
    "policy_type": "...",
    "source_files": []
  },
  "deck": {
    "deck_id": "...",
    "card_count": 60,
    "cards": []
  },
  "adapter_files": [],
  "submission_eligible": true
}
```

### B3. Behavior-preserving adapters

Allowed:

- Import/path fixes
- SDK-path fixes
- Interface wrappers
- Packaging wrappers
- Exception capture and telemetry around the policy

Forbidden:

- Action-score changes
- Added heuristics
- Changed card priorities
- Changed deck list
- Changed fallback strategy
- Any tactical correction

Freeze all source/deck/configuration hashes before evaluation and verify them after dataset production.

---

## 9. Phase C — Strategic teacher gauntlet

### C1. Smoke gate

Each candidate must complete:

- 10 games as seat 0
- 10 games as seat 1
- Against at least two strategic opponents

Admission requires:

- Zero invalid actions
- Zero attributable exceptions
- Zero attributable timeouts
- Valid 60-card deck
- Stable source/deck hashes
- P99 latency recorded

### C2. Official gauntlet

Use the c004 balanced sequential protocol with strategic candidates only.

For each unordered pair:

Initial batch:

```text
20 games per seat orientation
40 games total
```

Extend in balanced increments:

```text
10 games per seat orientation
20 games total
```

Maximum:

```text
100 games per seat orientation
200 games total
```

Stop when:

- 95% interval lies entirely above 0.55 or below 0.45; or
- maximum games reached.

Draws count as 0.5.

Attributable invalid actions, errors, and timeouts count as losses and reliability defects.

Engineering controls may be played separately but must not influence strategic ranking.

### C3. Required analysis

Produce:

- Ordered matchup matrix
- Seat-balanced matchup matrix
- Pairwise confidence intervals
- Bradley–Terry or equivalent ranking
- At least 2,000 bootstrap ranking resamples
- Worst-matchup lower bounds
- Reliability
- P50/P95/P99/max latency
- High-impact context coverage
- Action entropy by context
- Average game length and decision count

---

## 10. Teacher selection rule

Selection must be pre-registered and deterministic.

### 10.1 Eligibility

The primary teacher must:

- Be Submission-A eligible.
- Pass reliability gate.
- Have complete frozen deck/policy provenance.
- Complete the full gauntlet.
- Produce at least five high-impact decision contexts across its dataset or document why the engine/deck does not expose them.

High-impact contexts include where applicable:

```text
MAIN
ATTACK
SWITCH
EVOLVE
TO_ACTIVE
TO_BENCH
SELECT_CARD
DISCARD
ACTIVATE
```

### 10.2 Competitive score

Compute:

```text
competitive_score =
    0.50 * normalized_local_strength
  + 0.20 * normalized_worst_matchup_lower_bound
  + 0.20 * external_evidence_score
  + 0.10 * normalized_latency_reliability_score
```

Definitions:

- `normalized_local_strength`: bootstrap percentile of the global ranking.
- `normalized_worst_matchup_lower_bound`: min-max normalized conservative matchup floor.
- `external_evidence_score`: predefined evidence tier below.
- `latency_reliability_score`: zero if reliability gate fails; otherwise rewards lower P99 latency.

External evidence tiers:

```text
1.00 = recent verifiable real Kaggle ladder score/result tied to exact source version
0.80 = official sample benchmark or recent public field matrix tied to exact candidate
0.60 = author-reported ladder result with reproducible exact code/deck
0.40 = recent public local benchmark with reproducible exact code/deck
0.20 = older or weakly linked public claim
0.00 = no usable external evidence
```

Do not double-count the same source.

### 10.3 Teacher suitability score

Compute:

```text
teacher_score =
    0.70 * competitive_score
  + 0.15 * normalized_high_impact_context_coverage
  + 0.10 * normalized_action_entropy
  + 0.05 * reproducibility_score
```

The primary teacher is the eligible candidate with highest `teacher_score`.

The backup teacher is the highest remaining eligible candidate by `competitive_score`, preferably with a different archetype.

### 10.4 Override

An override is allowed only when:

- The top candidate cannot legally be submitted.
- The top candidate’s teacher dataset is structurally unusable.
- A documented packaging/runtime issue exists.
- The score difference is less than 0.02 and external evidence clearly favors the alternative.

Every override requires a written, evidence-based justification.

---

## 11. Phase D — Freeze teacher and build Submission A

### D1. Frozen teacher directory

Create an immutable project directory such as:

```text
teachers/<teacher_id>/
├── main.py
├── deck.csv
├── SOURCE.json
├── FREEZE.json
└── optional required source files
```

Do not include files not allowed by competition rules.

Record:

- Exact source version
- Original source hashes
- Adapter hashes
- Canonical deck ID
- Full deck multiset
- Agent version
- Reuse/attribution
- c005 final Git commit

### D2. Submission archive

Build:

```text
submission_A_teacher.tar.gz
```

It must contain the exact competition-required structure, including `cg/` when required.

Validate:

- Archive paths
- Required files
- No secrets
- No training data
- No unnecessary files
- Size under current competition limit
- Extraction in a clean temporary directory
- cabt smoke match from extracted archive
- At least 20 games against strategic opponents from extracted archive
- Zero invalid actions/errors/timeouts
- P99 latency and total match-clock safety

### D3. Submission decision

Produce exactly one:

```text
SUBMIT
DO_NOT_SUBMIT
```

`SUBMIT` requires all packaging and reliability gates.

### D4. Optional actual submission

Do not upload by default.

Only submit when the execution environment contains:

```text
PTCG_ALLOW_KAGGLE_SUBMIT=1
```

and Kaggle credentials are available.

Then run the exact Kaggle CLI submission command, capture stdout/stderr and returned submission identifier/status, and do not expose credentials.

If the flag is absent, provide the exact command for the user.

---

## 12. Phase E — Strategic teacher dataset

### E1. Dataset opponents

Generate data using the frozen teacher against at least:

- Backup teacher
- Official Dragapult or Lucario, whichever is not primary
- One additional strategic archetype
- Engineering control
- Teacher mirror

### E2. Minimum dataset

Capture at least:

```text
240 completed games
8,000 teacher decisions
```

Requirements:

- Teacher appears in both seats.
- At least 30 games per strategic opponent.
- Full schema-v2 observation snapshots.
- Full legal-option metadata.
- Teacher selected action.
- Decision source.
- Deck/source lineage.
- Opponent identity.
- Terminal outcome.
- Per-decision latency.
- Turn/step identifiers where available.

If 240 games produce fewer than 8,000 teacher decisions, continue until 8,000 or 400 total games, whichever comes first. Record the stopping reason.

### E3. Dataset quality

Exclude from training splits but preserve separately:

- Attributable agent errors
- Invalid actions
- Timeouts
- Corrupt records
- Games missing terminal state

Do not exclude teacher losses merely because the teacher lost.

### E4. Splits

Create:

```text
train
validation
test
```

Split by complete game, never individual decision.

Target:

```text
70% / 15% / 15%
```

Stratify by:

- Opponent
- Teacher seat
- Outcome when feasible

No game ID may appear in more than one split.

The test split must remain frozen for c006.

### E5. Model-ready records

Produce compressed JSONL records containing, at minimum:

```json
{
  "example_id": "...",
  "game_id": "...",
  "split": "train",
  "teacher_id": "...",
  "teacher_deck_id": "...",
  "opponent_id": "...",
  "seat": 0,
  "select_context": "...",
  "observation": {},
  "legal_options": [],
  "teacher_action_indices": [],
  "terminal_outcome": 1.0,
  "decision_latency_ms": 0.0,
  "importance_class": "high"
}
```

Create deterministic example IDs.

### E6. Dataset reports

Report:

- Games/decisions per split
- Opponent/seat/outcome balance
- Context counts
- High-impact context counts
- Legal-option-count distribution
- Selected-index distribution
- Action entropy
- Duplicate examples
- Missing fields
- Dataset size compressed/uncompressed

---

## 13. Phase F — c006 training specification

Produce a concrete configuration for the first student.

The specification must include:

### Input representation

- State/card/entity features
- Deck representation
- SelectContext representation
- Legal-option representation
- Masking rules
- Missing/unknown handling

### Initial model

Default target unless evidence requires a smaller model:

```text
structured legal-option scorer
1–5 million parameters
shared state encoder
context embedding
option encoder
policy score per legal option
optional value head disabled for first cloning baseline
```

### Training

- Behavioral-cloning objective
- Batch construction for variable option lists
- Optimizer
- Learning rate
- Epoch/step budget
- Early stopping
- Class/context weighting
- Seed handling
- Checkpointing
- CPU inference target
- Package-size target

### Evaluation gates

- Exact action agreement
- Top-k agreement
- High-impact-context agreement
- Forced-context agreement
- Full-game student-vs-teacher comparison
- Strategic gauntlet comparison
- Reliability
- P99 latency
- Submission decision criteria

Do not train the model in c005.

---

## 14. Mandatory acceptance criteria

### AC-01 — Current research and source audit

Evidence:

```text
results/artifacts/teacher_research.md
results/artifacts/source_evidence.json
results/artifacts/rules_and_reuse_audit.md
results/test_logs/source_acquisition.txt
```

Pass:

- Mandatory sources attempted.
- Current competition rules archived or precisely referenced.
- Verified facts separated from reported claims.
- License/reuse status recorded.
- No ineligible candidate selected for Submission A.

### AC-02 — At least three real strategic candidates

Evidence:

```text
results/artifacts/strategic_candidate_manifest.json
results/artifacts/candidate_admission.md
results/artifacts/candidate_freeze_before.json
results/artifacts/candidate_freeze_after.json
```

Pass:

- At least three distinct strategic policies.
- At least three distinct archetypes.
- Random/fallback controls do not count.
- Official Dragapult and Lucario attempted.
- Candidate hashes unchanged.

### AC-03 — Reliability smoke gate

Evidence:

```text
results/test_logs/strategic_smoke_tests.txt
results/artifacts/strategic_smoke_report.json
```

Pass:

- Required smoke games complete.
- Every admitted candidate has zero invalid actions, attributable errors, and timeouts.

### AC-04 — Complete strategic gauntlet

Evidence:

```text
results/artifacts/strategic_gauntlet_games.jsonl.gz
results/artifacts/strategic_matchup_matrix.csv
results/artifacts/strategic_pairwise_intervals.json
results/artifacts/strategic_ranking.json
results/artifacts/strategic_bootstrap.json
results/artifacts/strategic_worst_matchups.json
results/test_logs/strategic_gauntlet_execution.txt
```

Pass:

- Every admitted strategic pair evaluated in both seats.
- Sequential protocol followed.
- At least 2,000 bootstrap resamples.
- No pair omitted silently.

### AC-05 — Teacher selection is reproducible

Evidence:

```text
results/artifacts/teacher_scorecard.csv
results/artifacts/teacher_selection.json
results/artifacts/teacher_selection.md
```

Pass:

- Competitive and teacher scores reproduced from raw artifacts.
- Primary and backup selected under predefined rule.
- Any override justified.
- Primary is Submission-A eligible.

### AC-06 — Frozen teacher pair

Evidence:

```text
results/artifacts/frozen_teacher/
results/artifacts/frozen_teacher_manifest.json
```

Pass:

- Exact policy and deck frozen.
- Canonical deck and full card list recorded.
- Source/adapters/configuration hashed.
- Reuse/attribution documented.

### AC-07 — Valid Submission A archive

Evidence:

```text
results/artifacts/submission_A_teacher.tar.gz
results/artifacts/submission_A_validation.json
results/test_logs/submission_A_smoke.txt
results/artifacts/SUBMISSION_A_DECISION.md
results/artifacts/KAGGLE_SUBMIT_COMMAND.txt
```

Pass:

- Archive structure and size valid.
- Clean extraction works.
- At least 20 strategic smoke games from extracted archive.
- Zero invalid actions/errors/timeouts.
- Decision is explicit.

### AC-08 — Optional Kaggle submission is safely handled

Evidence:

```text
results/artifacts/kaggle_submission_status.json
results/test_logs/kaggle_submission.txt
```

Pass:

- If flag absent: no upload occurred and exact command is provided.
- If flag present: submission response/status captured without secrets.
- No accidental duplicate submission.

### AC-09 — Strategic dataset minimum

Evidence:

```text
results/artifacts/teacher_dataset/
results/artifacts/teacher_dataset_manifest.json
results/test_logs/teacher_dataset_generation.txt
```

Pass:

- At least 240 valid completed games.
- At least 8,000 teacher decisions, or documented 400-game cap.
- Both teacher seats.
- Required opponents.
- Full lineage and observations.
- No invalid training records.

### AC-10 — Frozen train/validation/test split

Evidence:

```text
results/artifacts/teacher_dataset/splits.json
results/artifacts/teacher_dataset/train.jsonl.gz
results/artifacts/teacher_dataset/validation.jsonl.gz
results/artifacts/teacher_dataset/test.jsonl.gz
results/artifacts/teacher_dataset/split_report.json
```

Pass:

- Split by whole game.
- No leakage.
- Approximately 70/15/15.
- Stratification report.
- Test split frozen.

### AC-11 — Dataset quality and model readiness

Evidence:

```text
results/artifacts/teacher_dataset/quality_report.json
results/artifacts/teacher_dataset/context_report.csv
results/artifacts/teacher_dataset/schema.json
results/test_logs/teacher_dataset_validation.txt
```

Pass:

- Streaming validation succeeds.
- Deterministic example IDs.
- Missing/duplicate/corrupt checks pass.
- Context/action distributions reported.
- Records contain all required model inputs and labels.

### AC-12 — c006 training specification

Evidence:

```text
results/artifacts/c006_training_spec.md
results/artifacts/c006_training_config.json
```

Pass:

- Model, features, losses, splits, training, inference, and evaluation gates fully specified.
- No unresolved architecture choice blocks c006.
- No training is performed in c005.

### AC-13 — Git and source integrity

Evidence:

```text
results/GIT_REPORT.md
results/artifacts/c005.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

Pass:

- Implementation committed on c005 branch.
- Raw third-party assets are not committed unless permitted.
- Frozen candidate and teacher hashes recorded.
- Earlier results untouched.
- Pre-existing user changes preserved.
- No credentials/secrets committed.

---

## 15. Required results structure

```text
contracts/c005_teacher_import_submission_and_dataset/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── source_acquisition.txt
│   ├── strategic_smoke_tests.txt
│   ├── strategic_gauntlet_execution.txt
│   ├── submission_A_smoke.txt
│   ├── kaggle_submission.txt
│   ├── teacher_dataset_generation.txt
│   ├── teacher_dataset_validation.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── teacher_research.md
│   ├── source_evidence.json
│   ├── rules_and_reuse_audit.md
│   ├── strategic_candidate_manifest.json
│   ├── candidate_admission.md
│   ├── candidate_freeze_before.json
│   ├── candidate_freeze_after.json
│   ├── strategic_smoke_report.json
│   ├── strategic_gauntlet_games.jsonl.gz
│   ├── strategic_matchup_matrix.csv
│   ├── strategic_pairwise_intervals.json
│   ├── strategic_ranking.json
│   ├── strategic_bootstrap.json
│   ├── strategic_worst_matchups.json
│   ├── teacher_scorecard.csv
│   ├── teacher_selection.json
│   ├── teacher_selection.md
│   ├── frozen_teacher/
│   ├── frozen_teacher_manifest.json
│   ├── submission_A_teacher.tar.gz
│   ├── submission_A_validation.json
│   ├── SUBMISSION_A_DECISION.md
│   ├── KAGGLE_SUBMIT_COMMAND.txt
│   ├── kaggle_submission_status.json
│   ├── teacher_dataset/
│   ├── teacher_dataset_manifest.json
│   ├── c006_training_spec.md
│   ├── c006_training_config.json
│   ├── c005.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
└── failures/
```

---

## 16. Required summary and final decision

`SUMMARY.md` must state:

- Candidates acquired, admitted, rejected
- Reuse status
- Local ranking
- External evidence
- Primary teacher
- Backup teacher
- Exact frozen deck ID
- Submission archive size
- Submission A decision
- Actual submission status
- Dataset games and decisions
- Split sizes
- c006 readiness
- Known limitations

`STATUS.json`:

```json
{
  "contract": "c005_teacher_import_submission_and_dataset",
  "status": "PASS",
  "acceptance_criteria_total": 13,
  "acceptance_criteria_passed": 13,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": [],
  "primary_teacher": "...",
  "backup_teacher": "...",
  "frozen_deck_id": "...",
  "submission_A_decision": "SUBMIT",
  "kaggle_submission_performed": false,
  "dataset_games": 0,
  "dataset_teacher_decisions": 0,
  "blocking_issues": [],
  "known_limitations": []
}
```

---

## 17. Git requirements

Branch:

```text
contract/c005_teacher_import_submission_and_dataset
```

Create from accepted c004 final HEAD.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Commit messages begin:

```text
c005:
```

Recommended commits:

```text
c005: add strategic teacher acquisition and candidate registry
c005: add teacher gauntlet and frozen submission packaging
c005: add teacher dataset and c006 training specification
```

Do not:

- Push
- Force-push
- Rebase shared history
- Amend user commits
- Commit credentials
- Commit third-party code without verified permission
- Modify candidate strategy/deck
- Modify earlier contract results

---

## 18. Status and stop rules

`BLOCKED` when:

- Fewer than two strategic candidates can be acquired.
- Cabt runtime is unavailable.
- Competition rules prohibit the intended official-sample baseline use.
- Overlapping user changes cannot be preserved.

`PARTIAL` when:

- Fewer than three strategic candidates are admitted.
- No Submission-A-eligible primary teacher exists.
- Submission archive fails validation.
- Dataset minimum is not met.
- Dataset leakage or corruption exists.
- Any mandatory AC fails.

Do not substitute toy agents to obtain `PASS`.

---

## 19. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Official candidates acquired:
Public candidates acquired:
Candidates admitted:
Candidates rejected:
Primary teacher:
Backup teacher:
Frozen deck ID:
Submission A decision:
Submission A archive:
Kaggle submission performed:
Kaggle submission status:
Teacher dataset games:
Teacher dataset decisions:
Train/validation/test sizes:
c006 ready:
Results directory:
Blocking issues:
Known limitations:
```

Do not claim `PASS` unless all thirteen acceptance criteria pass.
