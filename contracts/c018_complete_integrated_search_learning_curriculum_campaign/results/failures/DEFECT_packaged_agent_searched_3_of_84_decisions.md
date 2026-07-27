# DEFECT — the packaged agent searched 3 of 84 decisions

**Severity: submission blocker (§8.2.6 — the uploaded package differs from the evaluated
source).** Found before any upload, by instrumenting the extracted archive rather than trusting
that clean extraction passing meant the agent worked.

## What happened

`c018_search.plan` gated its beam on a *cumulative* node budget:

```python
if stats["nodes"] >= cfg["max_nodes"] * max(1, stats["decisions"]) or ...:
    break
```

The allowance grew with `stats["decisions"]`, a counter the **caller** was expected to
increment. Every offline harness did (`c018_trajectories.py`, `c018_panel.py`), so the budget
grew to ~40 nodes per decision and was never binding — the scaled run used 14.2 nodes per
searched decision against an allowance of 40·d.

The generated `main.py` in the submission package did not increment it. Inside a real match
`stats["decisions"]` stayed 0, `max(1, 0)` pinned the allowance at 40 nodes **for the entire
game**, and after the first few decisions every candidate loop broke immediately, produced no
scored candidates, and returned the baseline action.

Measured on the extracted archive against the official iono agent:

| | decisions | searched | search_step ok | changed action |
|---|---|---|---|---|
| before | 84 | **3** | 40 | **0** |
| after | 75 | 67 | 957 | 21 |

## Why the existing checks missed it

Clean-extraction validation asked whether the package *imports and completes games*. It did —
because falling back to the baseline is a perfectly playable agent. Every safety property held.
The package was a well-behaved copy of the official agent with a search layer that had been
silently switched off, and nothing in the pipeline was asking "did it actually search?"

This is c017's global-node-budget starvation (249 of 266 searches aborted) in a new place. The
same defect recurred because the fix last time was to enlarge the budget, not to remove the
dependence on an external counter.

## Fix

A local `nodes_here` counter, incremented where nodes are actually expanded and compared against
`cfg["max_nodes"]` directly. A budget that lives in the function that spends it cannot be
starved by a caller that forgets a side effect. `main.py` still increments `decisions`, but only
for reporting.

## Blast radius

None for M01–M03. The cumulative rule was never binding in the harnesses, confirmed empirically
rather than argued: 14.57 nodes per searched decision after the fix versus 14.25 before, on the
same generator. See `artifacts/node_budget_defect.json`. The trajectory, distillation and
curriculum evidence was therefore not regenerated.

## Generalisable lesson

"The package runs" and "the package does what was evaluated" are different claims, and only the
first was being tested. Clean-extraction validation now has a companion check that reads the
search counters out of the extracted agent.
