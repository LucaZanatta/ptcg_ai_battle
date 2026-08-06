# Hybrid Evaluation Protocol

The frozen teacher is the default runtime policy. Learning may change actions only in pre-approved semantic contexts under evidence-backed gates.

Controls:

```text
T  frozen teacher
H0 parity wrapper
H1 monitor only
H2 gated residual
```

Submission requires reliability, teacher non-inferiority with lower bound at least 0.47, at least one reproducible improvement, no major regression, and validated packaging.

When the local gate passes, submit automatically and retrieve submission ref, status history, score snapshot, same-run teacher snapshot, and promotion decision.
