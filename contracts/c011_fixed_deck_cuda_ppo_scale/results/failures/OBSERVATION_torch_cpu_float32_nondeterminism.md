# Observation: multi-threaded torch CPU float32 is not run-to-run reproducible

## What was seen

The first trainer-state round-trip run reported a 7.6e-06 maximum weight difference between
an uninterrupted two-update control and a save/restore/resume sequence, even though the
resumed update's diagnostics matched the control to ~1e-08.

## Diagnosis, not assumption

Rather than attribute it to the restore, two **identical** runs were compared — same weights,
same frozen batch, same minibatch permutation, same everything, no save/restore involved:

```text
torch threads: 12
two IDENTICAL runs, max weight diff: 2.6300549507141113e-06
=> run-to-run determinism: NOT exact
```

So the divergence was ordinary floating-point nondeterminism in multi-threaded CPU float32
reductions, whose accumulation order is not fixed. It was not a trainer-state defect.

## Response

§9.2 requires parity validation in **deterministic** FP32, so `enable_determinism()` was
added and is called by every parity harness:

```python
torch.set_num_threads(1)
torch.use_deterministic_algorithms(True, warn_only=True)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
CUBLAS_WORKSPACE_CONFIG=:4096:8
```

With determinism enforced the round trip is exact:

```text
roundtrip_weight_diff              0.0
roundtrip_adamw_diff               0.0
control_vs_resumed_weight_diff     0.0
policy/value/entropy/KL/clip errors 0.0
```

The round-trip check was also corrected while doing this. It originally compared the
*control* model against the *resumed* model, which conflates round-trip fidelity with
run-to-run determinism. It now measures the actual round trip — state immediately before
save versus immediately after restore, for both weights and AdamW moments — and keeps the
control comparison separately, which is what §10.6 requires.

## Scope

Determinism is pinned for parity and round-trip evidence only. Scale training deliberately
uses all available threads: it does not require bit-reproducibility, and pinning one thread
there would cost throughput for no evidential benefit. Training reproducibility is instead
established the way every earlier contract established it — full trainer state, recorded
seeds, and raw per-game records — with the engine itself being `std::random_device`-seeded
and therefore never bit-reproducible regardless of backend.
