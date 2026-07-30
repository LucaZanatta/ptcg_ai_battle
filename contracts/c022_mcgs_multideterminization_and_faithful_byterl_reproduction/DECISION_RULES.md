# Decision Rules

## 1. Status vocabulary

Use only:

```text
PASS
PARTIAL
FAIL
BLOCKED
COMPUTE_LIMITED
INCONCLUSIVE
NOT_RUN
```

## 2. MCGS statuses

### `MCGS_HIDDEN_INFO=PASS`

Requires:

- repeated legal hidden worlds are demonstrated;
- aggregation/re-determinization behavior is implemented and traced;
- c021 overconfidence is materially reduced;
- K>1 improves calibration and does not regress external field performance beyond noise.

### `MCGS_COMPETITIVE=PASS`

Requires a preregistered candidate that either:

- credibly beats the strongest frozen local champion on the broad panel; or
- has a strong complementary matchup profile with no unacceptable broad-field regression and a clear submission rationale.

A small noisy improvement over c021 MCGS is not a competitive pass.

## 3. ByteRL statuses

### `BYTERL_REFERENCE_FIDELITY=PASS`

Requires:

- LSTM-256 recurrence;
- exact complete-action autoregression;
- actor versions and stored recurrent starts;
- bounded blocking FIFO and measured production/consumption;
- exact numerical V-trace/UPGO/b3 fixtures;
- published stage-delta tests;
- immutable OSFP history and correct period accounting;
- end-to-end construction path implemented.

### `BYTERL_FIXED_DECK=PASS`

Requires a statistically credible improvement over random initialization/floor and a reproducible upward external trajectory. It does not imply competitive strength.

### `BYTERL_E2E=PASS`

Requires legal diverse deck construction and external improvement above random/fixed weak baselines. Merely generating legal decks is partial.

### `BYTERL_SCALE=COMPUTE_LIMITED`

Expected when method fidelity passes but paper-scale samples/periods are not approached.

## 4. Transfer status

`TRANSFER=PASS` requires one isolated ByteRL component to improve corrected MCGS beyond paired run-to-run noise under identical simulations and hidden worlds.

A positive point estimate smaller than the measured noise floor is `INCONCLUSIVE`, not pass or fail.

## 5. Submission

Submit only when:

- exact candidate identity is frozen;
- package validation passes;
- credible gate passes;
- no source/report mismatch exists;
- the submission is strategically justified against the current champion.

No automatic submission is required when no candidate qualifies.

## 6. Final overall interpretation

Possible honest outcomes include:

```text
MCGS fixed and competitive; ByteRL faithful but compute-limited.
MCGS fixed but weak; ByteRL yields transferable priors.
MCGS still blocked by API; ByteRL faithful and analytically useful.
Both methods faithful but no competitive candidate.
```

Do not compress these into a misleading single PASS.
