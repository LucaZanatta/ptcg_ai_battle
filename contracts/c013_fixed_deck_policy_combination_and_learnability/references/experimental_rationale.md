# Experimental Rationale

## Why combination comes before more scale

c012 found that policy averaging produced a stronger deployable policy while a large
continuation budget did not produce a broad promotion. The immediate question is
whether complementary knowledge already present in saved branches can be combined
more effectively and then made learnable.

## Why online ensembles must be tested

A nonlinear network evaluated at averaged weights is not equivalent to averaging
component logits or probabilities. These methods can produce different decisions
and different strategic performance.

## Why Q0/Q1/Q2

Q0 recreates direct soup continuation.

Q1 tests whether an averaged or miscalibrated value head is poisoning PPO learning.

Q2 tests whether preserving component lineages and recombining after continuation is
better than optimizing the soup directly.

## Why only a curriculum smoke test

c012 did not execute its adaptive curriculum. Before another large run, the in-run
evaluation, hash refresh, stage transition, resume, and early-stop machinery must
work under a bounded test.

## Why only a Claude semantic preflight

The prior Claude test lacked human-readable card/action semantics. c013 tests whether
Claude can understand the decision representation. It does not test strategic
superiority and cannot train the policy.
