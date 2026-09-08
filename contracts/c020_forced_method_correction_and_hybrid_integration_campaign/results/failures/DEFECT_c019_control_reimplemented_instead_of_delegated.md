# DEFECT — the c019 ByteRL control was re-implemented instead of delegated

**Found:** during the Phase 2 integrated smoke, 10-candidate panel.
**Symptom:** `C019_BYTERL_CONTROL` scored 0 of 4 games; all four were incomplete with no
exception recorded, because the agent returned an empty action payload on encode failure and the
environment terminated the episode rather than raising.

## What was wrong

`tools/c020_panel.py` built the c019 ByteRL control by re-implementing its inference loop inside
c020 — re-deriving the encode call, the mask handling, the top-k selection and the payload
construction. Two of those differed subtly from c019's own agent, and the fallback path returned
`[]`.

The deeper error is conceptual rather than mechanical. **A control is only a control if it is the
code being controlled for.** A paraphrase compares c020 against my reconstruction of c019, and any
divergence — in either direction — is then attributed to the method rather than to the paraphrase.
That is the same class of mistake as `CONTRACT §12`'s prohibition on relabelling: the artifact must
be what it claims to be.

Note the direction of the risk. A broken control makes c020 look *better*, not worse, so this is
exactly the kind of defect that does not announce itself in a results table.

## Fix

Delegate to c019's own builder:

```python
from tools.c019_panel import build_candidate as build19
play, handle = build19("ptcg_byterl_v0", deck, seed,
                       {"byterl_checkpoint": cfg["c019_byterl_checkpoint"]})
```

`tools/c019_panel.py` is imported unmodified, so the control executes the c019 code path that
produced c019's own reported numbers. After the fix all three controls complete every game
(0 incomplete over 12 games).

## Why this is not the consolidated repair pass

`CONTRACT §4` Phase 3 allows exactly one consolidated repair pass, after the complete smoke, for
defects in the c020 methods. This is neither: it is a defect in the c020 *evaluation harness*
discovered while assembling the smoke, and leaving it in place would have made the smoke
incapable of producing a control comparison at all — `CONTRACT §8`'s "evaluator/candidate identity
corruption" blocker. It is recorded here so the repair-pass budget is visibly not spent on it.
