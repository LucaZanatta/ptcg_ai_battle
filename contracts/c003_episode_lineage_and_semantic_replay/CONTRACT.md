# c003 — Episode Lineage and Semantic Replay

## 1. Objective

Upgrade the episode-capture platform from schema v1 to a trustworthy, self-describing schema v2 suitable for future policy evaluation and model training.

When this contract is complete, the repository must contain:

1. A versioned schema-v2 capture format with immutable run, agent, engine, environment, deck, seed, decision-source, and terminal provenance.
2. A canonical deck registry that stores the full card multiset and uses order-independent deck identifiers.
3. A semantic replay validator that reconstructs recorded observations, invokes the deterministic safe agent on them, and verifies that the reproduced decisions match the recorded decisions.
4. Cross-field validation proving that duplicated decision metadata agrees with `observation.select`.
5. Correct terminal-state classification based on final environment state rather than the first step.
6. Streaming `.jsonl` and `.jsonl.gz` capture and validation.
7. A compatibility reader for c002 schema-v1 files.
8. A fresh schema-v2 validation dataset from real cabt games with complete lineage and passing validation evidence.

This contract is successful only if the resulting files can be used to answer:

- Which exact repository revision, policy implementation, deck, engine binary, Python environment, and capture schema produced each run?
- Which RNG values were controlled, requested but not controlled, or unknown?
- Can every recorded safe-agent decision be semantically reproduced from the serialized observation?
- Can equivalent deck lists with different line ordering be recognized as the same deck?
- Can normal wins, errors, timeouts, and abnormal terminations be distinguished reliably?
- Can old c002 files still be read without silently pretending they are schema v2?

---

## 2. Context

The preceding contracts established:

- `c001`: a deterministic legal fallback agent.
- `c002`: runtime-asset verification, side-effect-free tests, JSONL episode capture, streaming structural validation, and context/latency reporting.

Review of c002 found that the implementation is useful but not yet suitable as a trustworthy experiment or training-data platform because:

1. `game_seed` implies engine determinism even though the exposed seed does not control the full cabt trajectory.
2. The current replay check validates duplicated bounds metadata rather than reconstructing and replaying the serialized observation.
3. Captures lack immutable agent, Git, engine, environment, and source-code lineage.
4. Deck IDs are order-sensitive and do not include the actual card multiset.
5. `used_fallback` is currently equivalent to “this player is the safe agent,” not actual fallback invocation.
6. Terminal classification appears to inspect the wrong environment step.
7. The runtime manifest does not fully verify Python/package/platform versions.
8. Schema-v1 data must remain readable, but it must not be silently upgraded with invented provenance.

This contract corrects those defects before strategic rule policies, search, RL, imitation learning, or deck optimization begin.

---

## 3. Dependencies

This contract depends on the accepted source code and commits from:

- `c001_deterministic_safe_agent_core`
- `c002_reproducible_episode_capture`

Claude Code must inspect the repository rather than assume exact paths from this document.

If the expected c001/c002 implementation is not present, record the missing dependency under:

```text
contracts/c003_episode_lineage_and_semantic_replay/results/failures/
```

and set status to `BLOCKED`.

---

## 4. Inputs

Claude Code may use:

- The current Git repository.
- Existing c001 and c002 source code.
- Existing c002 schema-v1 capture files, when available.
- cabt starter-kit assets already present locally.
- `contracts/c003_episode_lineage_and_semantic_replay/inputs/c002_review_findings.md`
- `contracts/c003_episode_lineage_and_semantic_replay/references/results_protocol.md`

All paths in code and documentation must be relative to the repository root unless an external runtime asset requires an absolute path.

---

## 5. Scope

Expected implementation areas include, but are not limited to:

- Episode schema definitions
- Run metadata collection
- Agent metadata collection
- Environment/runtime metadata
- Deck canonicalization and registry
- Seed metadata
- Decision provenance
- Terminal classification
- Capture writer
- Gzip support
- Schema-v1 compatibility reader
- Streaming validator
- Semantic replay validator
- Tests and fixtures
- Evidence-generation commands

Claude Code may reorganize c002 capture modules when necessary, but must preserve a small, reviewable change set and must avoid unrelated refactoring.

---

## 6. Non-goals

Do not implement:

- Strategic card sequencing
- Deck-specific heuristics
- MCTS, beam search, or any search policy
- RL, policy/value networks, imitation learning, or model training
- Opponent modeling
- Meta mining
- Deck optimization
- Arbitrary cabt state construction
- Exact executable card-effect DSL
- Kaggle submission packaging changes unrelated to provenance or capture
- A claim that cabt engine trajectories are reproducible when they are not

Do not alter c001 or c002 historical `results/` folders.

---

## 7. Required design

### 7.1 Schema versions

The capture system must explicitly distinguish at least:

```text
schema_version = 1
schema_version = 2
```

Schema-v2 records must never be inferred solely from file extension.

Provide a schema reader that:

- Detects supported versions.
- Reads schema v1.
- Reads schema v2.
- Rejects unsupported future versions with a clear error.
- Does not invent missing provenance for schema-v1 data.
- Marks unavailable schema-v1 fields explicitly as `null`, `unknown`, or `legacy_unavailable`.

### 7.2 Run-level lineage

Each schema-v2 run must have a stable `run_id` and immutable run metadata containing, at minimum:

```json
{
  "schema_version": 2,
  "run_id": "...",
  "created_at_utc": "...",
  "git": {
    "commit": "...",
    "branch": "...",
    "dirty": false
  },
  "capture": {
    "implementation_sha256": "...",
    "command": "...",
    "compression": "none or gzip"
  },
  "environment": {
    "python_version": "...",
    "platform": "...",
    "machine": "...",
    "kaggle_environments_version": "..."
  },
  "engine": {
    "path": "...",
    "sha256": "...",
    "size_bytes": 0
  }
}
```

Additional fields are allowed.

If the worktree is dirty at capture time, either:

- Refuse to create an official validation capture; or
- Mark the run clearly as dirty and include hashes of all capture-critical source files.

For the contract acceptance dataset, the run must be captured from a clean contract branch.

### 7.3 Agent lineage

Every player definition must include:

```json
{
  "agent_id": "...",
  "agent_version": "...",
  "policy_type": "...",
  "source_files": [
    {
      "path": "...",
      "sha256": "..."
    }
  ],
  "configuration": {}
}
```

Agent identity must distinguish at least:

- deterministic safe agent
- random baseline
- future strategic agents

Do not encode policy identity only in a human-readable display string.

### 7.4 Decision provenance

Each decision record must include a structured source:

```text
forced
rule
heuristic
search
model
fallback
random_baseline
unknown
```

The record must include:

```json
{
  "decision_source": "fallback",
  "used_fallback": true,
  "fallback_reason": "no_strategy_policy_configured"
}
```

For random baseline actions:

```json
{
  "decision_source": "random_baseline",
  "used_fallback": false,
  "fallback_reason": null
}
```

Do not infer `used_fallback` from agent identity.

The safe agent may still use fallback for every action during c003, but the instrumentation must support future mixed policies correctly.

### 7.5 Seed semantics

Replace ambiguous seed naming with explicit fields.

At minimum:

```json
{
  "runner_seed": 0,
  "opponent_policy_seed": 0,
  "requested_engine_seed": 0,
  "engine_rng_controlled": false,
  "engine_rng_note": "..."
}
```

Use `null` when a seed does not apply.

Documentation and reports must state that repeated requested engine seeds do not guarantee identical trajectories unless proven otherwise.

Do not claim trajectory reproducibility.

### 7.6 Canonical deck registry

Deck identity must be based on the multiset of card IDs, not line order.

Canonical representation:

```json
{
  "deck_id": "sha256:...",
  "card_count": 60,
  "cards": [
    {"card_id": 123, "count": 4},
    {"card_id": 456, "count": 2}
  ],
  "source": {
    "path": "...",
    "sha256": "..."
  }
}
```

Requirements:

- `cards` sorted by numeric card ID.
- Counts aggregated.
- Total count validated.
- Reordering identical deck lines produces the same `deck_id`.
- Changing one card produces a different `deck_id`.
- The capture is self-describing: the full canonical deck list must be present in run metadata or a referenced registry artifact included with the run.

Do not treat mutable experimental decks as fixed runtime assets whose hash must always match the original c001/c002 deck.

### 7.7 Observation snapshot timing

Capture/normalize the observation before invoking the policy.

The recorder must ensure that future policy-side mutation cannot change the recorded input.

Acceptable approaches:

- Deep-copy or serialize first.
- Normalize to an immutable JSON-compatible structure before the call.
- Hash before and after and fail if mutation is detected.

The implementation must have a test using a deliberately mutating fake policy.

### 7.8 Semantic replay

For every schema-v2 decision produced by the deterministic safe agent:

1. Load the serialized observation.
2. Validate that top-level context, bounds, option count, and option metadata agree with `observation.select`.
3. Reconstruct the observation representation accepted by the agent.
4. Invoke the safe agent.
5. Compare the returned indices with the recorded action.
6. Report mismatches with run, game, turn/step, context, and record identifiers.

The validator must not merely call the lower-level selector with duplicated top-level bounds.

Where the current cabt helper supports conversion of serialized observations to observation classes, use it and test successful conversion. If exact reconstruction is impossible for a documented engine reason, implement the strongest supported reconstruction and clearly identify the limitation; however, AC-04 still requires actual invocation of the safe agent from the serialized observation.

### 7.9 Cross-field validation

For every decision:

- top-level `select_context` equals `observation.select.context`
- top-level min/max counts equal `observation.select` bounds
- legal-option count equals the serialized option list length
- selected indices satisfy bounds and refer to available options
- required IDs are unique within the run
- game record sequence is valid
- terminal decision count matches observed decisions

Corrupt fixtures must prove these checks fail.

### 7.10 Terminal classification

Terminal classification must inspect final environment/player state, final errors, rewards, and exceptions.

Use structured terminal fields, for example:

```json
{
  "terminal_type": "normal_win",
  "winner": 0,
  "loser": 1,
  "draw": false,
  "timeout_player": null,
  "error_player": null,
  "error": null
}
```

Supported classifications must include, where cabt exposes enough information:

```text
normal_win
draw
timeout
agent_error
environment_error
aborted
unknown
```

Tests must cover at least:

- normal win
- draw or no-winner terminal fixture
- agent error fixture
- timeout fixture or a documented synthetic equivalent

Do not read only the first environment step when classifying terminal state.

### 7.11 Compression and streaming

Capture and validation must support:

- `.jsonl`
- `.jsonl.gz`

Requirements:

- Streaming writes
- Streaming reads
- No full-file load required for validation
- Flush at game terminal
- Configurable periodic flush interval
- Identical semantic validation for compressed and uncompressed files

### 7.12 Runtime/environment verification

Extend runtime verification to check at minimum:

- Python version
- `kaggle-environments` installed version
- platform/machine architecture
- required engine path
- engine SHA-256 and size
- required source/runtime assets
- clear failure messages

Produce a machine-readable environment report.

Do not require the mutable active `deck.csv` to match one historical fixed hash. Validate its syntax and record its canonical identity separately.

---

## 8. Mandatory acceptance criteria

### AC-01 — Schema-v2 lineage completeness

**Requirement**

A schema-v2 capture run contains complete run, Git, capture, environment, engine, agent, seed, and deck lineage as defined above.

**Verification**

Run the schema-v2 capture metadata tests and inspect the generated validation run metadata.

**Required evidence**

```text
results/test_logs/schema_v2_lineage_tests.txt
results/artifacts/validation_run/run_metadata.json
results/artifacts/environment_report.json
```

**Pass condition**

All required fields exist, are non-empty where applicable, and hashes match the files in the reviewed branch/runtime.

---

### AC-02 — Canonical deck identity

**Requirement**

Deck identifiers are order-independent and deck records include complete canonical card counts.

**Verification**

Automated tests must prove:

1. Same multiset in different line order → same deck ID.
2. One-card mutation → different deck ID.
3. Duplicate card lines aggregate correctly.
4. Total count is validated.
5. The validation run references its full deck record.

**Required evidence**

```text
results/test_logs/deck_registry_tests.txt
results/artifacts/deck_registry.json
```

**Pass condition**

All automated tests pass and the generated registry contains every deck used in the validation capture.

---

### AC-03 — Honest seed and decision provenance

**Requirement**

Schema-v2 records do not use ambiguous `game_seed`; they identify controlled and uncontrolled RNG fields and record actual decision source/fallback behavior.

**Verification**

Automated tests plus inspection of all generated records.

**Required evidence**

```text
results/test_logs/provenance_tests.txt
results/artifacts/provenance_summary.json
```

**Pass condition**

- Every game has explicit seed semantics.
- `engine_rng_controlled` is not falsely set to true.
- Every decision has `decision_source`, `used_fallback`, and `fallback_reason`.
- Random baseline and safe fallback records are classified correctly.
- No schema-v2 record contains an ambiguous top-level `game_seed` field unless retained only inside a clearly marked legacy payload.

---

### AC-04 — True semantic replay

**Requirement**

All deterministic safe-agent decisions in the validation dataset are reproduced by reconstructing the serialized observation and invoking the safe agent.

**Verification**

Run the semantic replay validator over both uncompressed and compressed schema-v2 captures.

**Required evidence**

```text
results/test_logs/semantic_replay_jsonl.txt
results/test_logs/semantic_replay_gzip.txt
results/artifacts/semantic_replay_report.json
```

**Pass condition**

- 100% of deterministic safe-agent decisions reproduce exactly.
- Cross-field observation/select consistency passes.
- The validator invokes the safe agent using the serialized observation, not duplicated top-level bounds.
- Any reconstruction limitation is documented, but no mismatch is permitted for the acceptance dataset.

---

### AC-05 — Mutation-safe observation capture

**Requirement**

The stored observation is the observation seen by the policy before policy execution and is not affected by policy mutation.

**Verification**

Automated test with a fake policy that mutates its input.

**Required evidence**

```text
results/test_logs/observation_snapshot_tests.txt
```

**Pass condition**

The stored observation matches the pre-policy input and the mutation is either isolated or explicitly detected and rejected.

---

### AC-06 — Correct terminal classification

**Requirement**

Terminal state is classified from final game state and supports structured normal/error/timeout outcomes.

**Verification**

Automated fixture tests plus inspection of the real validation dataset.

**Required evidence**

```text
results/test_logs/terminal_classification_tests.txt
results/artifacts/terminal_summary.json
```

**Pass condition**

All required synthetic/fixture classifications pass, all real validation games receive structured terminal records, and no implementation relies solely on the first environment step.

---

### AC-07 — Streaming JSONL/GZIP and schema-v1 compatibility

**Requirement**

The system reads/writes schema v2 as plain JSONL and gzip JSONL, validates both by streaming, and reads existing schema-v1 data without inventing missing provenance.

**Verification**

Run compatibility and compression tests, including at least one available c002 schema-v1 file or a fixture faithfully derived from it.

**Required evidence**

```text
results/test_logs/compression_tests.txt
results/test_logs/schema_v1_compatibility_tests.txt
results/artifacts/schema_v1_compatibility_report.json
```

**Pass condition**

- JSONL and GZIP semantic validation produce equivalent counts/results.
- Schema-v1 input is recognized as legacy.
- Missing provenance remains explicitly unavailable.
- Unsupported schema versions fail clearly.

---

### AC-08 — Fresh real cabt validation capture

**Requirement**

Produce a fresh schema-v2 validation dataset from at least 30 completed cabt games:

```text
10 safe_agent as seat 0 vs random_baseline
10 random_baseline as seat 0 vs safe_agent
10 safe_agent vs safe_agent
```

Each cohort must use varying runner/opponent seeds. Do not claim identical engine trajectories.

**Verification**

Run capture, structural validation, semantic replay, and report generation.

**Required evidence**

```text
results/artifacts/validation_run/episodes_v2.jsonl
results/artifacts/validation_run/episodes_v2.jsonl.gz
results/artifacts/validation_run/run_metadata.json
results/artifacts/validation_run/deck_registry.json
results/artifacts/validation_run/validation_report.json
results/artifacts/validation_run/context_report.json
results/artifacts/validation_run/latency_report.json
results/test_logs/validation_capture_command.txt
results/test_logs/validation_capture_validation.txt
```

**Pass condition**

- At least 30 games start and terminate.
- No invalid selections.
- No malformed records.
- Every deterministic safe-agent decision passes semantic replay.
- Every run/game/decision/terminal record has valid lineage.
- Plain and gzip files contain semantically equivalent records.
- Both seats are represented as required.

---

### AC-09 — Clean reproducible Git state

**Requirement**

All source changes required to run schema-v2 capture and validation are committed on the contract branch, and no c001/c002 historical result is modified.

**Verification**

Git report, patch, source snapshot, and clean checkout/run instructions.

**Required evidence**

```text
results/GIT_REPORT.md
results/artifacts/c003.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

**Pass condition**

- Intended source changes are committed.
- Pre-existing user changes are preserved.
- Earlier contract results are untouched.
- Clean-checkout instructions identify external runtime assets and verification steps.
- Final branch HEAD is recorded.
- No unrelated files are committed.

---

## 9. Required deliverables

Create:

```text
contracts/c003_episode_lineage_and_semantic_replay/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── schema_v2_lineage_tests.txt
│   ├── deck_registry_tests.txt
│   ├── provenance_tests.txt
│   ├── semantic_replay_jsonl.txt
│   ├── semantic_replay_gzip.txt
│   ├── observation_snapshot_tests.txt
│   ├── terminal_classification_tests.txt
│   ├── compression_tests.txt
│   ├── schema_v1_compatibility_tests.txt
│   ├── validation_capture_command.txt
│   ├── validation_capture_validation.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── c003.patch
│   ├── CLEAN_CHECKOUT.md
│   ├── environment_report.json
│   ├── deck_registry.json
│   ├── provenance_summary.json
│   ├── semantic_replay_report.json
│   ├── terminal_summary.json
│   ├── schema_v1_compatibility_report.json
│   ├── source_snapshot/
│   └── validation_run/
│       ├── episodes_v2.jsonl
│       ├── episodes_v2.jsonl.gz
│       ├── run_metadata.json
│       ├── deck_registry.json
│       ├── validation_report.json
│       ├── context_report.json
│       └── latency_report.json
└── failures/
```

Additional useful evidence is allowed.

All source files changed by this contract must be copied into:

```text
results/artifacts/source_snapshot/
```

preserving repository-relative paths.

---

## 10. Required reports

### `SUMMARY.md`

Include:

- Final status
- What was implemented
- Number of tests passed/failed
- Number of validation games and decisions
- Number of semantic replay matches/mismatches
- Schema-v1 compatibility result
- Environment and engine identifiers
- Known limitations
- Exact recommendation for c004

Do not call the dataset training-ready unless all mandatory criteria pass.

### `STATUS.json`

Required shape:

```json
{
  "contract": "c003_episode_lineage_and_semantic_replay",
  "status": "PASS",
  "acceptance_criteria_total": 9,
  "acceptance_criteria_passed": 9,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": ["..."],
  "blocking_issues": [],
  "known_limitations": []
}
```

Allowed values:

```text
PASS
PARTIAL
BLOCKED
FAILED
```

### `ACCEPTANCE_CHECKLIST.md`

One section for each AC-01 through AC-09 with:

- Requirement
- Verification command
- Result
- Evidence paths
- Notes

---

## 11. Git requirements

### Before editing

Run and record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

### Branch

Use:

```text
contract/c003_episode_lineage_and_semantic_replay
```

Create it from the current accepted development HEAD.

Do not reset, delete, or overwrite pre-existing user changes.

If current uncommitted changes overlap with contract scope and cannot be preserved safely, set status to `BLOCKED`.

### Commits

Use meaningful commits beginning with:

```text
c003:
```

Recommended grouping:

```text
c003: add schema v2 lineage and canonical deck registry
c003: add semantic replay and terminal validation
c003: add gzip capture and compatibility evidence
```

A different small set of coherent commits is acceptable.

Do not:

- push
- force-push
- rebase shared history
- amend user commits
- use `git reset --hard`
- use destructive clean commands

### Final state

All required source changes must be committed.

Contract results may remain uncommitted if the repository protocol treats `contracts/*/results` as external evidence. Record this clearly.

Record final branch HEAD after all implementation commits.

---

## 12. Stop conditions

Stop and mark `BLOCKED` if:

- c001/c002 source dependencies are missing.
- cabt cannot run because required external runtime assets are unavailable.
- The current working tree has overlapping user changes that cannot be preserved safely.
- Observation reconstruction cannot invoke the existing deterministic safe agent and no technically valid solution exists without changing public contracts outside scope.
- The engine/runtime license or repository policy forbids required handling.

Mark `PARTIAL`, not `PASS`, if:

- Any mandatory acceptance criterion fails.
- Semantic replay mismatches any deterministic safe-agent decision.
- Provenance fields are fabricated or incomplete.
- Terminal classification cannot distinguish required outcomes.
- Clean Git lineage is unavailable.
- The validation dataset is smaller than required.
- Gzip or schema-v1 compatibility is missing.

Do not weaken acceptance criteria or modify this contract.

---

## 13. Final Claude Code response

Return a concise completion message containing:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
Acceptance criteria:
Validation games:
Validation decisions:
Semantic replay:
Schema-v1 compatibility:
Results directory:
Blocking issues:
Known limitations:
Recommended next contract:
```

Do not claim `PASS` unless all nine criteria pass.
