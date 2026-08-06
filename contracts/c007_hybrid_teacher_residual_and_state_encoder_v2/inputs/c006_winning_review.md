# c006 Winning-Oriented Findings

Accepted:

- c006 was an honest negative result.
- The students were reliable and reproducible.
- Neither student was strong enough to submit.
- Ordinary RL from those checkpoints is not justified.
- The frozen teacher remains the runtime baseline.

Critical diagnosis:

```text
dynamic in-play state omitted
+ exact hand/bench/discard structure collapsed
+ weak card semantics
+ independent option scoring
+ incomplete previous-action identity
+ limited dataset
+ behavioral-cloning distribution shift
```

`MEMORY_NOT_JUSTIFIED` is not treated as conclusive because the recurrent model did not receive the actual previous action identity and shared the same lossy state encoder.

Required pivot:

```text
frozen teacher
+ state encoder v2
+ learned advisory model
+ narrow evidence-backed residual overrides
```
