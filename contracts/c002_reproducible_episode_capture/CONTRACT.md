# c002 — Reproducible Runtime and Episode Capture

## 1. Objective

Convert the c001 deterministic safe-agent baseline into a reproducible, inspectable platform for future strategy work.

When this contract is complete, a reviewer must be able to:

1. Verify all required runtime assets from a machine-readable manifest.
2. Run the safe agent without tests mutating historical contract results.
3. Capture complete game trajectories to a documented, versioned JSONL format.
4. Load captured trajectories back without loss of required fields.
5. Re-run a deterministic validation suite and inspect context coverage, latency, seeds, seats, and terminal outcomes.
6. Reproduce the implementation from the Git branch plus the declared external runtime assets.

This contract must produce working code and executed evidence. A prose-only audit is not an acceptable result.

---

## 2. Context

The previous contract, `c001_deterministic_safe_agent_core`, produced a deterministic legal fallback agent and reported:

- 30/30 tests passed.
- 300/300 games completed.
- Zero invalid selections.
- Very low steady-state policy latency.
- Runtime observation of only a subset of the available `SelectContext` values.

The c001 review identified these issues:

1. The implementation depends on untracked runtime assets such as the `cg` path, starter-kit files, deck data, and the native cabt library.
2. A clean checkout cannot currently prove that it contains everything required to run.
3. Unit tests write contract evidence into `contracts/c001.../results/`, mutating historical results.
4. Deck validation is syntactic rather than semantic or engine-backed.
5. Benchmark opponent seeds are reused too narrowly.
6. Episode-level observations, legal options, selected actions, seats, seeds, and outcomes are not captured in a reusable dataset.
7. Runtime coverage exists for only a subset of selection contexts.

This contract addresses the platform and data issues. It does not add competitive strategy.

---

## 3. Dependencies

This contract depends on:

- The accepted source implementation from `c001_deterministic_safe_agent_core`.
- The locally available cabt competition runtime and starter-kit assets.
- A working Git repository.
- A Python environment capable of running the existing c001 tests and local cabt games.

Claude Code must inspect the repository before assuming exact file locations. Known likely paths include:

- `starter_kit/main.py`
- `starter_kit/safe_policy.py`
- `starter_kit/deck.csv`
- `starter_kit/api.py`
- `starter_kit/libcg.so`
- `cg`
- Existing c001 tests and benchmark scripts

If actual paths differ, use the repository’s existing structure and document the differences.

---

## 4. Inputs

Read-only contract inputs:

- `contracts/c002_reproducible_episode_capture/inputs/c001_review_findings.md`
- `contracts/c002_reproducible_episode_capture/references/results_protocol.md`

Repository inputs:

- Current source tree.
- Existing c001 implementation, tests, logs, and benchmark utilities.
- Locally available competition runtime assets.

Do not modify this contract, its `inputs/`, or its `references/`.

---

## 5. Scope

Implement the following capabilities.

### 5.1 Runtime asset manifest

Create a machine-readable manifest for every non-standard asset required to run the local agent and tests.

Preferred path:

```text
runtime_assets.json
```

Each entry must include:

- Logical name
- Repository-relative expected path
- Required or optional
- Asset type: source, data, symlink, binary, generated, or external
- Expected file/directory/symlink kind
- Expected size where stable
- SHA-256 for stable files where practical
- Symlink target where applicable
- Whether the asset must be tracked by Git
- Human-readable acquisition or reconstruction instructions

Do not copy copyrighted or competition-restricted binaries into Git unless the repository already tracks them and doing so is clearly permitted.

### 5.2 Runtime verification command

Create a command-line verifier, preferably:

```text
tools/verify_runtime_assets.py
```

It must:

- Load the manifest.
- Validate presence and type.
- Validate symlink targets.
- Validate SHA-256 where supplied.
- Print a concise PASS/FAIL table.
- Exit `0` only when all required assets pass.
- Exit nonzero with actionable messages when required assets are missing or invalid.
- Support a machine-readable JSON output option.

### 5.3 Reproducible setup documentation

Create or update concise documentation describing how a clean checkout becomes runnable.

It must distinguish:

- Git-tracked source/configuration.
- External competition/runtime assets.
- Generated artifacts.
- Verification command.
- Exact test command.
- Exact one-game command.
- Exact episode-capture command.

Do not write vague instructions such as “copy the necessary files.” State exact paths and commands.

### 5.4 Remove test side effects

Refactor tests so ordinary test execution does not write into any historical contract folder.

Rules:

- Unit tests must use temporary directories or in-memory data.
- Contract evidence generation must be performed by explicit scripts or commands, not implicit test side effects.
- Running the full test suite twice must not alter tracked source files or previously completed contract result folders.

### 5.5 Versioned episode capture

Implement a reusable game/decision capture layer.

Preferred module location:

```text
starter_kit/episode_capture.py
```

or an equally clear project module.

The capture format must be newline-delimited JSON (`.jsonl`) with one record per agent decision plus explicit game metadata and terminal information.

Every decision record must include at least:

- `schema_version`
- `game_id`
- `decision_index`
- `player_index`
- `seat`
- `game_seed`
- `agent_name`
- `deck_identifier`
- `timestamp_monotonic_ns` or equivalent monotonic timing field
- Serialized observation sufficient for offline analysis
- Selection context name and numeric value when available
- Legal option count
- Legal option metadata sufficient to distinguish choices
- `min_count`
- `max_count`
- Selected indices
- Policy latency in nanoseconds or milliseconds
- Whether fallback logic was used
- Validation status

The game-level metadata or terminal record must include:

- Both agents
- Both deck identifiers
- Initial seat assignment
- Seed
- Winner
- Terminal reason where available
- Number of decisions by each agent
- Game duration
- Invalid-selection count
- Error/exception status

Do not serialize Python objects using unsafe pickle. Use portable JSON-compatible data.

If the cabt observation cannot be fully serialized directly, create a documented normalization function. Preserve raw fields where JSON-compatible and record explicitly omitted fields.

### 5.6 Round-trip loader and validator

Implement a loader/validator, preferably:

```text
tools/validate_episode_jsonl.py
```

It must:

- Stream records without loading the entire file into memory.
- Validate schema version and required fields.
- Validate game and decision ordering.
- Validate selected indices against recorded legal bounds.
- Validate terminal summaries against decision counts.
- Report malformed records with line numbers.
- Produce JSON and human-readable summaries.
- Exit nonzero on validation failure.

### 5.7 Seed and seat discipline

Update the benchmark/capture runner so every game has a recorded unique seed derived deterministically from a base seed and game index.

Requirements:

- Do not reinitialize all opponents with the identical random sequence for every game.
- Record every actual seed.
- Run both seat assignments.
- Make repeated runs with the same base seed reproducible.

### 5.8 Context coverage report

Generate a coverage report from captured decisions.

It must show:

- All enum-defined selection contexts.
- Runtime-observed count per context.
- Number and percentage observed.
- Decision count per seat.
- Fallback usage per context.
- Invalid selection count per context.
- P50/P95/P99/max policy latency per context when sample count permits.
- Explicit list of contexts not observed.

### 5.9 Source snapshots for review

Copy every created or modified source/test/configuration file into:

```text
contracts/c002_reproducible_episode_capture/results/artifacts/source_snapshot/
```

Preserve repository-relative paths under that directory.

Also include a patch:

```text
results/artifacts/c002.patch
```

created from the contract branch against the initial contract base commit.

---

## 6. Non-goals

Do not:

- Add deck strategy or context-specific tactical rules.
- Add MCTS, beam search, RL, neural networks, or LLM integration.
- Change the competition deck except where required to prove existing deck validity.
- Optimize win rate.
- Interpret safe-agent win rates as strategic strength.
- Rewrite the repository structure broadly.
- Introduce a database or heavy data framework.
- Commit large episode datasets or native binaries unless explicitly already tracked and appropriate.
- Modify c000 or c001 contract results.
- Push to any remote.

---

## 7. Implementation constraints

1. Preserve the c001 deterministic fallback behavior.
2. All agent decisions must remain legal and deterministic for identical observations.
3. Prefer Python standard library unless an existing project dependency is clearly appropriate.
4. JSONL schema must be documented and versioned as `1` or `1.0`.
5. Capture must be optional and must not materially complicate the core selector.
6. Capture failures must not silently corrupt files. Use flush/close discipline and report errors.
7. No secrets, machine-specific absolute paths, or personal identifiers may be written into tracked files or results.
8. Use UTF-8 explicitly for text files.
9. Generated episode files must be excluded from Git unless they are tiny fixtures.
10. Add or update `.gitignore` narrowly for generated data, without masking source or evidence files.
11. Every verification command must be runnable from the repository root.
12. Maintain backwards compatibility with the c001 entrypoint unless a change is unavoidable and documented.

---

## 8. Required tests

Add automated tests covering at least:

1. Runtime manifest loading.
2. Successful required-asset validation in the current environment.
3. Failure behavior for a missing required asset.
4. Symlink validation where applicable.
5. Stable deterministic seed derivation.
6. Episode decision serialization.
7. Terminal record serialization.
8. JSONL round-trip loading.
9. Detection of malformed JSON.
10. Detection of out-of-bounds selected indices.
11. Detection of inconsistent game/decision ordering.
12. No writes to historical contract result folders during normal unit tests.
13. Deterministic safe-agent behavior remains unchanged.

Tests may use small synthetic fixtures, but the integration criteria below must use the real cabt runtime.

---

## 9. Mandatory acceptance criteria

### AC-01 — Runtime assets are reproducibly declared

**Requirement**

A machine-readable manifest declares every asset needed for the c001 agent, tests, and local cabt execution.

**Verification**

Run the runtime verifier in human-readable and JSON modes.

**Pass conditions**

- Every required asset present in the current environment passes.
- A deliberately missing required-asset fixture causes a nonzero exit.
- The output distinguishes tracked, external, generated, and symlink assets.

**Evidence**

- `results/artifacts/runtime_assets.json`
- `results/test_logs/runtime_assets_human.txt`
- `results/artifacts/runtime_assets_verification.json`
- `results/test_logs/runtime_assets_negative_test.txt`

### AC-02 — Clean reproducibility procedure exists

**Requirement**

A reviewer can follow exact documented steps from a clean checkout plus declared external assets to run tests and one cabt game.

**Verification**

Execute the documented verification and one-game commands from the repository root.

**Pass conditions**

- Commands are explicit and succeed in the current environment.
- Documentation identifies any asset that cannot be committed and how to provide it.

**Evidence**

- `results/artifacts/REPRODUCIBILITY.md`
- `results/test_logs/clean_reproduction_commands.txt`

### AC-03 — Tests are side-effect free

**Requirement**

Running the normal automated test suite does not modify c000/c001 results or tracked source files.

**Verification**

1. Record hashes or Git status before tests.
2. Run the full relevant test suite twice.
3. Compare after each run.

**Pass conditions**

- Both runs pass.
- No historical contract result file changes.
- No tracked source file changes.
- No evidence files are created outside temporary directories by unit tests.

**Evidence**

- `results/test_logs/tests_run_1.txt`
- `results/test_logs/tests_run_2.txt`
- `results/test_logs/test_side_effect_check.txt`

### AC-04 — Episode JSONL capture works on real games

**Requirement**

Capture at least 60 completed real cabt games with complete decision and terminal records.

**Required cohorts**

- 20 safe-agent vs safe-agent games, balanced across seats.
- 20 safe-agent vs existing random/baseline opponent games, safe agent in seat 0.
- 20 safe-agent vs existing random/baseline opponent games, safe agent in seat 1.

**Pass conditions**

- 60/60 games complete, unless a genuine cabt/runtime blocker is documented.
- Every game has a unique recorded seed.
- Re-running a 5-game deterministic subset with the same base seed reproduces the same seeds, seat assignments, decision counts, and winners.
- Zero invalid safe-agent selections.
- Every game has a terminal record.

**Evidence**

- `results/artifacts/episodes/` containing JSONL files or one clearly indexed JSONL file.
- `results/artifacts/episode_run_summary.json`
- `results/test_logs/episode_capture_run.txt`
- `results/test_logs/deterministic_replay_check.txt`

Do not commit the large generated episode files to Git unless the contract branch already treats such evidence as tracked. They must still be present in the contract results package.

### AC-05 — Episode round-trip validation passes

**Requirement**

Every captured episode record passes the streaming loader and validator.

**Pass conditions**

- Zero malformed records.
- Zero out-of-bounds recorded selections.
- Decision ordering is valid for every game.
- Terminal decision counts agree with captured records.
- Validator returns exit code 0.

**Evidence**

- `results/test_logs/episode_validation.txt`
- `results/artifacts/episode_validation.json`

### AC-06 — Context and latency report is generated

**Requirement**

Produce a complete report covering all enum-defined contexts and runtime-observed contexts.

**Pass conditions**

- Every enum-defined context appears in the report, including zero-count contexts.
- Seat counts, fallback counts, invalid counts, and latency percentiles are reported.
- The report clearly distinguishes enum coverage from real runtime coverage.

**Evidence**

- `results/artifacts/context_coverage.json`
- `results/artifacts/context_coverage.csv`
- `results/artifacts/CONTEXT_COVERAGE.md`

### AC-07 — Automated test suite passes

**Requirement**

All new and existing relevant tests pass.

**Pass conditions**

- No skipped mandatory tests.
- At least the thirteen required test categories in Section 8 are represented.
- Existing c001 deterministic-selector tests remain passing.

**Evidence**

- `results/test_logs/pytest_full.txt`
- `results/artifacts/test_inventory.json`

### AC-08 — Git state is reviewable and reproducible

**Requirement**

All intended source, test, configuration, manifest, and documentation changes are committed on the contract branch. Pre-existing user changes and prohibited external binaries are not included.

**Pass conditions**

- Branch name is correct.
- Contract implementation has one or more commits beginning with `c002:`.
- Final Git status is explained line by line.
- A patch from the initial base commit is included.
- The final branch head is recorded.
- Runtime assets required but not tracked are declared in the manifest.

**Evidence**

- `results/GIT_REPORT.md`
- `results/artifacts/c002.patch`
- `results/artifacts/source_snapshot/`

---

## 10. Optional stretch goals

These do not affect PASS status:

1. Capture at least 100 games instead of 60.
2. Collect real observations for additional previously unseen contexts.
3. Add gzip support for JSONL while retaining streaming validation.
4. Add a compact anonymized episode fixture for CI.
5. Produce a lightweight HTML coverage report without adding a heavy dependency.

Do not pursue stretch goals before all mandatory criteria pass.

---

## 11. Required deliverables

Claude Code must populate:

```text
contracts/c002_reproducible_episode_capture/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
├── artifacts/
│   ├── runtime_assets.json
│   ├── runtime_assets_verification.json
│   ├── REPRODUCIBILITY.md
│   ├── episode_run_summary.json
│   ├── episode_validation.json
│   ├── context_coverage.json
│   ├── context_coverage.csv
│   ├── CONTEXT_COVERAGE.md
│   ├── test_inventory.json
│   ├── c002.patch
│   ├── episodes/
│   └── source_snapshot/
└── failures/
```

If a required artifact cannot be produced, status cannot be `PASS`. Put detailed diagnostics under `failures/`.

---

## 12. Results file requirements

### `STATUS.json`

Use this structure:

```json
{
  "contract": "c002_reproducible_episode_capture",
  "status": "PASS",
  "acceptance_criteria_total": 8,
  "acceptance_criteria_passed": 8,
  "acceptance_criteria_failed": 0,
  "initial_head": "<hash>",
  "final_head": "<hash>",
  "implementation_commits": ["<hash>"],
  "blocking_issues": [],
  "known_limitations": []
}
```

Allowed statuses:

- `PASS`
- `PARTIAL`
- `BLOCKED`
- `FAILED`

`PASS` is allowed only when all eight mandatory acceptance criteria pass.

### `SUMMARY.md`

Include:

- Objective
- Implemented capabilities
- Exact runtime asset policy
- Episode schema overview
- Integration results
- Context coverage result
- Known limitations
- Recommended next contract

### `GIT_REPORT.md`

Include:

- Initial branch and initial HEAD
- Contract branch and final HEAD
- Initial and final `git status --short`
- Every contract commit hash and message
- `git diff --stat` from initial HEAD to final HEAD
- Explanation of every remaining untracked/modified path
- Confirmation that no c000/c001 results were modified
- Confirmation that no destructive Git command was used

---

## 13. Git requirements

### Before work

Run and record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

### Branch

Use exactly:

```text
contract/c002_reproducible_episode_capture
```

Create it from the current checked-out commit.

If the branch already exists, inspect it. Do not overwrite or reset it destructively.

### Dirty working tree

Do not discard, overwrite, stage, or commit pre-existing user changes.

If pre-existing changes overlap contract files and cannot be safely separated, stop with status `BLOCKED` and document the conflict.

Never run:

```text
git reset --hard
git clean -fd
git checkout -- <user file>
git restore <user file>
```

or any equivalent destructive command.

### Commits

Use a small number of meaningful commits. Required prefixes:

```text
c002: add reproducible runtime asset verification
c002: add versioned episode capture and validation
c002: add integration evidence and reports
```

The exact split may vary, but every contract commit must begin with `c002:`.

Do not push, force-push, rebase, amend user commits, or change remotes.

### Evidence commits

Source/test/configuration changes must be committed.

Generated large episode files under the contract `results/` directory should normally remain uncommitted unless the repository explicitly tracks contract evidence. Record their hashes in the reports.

Do not create a commit whose sole purpose is to record its own future hash. Record:

- Initial HEAD
- Implementation commit hashes
- Final HEAD after implementation commits

The contract result package itself can record those hashes without requiring a self-referential evidence commit.

---

## 14. Stop conditions

Stop and set status to `BLOCKED` when:

- The cabt runtime cannot be executed and no safe local fix exists.
- Required external assets are absent and cannot be identified precisely.
- Pre-existing user changes overlap contract scope and cannot be isolated safely.
- The observation object cannot be serialized sufficiently for the required episode format without changing competition runtime behavior.
- Running required games would require destructive or prohibited actions.

Set status to `PARTIAL` when meaningful implementation is complete but one or more acceptance criteria cannot be verified because of a clearly external limitation.

Do not improvise strategy logic to work around a platform issue.

---

## 15. Final response format

Claude Code’s final message must contain only:

1. Contract status.
2. Acceptance criteria passed/total.
3. Contract branch.
4. Final HEAD.
5. Short list of implemented capabilities.
6. Short list of blockers or known limitations.
7. Exact path to the populated results folder.

Do not claim success that is not supported by files in `results/`.
