# B04 — V-trace numerical reference

The torch training path matches an independently written NumPy reference to 1e-10 on random trajectories; on-policy V-trace with γ=1 telescopes exactly to the return; and a dedicated test shows the targets CHANGE when the target policy differs from the behavior policy — a GAE-shaped computation would ignore importance ratios entirely and produce identical output.

Clipping bounds [0.001, 1.007] and γ=1.0 are the registered Hearthstone values. γ=1 makes the recursion non-contracting, so target magnitudes are logged from the first fixture to distinguish divergence from a bug.

**Status: PASS.**
