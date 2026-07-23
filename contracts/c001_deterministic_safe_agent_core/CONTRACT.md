# c001 — Deterministic Safe Agent Core

## A. Objective

Implement a deterministic, production-safe baseline agent core for the Pokémon TCG AI Battle Challenge that:

1. returns the configured 60-card deck during deck selection;
2. returns a syntactically valid deterministic list of legal option indices for every valid `Select` object exposed by the cabt API;
3. removes random action selection from the competition entrypoint;
4. completes a substantial cabt integration run without exceptions, invalid selections, or timeouts; and
5. produces complete, reproducible evidence under this contract's `results/` directory.

This contract is complete only when the code exists in the repository, automated tests pass, integration games complete, metrics are generated, and all intended source changes are committed.

The implementation is a **safety baseline**, not a strategy agent. It may choose strategically poor actions, but it must choose deterministically and legally for every valid engine observation encountered.

---

## B. Context

`c000_repository_audit_and_baseline` completed with status `PASS` and established the following facts:

- The competition entrypoint is `starter_kit/main.py:agent(obs_dict)`.
- The deck is `starter_kit/deck.csv` and contains exactly 60 card IDs.
- `cg.api.to_observation_class` converts the harness observation dictionary.
- A non-deck observation exposes `obs.select.option`, `minCount`, `maxCount`, and `context`.
- The current baseline uses `random.sample(range(len(option)), maxCount)`.
- `kaggle_environments.make("cabt")` is the verified integration harness.
- Python is available through `.venv/bin/python`.
- The baseline completed 10/10 random-agent games.
- `starter_kit/`, `cg`, and several competition assets were pre-existing untracked working-tree entries during c000.

The highest-priority c000 risk was that legal-action behavior had not been isolated, validated, or made deterministic.

This contract depends on c000's successful baseline, but must independently inspect the real repository files before implementation. The reference files included with this contract are summaries, not substitutes for the repository source or cabt API.

---

## C. Inputs

Claude Code may use:

- `contracts/c001_deterministic_safe_agent_core/CONTRACT.md`
- `contracts/c001_deterministic_safe_agent_core/references/c000_status.json`
- `contracts/c001_deterministic_safe_agent_core/references/c000_summary.md`
- `contracts/c001_deterministic_safe_agent_core/references/c000_risks.md`
- `starter_kit/main.py`
- `starter_kit/deck.csv`
- `starter_kit/api.py`
- `starter_kit/game.py`
- `starter_kit/sim.py`
- `starter_kit/utils.py`
- root `cg` package/symlink
- `test_engine.py`
- the installed `kaggle_environments` cabt environment
- the existing `.venv`

All paths are relative to the repository root.

Do not download additional code, models, datasets, or dependencies. Do not use network access.

---

## D. Scope

### Required project changes

Implement the safe deterministic selection core in these locations unless an existing equivalent module is already present:

- `starter_kit/safe_policy.py` — deterministic selection and validation logic.
- `starter_kit/main.py` — competition agent entrypoint using the safe policy instead of randomness.
- `tests/test_safe_policy.py` — selector unit and property-style tests using only the standard library.
- `tests/test_agent_integration.py` — entrypoint/deck/integration-facing tests that do not run a large benchmark.
- `tools/benchmark_safe_agent.py` — reproducible cabt benchmark and context-coverage script.

Small supporting files under `tests/` or `tools/` are allowed if necessary. Do not create a broad framework.

### Required behavior

The public `agent(obs_dict)` function must:

1. Convert the observation with the existing official conversion function.
2. Return the validated 60-card deck when `obs.select is None`.
3. For a normal selection, return a `list[int]` containing distinct indices.
4. Return only indices in `[0, len(obs.select.option))`.
5. Return a count accepted by the engine for valid observations.
6. Produce the same output for the same observation every time.
7. Use no random-number generation.
8. Avoid absolute local filesystem paths.

### Deterministic fallback rule

Start from the existing baseline's empirically accepted convention: select exactly `maxCount` distinct options. The default deterministic choice should be the first `maxCount` legal option indices in engine order:

```python
list(range(max_count))
```

However, do not copy this blindly. Inspect the real API fields and integration behavior. Centralize all count validation in one function and ensure:

- counts are integer-like and non-negative;
- `minCount <= maxCount`;
- `maxCount <= number_of_options` for a valid observation;
- zero-count selections return `[]`;
- duplicate and out-of-range indices are impossible;
- malformed internal test inputs raise one explicit, documented internal exception rather than failing unpredictably.

The public agent is required to be safe for **valid cabt observations**. Do not fabricate a supposedly legal action when the engine presents an impossible state such as `minCount > len(option)`. Such a condition must be logged and treated as an invalid observation in tests. Do not hide engine-contract violations.

### Compatibility

Preserve compatibility with the current competition packaging/import pattern. `starter_kit/main.py` must still work in the verified local harness and when used as a normal Kaggle agent entrypoint.

If imports differ between package execution and submission-root execution, implement the smallest clear compatibility solution and test both import modes where feasible. Do not copy the engine or create a second API implementation.

---

## E. Non-goals

Do not implement any of the following:

- Strategic action scoring
- Context-specific gameplay heuristics
- Deck changes or deck optimization
- MCTS, beam search, rollout search, or `search_*` use
- Reinforcement learning or model training
- LLM integration
- Episode-dataset ingestion
- Submission tarball production
- Refactoring the cabt API, engine bindings, or game driver
- New external dependencies
- Broad repository cleanup
- Changes to card data or PDFs
- Changes to `libcg.so`

Do not optimize win rate. This contract is about legality, determinism, integration safety, and evidence.

---

## F. Implementation Requirements

### F-01 — Safe-policy module

Create a small, typed module containing at least:

- an explicit exception type for malformed selection metadata;
- a pure function that receives the selection metadata or `Select` object and returns deterministic indices;
- a pure function that validates returned indices against option count and selection bounds;
- deck loading/validation logic, or a clearly separated validated deck loader if it remains in `main.py`.

The selector must not depend on global random state, current time, dictionary hash iteration, or mutable hidden state.

### F-02 — Competition entrypoint

Update `starter_kit/main.py` so that:

- the public function remains named `agent`;
- it uses `to_observation_class`;
- deck selection returns the validated deck;
- normal action selection delegates to the safe-policy module;
- `random` is not imported or used;
- no debug output is printed during normal agent calls;
- module import does not execute games or benchmarks.

### F-03 — Deck validation

Validate at minimum:

- exactly 60 entries;
- every non-empty line is parseable as an integer card ID;
- no silent omission of malformed lines;
- path resolution is relative to the module/repository, not a user-specific absolute path.

Tests must cover an invalid deck length and at least one malformed card ID.

### F-04 — Unit tests

Use the Python standard library `unittest`; do not add pytest or another dependency.

Tests must cover:

- zero options with `minCount=maxCount=0`;
- one option with an exact one-card selection;
- multiple options with an exact one-card selection;
- multiple options with a multi-card selection;
- deterministic repeated calls;
- no duplicates;
- all returned indices in range;
- invalid negative counts;
- `minCount > maxCount`;
- `maxCount > len(options)`;
- deck validation success and failure;
- every member of the real `SelectContext` enum through a synthetic selection object or another context-independent fixture, proving that context identity does not break the generic safety selector.

Do not claim engine coverage for contexts that were not encountered in integration games. Distinguish **enum-level selector coverage** from **runtime-observed context coverage**.

### F-05 — Integration benchmark

Create `tools/benchmark_safe_agent.py` with a deterministic command-line interface.

It must run exactly these three cohorts by default:

1. 100 games: safe agent as player 0, existing random legal baseline as player 1.
2. 100 games: random legal baseline as player 0, safe agent as player 1.
3. 100 games: safe agent versus safe agent.

Total default: **300 completed games**.

The benchmark must:

- use `kaggle_environments.make("cabt")`;
- use the same validated deck for both players unless the harness requires otherwise;
- capture exceptions and identify the game/cohort;
- verify terminal statuses for both players;
- instrument safe-agent calls without altering returned actions;
- report total agent calls;
- report minimum, mean, P50, P95, P99, and maximum safe-agent call latency;
- report per-cohort games completed and failed;
- report per-cohort rewards/wins/losses if available;
- report encountered `SelectContext` names and counts;
- report selection-size pairs such as `(minCount, maxCount)` and counts;
- report zero invalid selections;
- write machine-readable JSON to the output path supplied by CLI;
- be reproducible enough for regression use, while acknowledging that engine randomness may prevent identical game trajectories.

Do not require every enum context to occur during the 300 games.

### F-06 — No silent fallback to randomness

Search the implementation and tests for `random`, `randint`, `choice`, `sample`, NumPy RNG, or equivalent use in the safe agent path. The benchmark's intentionally random opponent is allowed and must be clearly isolated from the safe agent implementation.

### F-07 — Documentation

Add concise module docstrings and comments describing:

- what “safe” guarantees;
- what it does not guarantee;
- why engine option order is used;
- how malformed observations are handled.

Avoid lengthy strategy discussion in project source.

---

## G. Acceptance Criteria

### AC-01 — Deterministic safe selector exists and is isolated

**Pass condition:**
A pure deterministic selector and explicit validation logic exist in `starter_kit/safe_policy.py` or an approved equivalent location. No randomness appears in the safe-agent call path.

**Verification:**

```bash
.venv/bin/python -m unittest tests.test_safe_policy -v
```

Also run a source search for random-number use in the safe-agent path.

**Required evidence:**

- `results/test_logs/unit_safe_policy.txt`
- `results/test_logs/randomness_audit.txt`
- source snapshots under `results/artifacts/source_snapshot/`

### AC-02 — All SelectContext enum members are selector-compatible

**Pass condition:**
A standard-library unit test iterates every real `SelectContext` enum member and verifies that context identity does not alter or break legal deterministic index generation for valid synthetic bounds.

This criterion proves generic selector compatibility, not that every gameplay context was reached in live games.

**Verification:**

```bash
.venv/bin/python -m unittest tests.test_safe_policy -v
```

**Required evidence:**

- `results/test_logs/unit_safe_policy.txt`
- `results/artifacts/enum_context_coverage.json`

The JSON must list every discovered enum member and the total count.

### AC-03 — Deck selection is validated and deterministic

**Pass condition:**
The entrypoint returns exactly the same 60 integer card IDs on repeated deck-selection calls. Invalid deck length and malformed card contents are rejected in tests.

**Verification:**

```bash
.venv/bin/python -m unittest tests.test_agent_integration -v
```

**Required evidence:**

- `results/test_logs/unit_agent_integration.txt`
- `results/artifacts/deck_validation.json`

### AC-04 — Full unit-test suite passes

**Pass condition:**
All repository tests introduced by c001 pass with zero failures and zero errors.

**Verification:**

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

**Required evidence:**

- `results/test_logs/unittest_all.txt`

### AC-05 — 300-game cabt benchmark completes

**Pass condition:**
All 300 required games complete with both players terminal, zero uncaught exceptions, and zero invalid safe-agent selections.

**Verification:**

```bash
.venv/bin/python tools/benchmark_safe_agent.py \
  --games-per-cohort 100 \
  --output contracts/c001_deterministic_safe_agent_core/results/artifacts/safe_agent_benchmark.json
```

**Required evidence:**

- `results/test_logs/benchmark_safe_agent.txt`
- `results/artifacts/safe_agent_benchmark.json`
- `results/artifacts/runtime_context_coverage.json`

`runtime_context_coverage.json` must clearly identify contexts observed and contexts not observed, based on the actual `SelectContext` enum.

### AC-06 — Runtime overhead is measured and bounded

**Pass condition:**
The benchmark reports safe-agent call latency statistics. P99 safe-agent call latency must be below **10 milliseconds** on the local c000 environment. If P99 is at or above 10 ms, the contract cannot receive `PASS`; it must be `PARTIAL` with profiling evidence.

The game engine's own elapsed time must not be included as safe-agent call latency.

**Verification:**
Use the benchmark command from AC-05.

**Required evidence:**

- latency fields in `safe_agent_benchmark.json`;
- a human-readable latency summary in `results/SUMMARY.md`.

### AC-07 — Competition entrypoint remains compatible

**Pass condition:**
The updated `starter_kit/main.py:agent` runs through the verified cabt harness as both player 0 and player 1 without import errors or interface changes.

**Verification:**
Satisfied by AC-05 and an explicit entrypoint smoke test in `tests/test_agent_integration.py`.

**Required evidence:**

- `results/test_logs/unit_agent_integration.txt`
- `results/test_logs/benchmark_safe_agent.txt`

### AC-08 — Git changes are complete and isolated

**Pass condition:**
All intended c001 implementation and test changes are committed on the c001 contract branch. No pre-existing unrelated changes, binary engine files, PDFs, virtual environments, scratch files, or unrelated untracked files are staged or committed.

**Verification:**
Inspect Git report and diff statistics.

**Required evidence:**

- `results/GIT_REPORT.md`
- `results/FILES_CHANGED.md`
- `results/artifacts/committed_diff.patch`

The patch must contain only the c001-relevant text changes and may omit generated result logs if those are committed separately.

---

## H. Required Deliverables

Claude Code must populate:

```text
contracts/c001_deterministic_safe_agent_core/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── unit_safe_policy.txt
│   ├── unit_agent_integration.txt
│   ├── unittest_all.txt
│   ├── benchmark_safe_agent.txt
│   └── randomness_audit.txt
├── artifacts/
│   ├── safe_agent_benchmark.json
│   ├── runtime_context_coverage.json
│   ├── enum_context_coverage.json
│   ├── deck_validation.json
│   ├── committed_diff.patch
│   └── source_snapshot/
│       ├── starter_kit_main.py
│       ├── starter_kit_safe_policy.py
│       ├── test_safe_policy.py
│       ├── test_agent_integration.py
│       └── benchmark_safe_agent.py
└── failures/
    └── NONE.md or concrete failure files
```

If an approved equivalent source path is used, preserve the required snapshot filenames above and explain the mapping in `FILES_CHANGED.md`.

### `STATUS.json`

Use this schema:

```json
{
  "contract": "c001_deterministic_safe_agent_core",
  "status": "PASS",
  "acceptance_criteria_total": 8,
  "acceptance_criteria_passed": 8,
  "acceptance_criteria_failed": 0,
  "commit_hashes": ["..."],
  "blocking_issues": [],
  "benchmark": {
    "games_required": 300,
    "games_completed": 300,
    "invalid_safe_selections": 0,
    "safe_agent_calls": 0,
    "latency_ms": {
      "p50": 0.0,
      "p95": 0.0,
      "p99": 0.0,
      "max": 0.0
    },
    "runtime_contexts_observed": 0,
    "enum_contexts_total": 0
  }
}
```

Populate real values. Do not retain placeholder zeroes except where the true value is zero.

### Review payload

Copy the exact final versions of all changed implementation, test, and benchmark source files into `results/artifacts/source_snapshot/`. The snapshots are for review only; the repository files remain authoritative.

---

## I. Git Requirements

### Initial inspection

Before modifying anything, run and record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
```

### Dirty tree protection

The c000 audit found pre-existing untracked files. Do not stage or alter them unless they are an exact required c001 source path.

In particular, do not accidentally stage:

- `starter_kit/libcg.so`
- card PDFs or the full card-data directory
- `.venv/`
- `tmp.txt`
- `check.py`
- unrelated symlinks or binaries

`starter_kit/main.py` is an expected c001 path even if it was previously untracked. Stage it deliberately by exact path. Stage only the exact text files required by this contract.

If there are pre-existing modifications to any required c001 file, inspect them. Preserve them if compatible. If they overlap in a way that makes safe attribution impossible, set status `BLOCKED`; do not overwrite or reset them.

Never run destructive commands such as:

```bash
git reset --hard
git clean -fd
git checkout -- <user-file>
```

### Branch

Create:

```text
contract/c001_deterministic_safe_agent_core
```

from the currently checked-out commit after initial inspection.

If this branch already exists unexpectedly, do not delete, reset, or overwrite it. Inspect it and stop as `BLOCKED` unless it is clearly the current unfinished execution of this exact contract.

### Commits

Create at least one implementation commit and one evidence commit:

```text
c001: add deterministic safe agent core
c001: add safe agent validation evidence
```

The implementation commit should contain only source and tests required by c001.

The evidence commit may contain this contract folder's result reports, small JSON artifacts, text logs, and source snapshots. Do not commit large binary artifacts.

Every intended c001 source change must be committed. Do not push, merge, rebase, amend existing commits, force-push, or alter remotes.

### Final evidence

Record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline --decorate -5
git diff --stat <initial-head>..HEAD
git diff --check <initial-head>..HEAD
```

Generate:

```bash
git diff <initial-head>..<implementation-commit> -- \
  starter_kit/main.py starter_kit/safe_policy.py tests tools \
  > contracts/c001_deterministic_safe_agent_core/results/artifacts/committed_diff.patch
```

Adjust exact paths if an approved equivalent path was necessary.

---

## J. Stop Conditions

Stop and report `BLOCKED` rather than improvising if:

1. The verified cabt environment is unavailable and cannot import or start.
2. Required starter-kit files are missing.
3. Existing user changes overlap required files and cannot be preserved safely.
4. The contract branch already exists with unrelated or ambiguous work.
5. The engine repeatedly produces internally impossible selection bounds.
6. Running the required benchmark risks destructive changes or external access.

Report `PARTIAL`, not `PASS`, if:

1. Unit tests pass but fewer than 300 games complete.
2. Any safe-agent selection is invalid.
3. Any required cohort has failures.
4. P99 safe-agent call latency is at least 10 ms.
5. Runtime context coverage cannot be collected.
6. Required evidence is missing.
7. Intended source changes are not fully committed.

Do not weaken acceptance criteria or edit this contract to claim success.

---

## K. Final Response Format

Claude Code's final terminal/chat response must be concise and use exactly this structure:

```text
Contract: c001_deterministic_safe_agent_core
Status: PASS | PARTIAL | BLOCKED | FAILED
Branch: <branch>
Commits:
- <hash> <message>
- <hash> <message>

Acceptance: <passed>/<total>
Benchmark: <completed>/<required> games; <invalid> invalid selections
Safe-agent latency: P50=<...> ms, P95=<...> ms, P99=<...> ms, max=<...> ms
Runtime contexts: <observed>/<enum total> observed

Results: contracts/c001_deterministic_safe_agent_core/results/
Blocking issues: none | <brief list>
```

Do not claim `PASS` unless all eight mandatory acceptance criteria pass and the evidence files exist.
