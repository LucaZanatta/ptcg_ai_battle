# B06 — Actor/learner recurrent replay

The learner initializes from the recorded `h0`/`c0` and asserts the actor's per-timestep context fingerprints before computing any importance ratio; a mismatch RAISES and the batch is dropped to `failures/recurrent_mismatches/` rather than being trained on.

c019 reset the state to zero at every mid-game unroll boundary (audit #10), so every ratio on a mid-game unroll compared two different functions (audit #11).
