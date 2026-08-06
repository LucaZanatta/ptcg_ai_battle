# c004 — Competitive Baseline Gauntlet

## 1. Winning objective

This contract must identify the strongest currently available **complete deck–agent pair** that can serve as the competitive baseline for all subsequent improvements.

This is not an infrastructure contract and must not end with only code, charts, or observations.

The contract must finish with:

1. One explicitly selected **primary baseline**.
2. One explicitly selected **backup baseline**.
3. Explicitly rejected or non-admitted candidates with reasons.
4. A balanced matchup matrix and uncertainty estimates.
5. Reliability and latency evidence.
6. A concrete, evidence-based policy-improvement hypothesis for `c005`.

Before the gauntlet, apply only the narrow c003 amendments required for trustworthy competitive evaluation.

No candidate may be strategically improved during this contract.

---

## 2. Objective

Implement and execute a reproducible competitive gauntlet over three or four complete deck–agent pairs.

The contract must:

- Correct three c003 evaluation-integrity defects.
- Discover, register, freeze, and validate candidate pairs.
- Compare candidates without changing their strategy.
- Run every admitted candidate against every other admitted candidate in both seat orders.
- Use sequential balanced evaluation to avoid unnecessary games while preserving useful uncertainty estimates.
- Produce a final ranking using gameplay strength, matchup robustness, reliability, and latency.
- Select the primary and backup baseline for the next contract.

A `PASS` requires at least **three runnable, complete, frozen deck–agent pairs**.

---

## 3. Context

Accepted foundations:

- `c001`: deterministic legal fallback agent.
- `c002`: episode capture and validation.
- `c003`: schema-v2 lineage, canonical deck identity, semantic replay, gzip capture, and experiment provenance.

Winning-oriented review of c003 found three defects that directly affect competitive interpretation:

1. Terminal errors are still read from the first environment step in at least one real code path instead of the final state.
2. Duplicated `legal_option_metadata` is not checked for equality with `observation.select.option`.
3. Semantic replay is hard-coded to the safe agent and does not verify the recorded agent version/source hashes before invoking current code.

These must be corrected narrowly in Phase 0.

No other capture-platform redesign is allowed.

---

## 4. Dependencies and inputs

Claude Code may use:

- The current Git repository.
- Accepted c001–c003 source code.
- Existing starter-kit and cabt runtime assets.
- Existing complete official/public deck–agent pairs available locally.
- Public official/community candidate sources only when network access is available and licensing permits local use.
- `contracts/c004_competitive_baseline_gauntlet/inputs/c003_competitive_review.md`
- `contracts/c004_competitive_baseline_gauntlet/references/gauntlet_protocol.md`
- `contracts/c004_competitive_baseline_gauntlet/references/results_protocol.md`

Prefer local, already available candidate pairs.

Do not invent or reconstruct a public policy from an incomplete description.

Every external candidate must have source attribution, immutable source reference when available, file hashes, and deck identity.

---

## 5. Definitions

### Complete deck–agent pair

A candidate is complete only when it has:

- An exact 60-card deck accepted by cabt.
- An executable policy intended for that deck or explicitly published with it.
- A stable candidate ID and version.
- Source provenance.
- Agent source hashes.
- Canonical deck ID and full card multiset.
- A deterministic/stochastic classification.
- A working adapter to the project’s common agent interface.
- No strategic modifications made by this contract.

### Compatibility adaptation

Allowed:

- Import-path fixes.
- File-path fixes.
- Interface wrappers.
- Dependency compatibility changes.
- Serialization adapters.
- Deterministic seed plumbing for a stochastic baseline when supported.
- Defensive exception capture around the candidate.

Not allowed:

- Changing action priorities.
- Adding heuristics.
- Correcting strategic mistakes.
- Changing the candidate deck.
- Replacing candidate fallback behavior.
- Adding search, model, or deck-specific logic.

Any compatibility adaptation must be documented and source-snapshotted.

### Frozen candidate

A candidate is frozen when its:

- Agent source hashes
- Configuration
- Deck ID
- Adapter source hash

are recorded before the official gauntlet.

The same hashes must be verified after the gauntlet.

---

## 6. Contract phases

## Phase 0 — Narrow c003 amendments

Implement only:

1. Final-state terminal error extraction.
2. Equality validation between duplicated legal-option metadata and `observation.select.option`.
3. A minimal replay-agent registry keyed by:
   - `agent_id`
   - `agent_version`
   - required source hashes

Replay must refuse or mark unavailable when the current implementation does not match recorded hashes.

Add regression tests.

Do not introduce a general plugin framework.

## Phase 1 — Candidate discovery and admission

Discover candidate pairs from:

1. Current safe baseline.
2. Official sample agents/decks.
3. Complete public candidate pairs already available locally.
4. Official/public sources retrievable with immutable attribution if network access exists.

Target **four** admitted candidates.

A `PASS` requires at least **three**.

Admit candidates only after:

- Cabt deck acceptance.
- Agent smoke execution.
- Source/deck lineage recording.
- Compatibility changes documented.
- Candidate freeze hashes created.

If more than four valid candidates exist, select at most four using this priority:

1. Official sample pairs.
2. Public pairs with reported competitive relevance.
3. Strategic diversity:
   - simple/linear
   - midrange
   - setup/combo
   - another materially distinct archetype
4. Reproducibility and completeness.

Do not choose four near-identical variants merely to fill slots.

## Phase 2 — Candidate smoke and reliability gate

For every candidate:

- Run at least 10 completed cabt games:
  - 5 as seat 0
  - 5 as seat 1
- Use at least two different opponents where possible.
- Capture schema-v2 lineage.
- Record:
  - invalid selections
  - agent exceptions
  - environment exceptions
  - timeouts
  - fallback invocations
  - P50/P95/P99/max decision latency
  - match completion

A candidate is admitted to the official gauntlet only if:

- Deck is accepted.
- All smoke games terminate.
- No invalid selection occurs.
- No attributable agent exception occurs.
- No attributable timeout occurs.
- Candidate source/deck hashes remain unchanged.

A failed candidate must be recorded as rejected, not silently repaired strategically.

## Phase 3 — Frozen balanced round-robin gauntlet

Every admitted candidate must play every other admitted candidate in both seat orders.

For each unordered pair `(A, B)`:

### Initial batch

Run:

- 20 games with A as seat 0 and B as seat 1.
- 20 games with B as seat 0 and A as seat 1.

Minimum: **40 games per unordered pair**.

### Sequential extension

After each balanced batch, compute the seat-balanced A win rate and a 95% confidence interval.

Continue in balanced increments of:

- 10 games per seat orientation
- 20 games total per pair

Stop when either:

1. The 95% confidence interval lies entirely above `0.55` or entirely below `0.45`; or
2. The pair reaches 100 games per seat orientation, 200 total.

Draws count as `0.5` for win-rate estimation.

Do not stop early due only to a point estimate.

Record the exact stopping reason for every pair.

### Errors

- Attributable agent invalid action, exception, or timeout counts as a loss for that agent and a reliability defect.
- Environment errors not attributable to either candidate must be recorded separately and rerun up to a documented retry limit.
- Never silently drop failed games.

### Seat balancing

Report separately:

- A win rate as seat 0.
- A win rate as seat 1.
- Seat-balanced win rate.
- Overall seat-0 win rate across the gauntlet.

Do not use the raw overall win rate alone.

---

## 7. Statistical analysis

Produce all of the following.

### Pairwise analysis

For every ordered and unordered matchup:

- Games
- Wins
- Losses
- Draws
- Seat orientation
- Seat-balanced win rate
- 95% Wilson or bootstrap interval
- Stopping reason
- Reliability defects
- Latency summaries

Document the interval method.

### Global ranking

Fit a Bradley–Terry or equivalent pairwise ranking model.

Requirements:

- Draw handling documented.
- Candidate strength point estimates.
- At least 2,000 bootstrap resamples or an analytically justified equivalent.
- 95% interval per candidate.
- Ranking stability/frequency across bootstrap samples.
- Raw matchup results remain available; the global model must not replace them.

### Worst-matchup analysis

For every candidate:

- Worst observed matchup.
- Point estimate.
- Conservative lower confidence bound.
- Seat-specific weakness.
- Reliability defects against that opponent.

### Reliability gate

A primary or backup candidate is ineligible if the official gauntlet contains:

- Any invalid action.
- Any attributable agent exception.
- Any attributable timeout.

If all candidates fail this gate, status must be `PARTIAL`, and the least unreliable candidate may be named only as a temporary engineering baseline, not a competitive primary.

---

## 8. Selection rule

The final selection must be deterministic and documented before inspecting final results.

Among reliability-eligible candidates:

### Primary baseline

Select by:

1. Highest Bradley–Terry strength point estimate.
2. If leading candidates’ 95% intervals substantially overlap, prefer the candidate with the higher conservative worst-matchup lower bound.
3. If still tied, prefer lower P99 latency.
4. If still tied, prefer the simpler and more reproducible candidate.

### Backup baseline

Select the highest-ranked remaining eligible candidate.

When two candidates are statistically similar, prefer the one that performs better against the primary candidate’s worst matchup and provides archetype/policy diversity.

### Rejections

Every non-selected candidate must receive one of:

```text
REJECTED_STRENGTH
REJECTED_RELIABILITY
REJECTED_LATENCY
NOT_ADMITTED_INCOMPLETE
NOT_ADMITTED_INCOMPATIBLE
NOT_ADMITTED_MISSING_ASSETS
```

Include evidence.

---

## 9. c005 hypothesis requirement

The contract must finish with one concrete policy-improvement hypothesis for the selected primary pair.

The hypothesis must be grounded in:

- Captured decisions.
- Repeated tactical failure patterns.
- Matchup weakness.
- Candidate source inspection.
- Fallback or decision-source behavior.

Bad:

```text
Improve the policy.
```

Good:

```text
The primary agent repeatedly attaches Energy to the active attacker when a
backup attacker must be prepared; implement a deck-specific attachment scorer
and test it against the unchanged c004 baseline.
```

Do not implement the hypothesis in c004.

---

## 10. Non-goals

Do not implement:

- Strategic improvements to any candidate.
- New deck invention.
- Card-count tuning.
- Deck mutations.
- MCTS, beam search, or tree search.
- RL, imitation learning, policy/value models.
- Opponent modeling.
- LLM policy labels.
- Meta-scraping infrastructure.
- Schema v3.
- General-purpose plugin architecture.
- Descriptive analysis of fallback-vs-random data unrelated to candidate selection.

Do not modify earlier contract results.

---

## 11. Mandatory acceptance criteria

### AC-01 — c003 competitive amendments

**Requirement**

The three Phase-0 defects are corrected with regression tests.

**Evidence**

```text
results/test_logs/c003_amendment_tests.txt
results/artifacts/c003_amendment_report.json
```

**Pass condition**

- Terminal errors are extracted from final state/errors.
- Legal-option metadata equality is checked.
- Replay verifies agent identity/version/source hashes before invocation.
- Existing c003 tests still pass.

---

### AC-02 — Candidate manifest and freeze

**Requirement**

At least three complete runnable deck–agent pairs are admitted and frozen.

**Evidence**

```text
results/artifacts/candidate_manifest.json
results/artifacts/candidate_admission.md
results/artifacts/candidate_freeze_hashes_before.json
results/artifacts/candidate_freeze_hashes_after.json
```

**Pass condition**

- At least three admitted candidates.
- Every admitted candidate has complete source, deck, agent, version, and hash lineage.
- Before/after hashes match.
- No strategic modification occurred after freeze.

---

### AC-03 — Candidate smoke gate

**Requirement**

Every admitted candidate passes 10 smoke games balanced across seats.

**Evidence**

```text
results/test_logs/candidate_smoke_tests.txt
results/artifacts/candidate_smoke_report.json
```

**Pass condition**

Every admitted candidate completes all required games with zero invalid actions, attributable exceptions, and timeouts.

---

### AC-04 — Complete balanced round robin

**Requirement**

Every admitted candidate plays every other candidate under the specified sequential balanced protocol.

**Evidence**

```text
results/artifacts/gauntlet_plan.json
results/artifacts/gauntlet_games.jsonl.gz
results/artifacts/pair_stopping_report.json
results/test_logs/gauntlet_execution.txt
```

**Pass condition**

- Every unordered pair has at least 40 games.
- Both seat orientations are balanced.
- Sequential stopping rules are followed.
- No matchup is silently omitted.
- Every game has schema-v2 lineage.

---

### AC-05 — Matchup and seat analysis

**Requirement**

Produce complete pairwise and seat-adjusted results with uncertainty.

**Evidence**

```text
results/artifacts/matchup_matrix.csv
results/artifacts/ordered_matchup_matrix.csv
results/artifacts/seat_effects.csv
results/artifacts/pairwise_intervals.json
```

**Pass condition**

Every candidate pair and seat orientation is represented, intervals are documented and reproducible, and draws/errors are handled as specified.

---

### AC-06 — Global ranking and robustness

**Requirement**

Produce bootstrap-supported global ranking and worst-matchup analysis.

**Evidence**

```text
results/artifacts/bradley_terry_ranking.json
results/artifacts/bootstrap_ranking.json
results/artifacts/worst_matchups.json
results/test_logs/statistical_analysis_tests.txt
```

**Pass condition**

- At least 2,000 bootstrap resamples or justified equivalent.
- Candidate point estimates and 95% intervals.
- Ranking stability frequencies.
- Worst-matchup conservative bounds.
- Analysis is reproducible from captured results.

---

### AC-07 — Reliability and latency

**Requirement**

Measure reliability and latency for every candidate.

**Evidence**

```text
results/artifacts/reliability_report.json
results/artifacts/latency_report.json
results/artifacts/fallback_report.json
```

**Pass condition**

Reports include invalid actions, agent errors, environment errors, timeouts, fallback counts, calls, and P50/P95/P99/max latency per candidate.

---

### AC-08 — Explicit competitive decision

**Requirement**

Select primary and backup baselines using the predefined rule and reject all other candidates explicitly.

**Evidence**

```text
results/artifacts/selected_baselines.md
results/artifacts/competitive_decision.json
```

**Pass condition**

The decision includes:

- Primary baseline
- Backup baseline
- Candidate rankings
- Evidence
- Weak matchups
- Reliability status
- Uncertainty
- Rejection codes
- Exact frozen deck and agent IDs

No ambiguous “more testing needed” conclusion is allowed unless mandatory evidence failed, in which case status must be `PARTIAL`.

---

### AC-09 — Actionable c005 hypothesis

**Requirement**

Produce one specific policy-improvement hypothesis for the primary baseline.

**Evidence**

```text
results/artifacts/c005_policy_hypothesis.md
results/artifacts/tactical_failure_examples.jsonl
```

**Pass condition**

- At least five concrete captured examples support the hypothesis, unless fewer than five occurrences exist and this is documented.
- The hypothesis targets one coherent decision problem.
- It specifies the unchanged baseline, proposed intervention, evaluation opponents, and keep/reject criterion.
- No implementation is performed.

---

### AC-10 — Git and source integrity

**Requirement**

All c004 implementation and candidate adapters are committed cleanly without modifying frozen strategies or earlier results.

**Evidence**

```text
results/GIT_REPORT.md
results/artifacts/c004.patch
results/artifacts/source_snapshot/
results/artifacts/CLEAN_CHECKOUT.md
results/test_logs/final_git_status.txt
```

**Pass condition**

- Required source changes committed.
- Candidate strategic code/decks unchanged after freeze.
- Earlier contract results untouched.
- Pre-existing user changes preserved.
- Initial/final HEAD and commits recorded.
- No unrelated changes committed.

---

## 12. Required deliverables

```text
contracts/c004_competitive_baseline_gauntlet/results/
├── SUMMARY.md
├── STATUS.json
├── FILES_CHANGED.md
├── COMMANDS_RUN.md
├── ACCEPTANCE_CHECKLIST.md
├── GIT_REPORT.md
├── test_logs/
│   ├── c003_amendment_tests.txt
│   ├── candidate_smoke_tests.txt
│   ├── gauntlet_execution.txt
│   ├── statistical_analysis_tests.txt
│   └── final_git_status.txt
├── artifacts/
│   ├── c003_amendment_report.json
│   ├── candidate_manifest.json
│   ├── candidate_admission.md
│   ├── candidate_freeze_hashes_before.json
│   ├── candidate_freeze_hashes_after.json
│   ├── candidate_smoke_report.json
│   ├── gauntlet_plan.json
│   ├── gauntlet_games.jsonl.gz
│   ├── pair_stopping_report.json
│   ├── matchup_matrix.csv
│   ├── ordered_matchup_matrix.csv
│   ├── seat_effects.csv
│   ├── pairwise_intervals.json
│   ├── bradley_terry_ranking.json
│   ├── bootstrap_ranking.json
│   ├── worst_matchups.json
│   ├── reliability_report.json
│   ├── latency_report.json
│   ├── fallback_report.json
│   ├── selected_baselines.md
│   ├── competitive_decision.json
│   ├── c005_policy_hypothesis.md
│   ├── tactical_failure_examples.jsonl
│   ├── c004.patch
│   ├── CLEAN_CHECKOUT.md
│   └── source_snapshot/
└── failures/
```

Additional useful artifacts are allowed.

All changed source files and admitted candidate adapters/manifests must be copied under:

```text
results/artifacts/source_snapshot/
```

preserving repository-relative paths.

---

## 13. Required reports

### `SUMMARY.md`

Include:

- Final status
- Admitted and rejected candidates
- Total smoke games
- Total gauntlet games
- Primary baseline
- Backup baseline
- Ranking and uncertainty
- Worst matchups
- Reliability defects
- Latency
- c003 amendment status
- c005 policy hypothesis
- Known limitations

### `STATUS.json`

```json
{
  "contract": "c004_competitive_baseline_gauntlet",
  "status": "PASS",
  "acceptance_criteria_total": 10,
  "acceptance_criteria_passed": 10,
  "acceptance_criteria_failed": 0,
  "initial_head": "...",
  "final_head": "...",
  "implementation_commits": ["..."],
  "admitted_candidates": ["..."],
  "primary_baseline": "...",
  "backup_baseline": "...",
  "smoke_games": 0,
  "gauntlet_games": 0,
  "blocking_issues": [],
  "known_limitations": []
}
```

Allowed status values:

```text
PASS
PARTIAL
BLOCKED
FAILED
```

---

## 14. Git requirements

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
contract/c004_competitive_baseline_gauntlet
```

Create it from the accepted c003 final HEAD.

### Commits

Use coherent commits beginning with:

```text
c004:
```

Recommended grouping:

```text
c004: fix competitive replay and terminal validation
c004: add frozen candidate registry and gauntlet runner
c004: add ranking analysis and baseline selection evidence
```

Do not:

- Push
- Force-push
- Rebase shared history
- Amend user commits
- Reset or clean destructively
- Commit strategic modifications to candidate policies/decks

### Final state

All required implementation changes must be committed.

Contract results may remain uncommitted if that matches the existing repository protocol; record this clearly.

---

## 15. Stop and status conditions

Mark `BLOCKED` if:

- Accepted c003 source is missing.
- Cabt runtime is unavailable.
- Overlapping user changes cannot be preserved.
- Fewer than two complete candidates can be executed.

Mark `PARTIAL` if:

- Fewer than three candidates are admitted.
- Any mandatory acceptance criterion fails.
- No reliability-eligible candidate exists.
- Round robin is incomplete.
- Statistical analysis cannot be reproduced.
- Primary/backup selection cannot be made under the predefined rule.
- Candidate strategy/deck changed after freeze.
- c003 amendments are incomplete.

Do not weaken criteria or modify this contract.

---

## 16. Final Claude Code response

Return:

```text
Contract:
Status:
Branch:
Initial HEAD:
Final HEAD:
Implementation commits:
c003 amendments:
Candidates discovered:
Candidates admitted:
Candidates rejected:
Smoke games:
Gauntlet games:
Primary baseline:
Backup baseline:
Primary worst matchup:
Reliability gate:
c005 hypothesis:
Results directory:
Blocking issues:
Known limitations:
```

Do not claim `PASS` unless all ten criteria pass.
