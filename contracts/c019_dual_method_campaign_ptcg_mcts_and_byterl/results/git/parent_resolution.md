# c019 parent resolution (probe P00)

## Candidates

| commit | subject | status |
|---|---|---|
| `4cbae35888b21cbfccb6ebf4f5f5bfc5e05bd757` | c018: final reports state the wrapper mechanism and derive the next action from it | the contract's *expected* parent (`MANIFEST.expected_parent`, `inputs/PROJECT_GROUND_TRUTH.md`) |
| `2197214d1d9dcb93afc00ad5bfd650b2531ea6b3` | c018: fix two acceptance-checklist bugs and make M05 record the non-submission decision | **SELECTED** — actual latest c018 result-generation commit, one ahead of the expected hash |

## Selection: `2197214`

`CONTRACT.md` §2 requires resolving "the actual latest c018 code/result-generation parent", and
`inputs/PROJECT_GROUND_TRUTH.md` states plainly: *"Do not blindly reset to this hash when newer
c018 result-generation commits exist."* One does.

`2197214` is a strict descendant of `4cbae35` and touches exactly two files, both of which are
c018 **result-generation** code:

```text
tools/c018_reports.py
tools/c018_tree.py
```

It contains three corrections that the c019 evidence tree depends on:

1. `ACCEPTANCE_CHECKLIST.md` reported AC-02 as NOT MET while its own evidence line showed it
   passing — the test was `(x or 1) == 0`, and a passing `0` is falsy, so it became `1`. The zero
   hidden-information violations the criterion *requires* was the one value the test could not
   accept.
2. AC-03 failed only because one defect (D0) is deliberately left open as a design constraint;
   the criterion asks for one consolidated repair pass, not for every defect to be closed.
3. `M05_submitted` now records the non-submission **decision** with per-package promotion-gate
   deltas, which `RESULTS_SCHEMA` §35.4 requires the submitted package to resolve to exactly.

Selecting `4cbae35` would inherit a c018 checklist that misreports its own acceptance criteria.

## Verification

```text
git merge-base --is-ancestor 4cbae35 2197214   -> true (2197214 descends from the expected hash)
c018 branch head at c019 start                 -> 2197214
c019 branch created from                       -> 2197214
```

No reset, rebase, force-push, or modification of c005–c018 artifacts was performed. The c018
branch remains at `2197214`; c019 work proceeds on a new branch.

## Initial state

```text
branch  contract/c019_dual_method_campaign_ptcg_mcts_and_byterl
head    2197214d1d9dcb93afc00ad5bfd650b2531ea6b3
dirty   untracked contract result trees and pre-existing untracked repo files only (see status.txt)
```
