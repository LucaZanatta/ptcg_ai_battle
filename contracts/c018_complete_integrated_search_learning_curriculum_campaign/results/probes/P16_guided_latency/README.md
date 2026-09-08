# P16 — Guided search latency

Adding a model forward to a beam search is where a working idea becomes an unshippable one, so
this was measured **before** the guided runs, not after.

| | p50 | p90 | max |
|---|---|---|---|
| unguided | 2.24 ms | 3.31 ms | 95.14 ms |
| guided | 5.38 ms | 7.62 ms | 108.99 ms |

Budget is 2500 ms per decision. Guidance costs roughly
3.1 ms at the median — two forwards per
decision (one to order the root, one batched over all candidate leaves), not one per node. A
per-node call would have sat in the innermost loop and spent the whole budget on inference.

Encode failures: 0 leaf rows, 0 orderings.

**Status: PASS.**
