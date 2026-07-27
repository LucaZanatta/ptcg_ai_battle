# B05 — UPGO numerical reference

UPGO returns match a hand-calculated recursion, the torch path matches the NumPy reference, the loss produces a nonzero gradient, and a test asserts the UPGO advantage DIFFERS from the V-trace advantage.

That last check is the one that matters: METHOD_FIDELITY forbids setting UPGO to zero or aliasing it to the V-trace loss, and both would be invisible in a training curve.

**Status: PASS.**
