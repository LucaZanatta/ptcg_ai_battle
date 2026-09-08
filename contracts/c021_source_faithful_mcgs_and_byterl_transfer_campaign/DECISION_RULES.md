# Decision and Submission Rules

## 1. MCGS statuses

`SOURCE_FIDELITY=PASS` for MCGS requires official archive retrieval, source inventory, source/function map, formula fixtures and all mandatory conformance probes.

`MCGS_COMPETITIVE=PASS` requires a legal package that:

- is not tainted;
- passes package identity/latency rules;
- beats the frozen official baseline or current trustworthy champion under a preregistered sufficiently powered panel, or demonstrates a statistically credible complementary profile with an explicit submission rationale;
- does not achieve its result through illegal opponent information.

A technically faithful but weak MCGS is `MCGS_COMPETITIVE=FAIL`, not automatically an implementation failure.

## 2. ByteRL statuses

`BYTERL_METHOD=PASS` requires:

- end-to-end deck construction plus battle;
- recurrent actor–learner execution;
- exact autoregressive joint actions;
- exact numerical objective probes;
- working OSFP and immutable history;
- BR0→BR3 delta conformance;
- at least one genuine training run with changing weights and external evaluations.

`BYTERL_SCALE=COMPUTE_LIMITED` is allowed only when:

- method fidelity passed;
- the achieved scale is materially below the paper reference;
- throughput and scale evidence are complete;
- learning trajectory is reported without claiming convergence.

Do not call ByteRL a method failure only because it cannot reproduce the paper's distributed scale.

## 3. Component-transfer success

A ByteRL component is retained only when a controlled transfer test demonstrates one of:

- credible improvement in MCGS field score;
- credible matchup improvement without unacceptable broad-field regression;
- significant improvement in held-out calibration/ranking tied to downstream decisions;
- useful policy diversity that improves a registered ensemble/search decision.

Internal ByteRL-vs-history improvement alone is insufficient.

## 4. Submission gates

Submit immediately only after a candidate passes its registered gate.

Eligible candidate classes:

```text
MCGS_2019_PTCG_LEGAL_CORRECTED
faithful MCGS reference when fully legal/deployable
ByteRL standalone only if externally credible
one-component ByteRL→MCGS transfer candidate
```

Never submit:

- oracle-information candidates;
- source-mismatched packages;
- tainted evaluations;
- ByteRL checkpoints selected only on self-play;
- an uncontrolled hybrid;
- candidates clearly dominated by the current champion.

## 5. Final interpretation

The final report must explicitly state:

- whether MCGS was source-faithful;
- whether executed search actions helped or hurt;
- whether any MCGS defect was algorithmic, adaptation-related or throughput-related;
- whether ByteRL was method-correct;
- exact achieved fraction/scale relative to published references where available;
- which ByteRL stages improved what;
- which components transferred;
- which components were rejected and why;
- strongest trustworthy local candidate;
- submission IDs/scores or `PENDING`;
- exactly one next action.

## 6. Overall status

`OVERALL=PASS` requires both methods implemented/executed/analyzed, canonical evidence, and at least one credible competitive or transfer result.

`OVERALL=PARTIAL` is permitted when both methods are faithfully executed and analyzed but no candidate clears the competitive gate.

`OVERALL=FAIL` is mandatory when either method is omitted, materially simplified, not executed, or falsely reported.
