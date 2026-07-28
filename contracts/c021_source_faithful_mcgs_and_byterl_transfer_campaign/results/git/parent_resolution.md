# Parent resolution

## Expected vs actual

`CONTRACT §1` names the expected c020 final result-generation commit:

```
267ca81399d6ea3fc85d155f57ada92b119edf77
```

The actual tip of `contract/c020_forced_method_correction_and_hybrid_integration_campaign` is
**20 commits later**:

```
275f4308f052bdcb4361d9ec5e555d0c3e956734
c021-prep / c020: final panel, gates, and close-out
```

## Resolution: parent is 275f430

`267ca81` is "c020: materialize the full probe matrix from real evidence" — real work, but it
predates every c020 result this contract depends on. The twenty commits after it include:

1. the **isolated final panel** (11 candidates, 2,300 games, 0 incomplete) that produces the
   `C020_CORRECTED_MCTS`, `C020_CORRECTED_BYTERL` and `C020_H1` control numbers `CONTRACT §2`
   requires this campaign to freeze;
2. the **ByteRL retrain** whose final checkpoint is the `C020_CORRECTED_BYTERL_CONTROL` artifact;
3. four defect fixes without which the c020 numbers are not the ones to compare against —
   inert option-to-object references, an inert end-turn veto, an illegal override payload, and
   panel results that depended on machine load.

Freezing controls at `267ca81` would freeze pre-final-panel numbers and, worse, would freeze them
from code that c020 itself later found defective. `CONTRACT §1` asks for "the actual latest
legitimate c020 descendant", and `§2` forbids controls being "silently regenerated from different
code" — both point at the tip.

Recorded here so the divergence from the stated expectation is visible rather than assumed.

## State at branch time

```
git status --short (tracked)   0 modified
git branch --show-current      contract/c020_forced_method_correction_and_hybrid_integration_campaign
git rev-parse HEAD             275f4308f052bdcb4361d9ec5e555d0c3e956734
```

Clean tree; no uncommitted c020 work carried into c021 implicitly.

## Immutability commitment

c021 writes only `cg/c021_*.py`, `starter_kit/c021_*.py`, `tools/c021_*.py`,
`tests/test_c021_*.py`, `external_refs/c021_mcgs/`, and its own results tree. No c005–c020 file,
package, checkpoint or evidence artifact is modified, and no history is rewritten.
