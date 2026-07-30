# Training and Evaluation Protocol

## 1. Matched-budget rule

Recover the exact c021 fixed-deck B2 training exposure from raw artifacts:

- games;
- environment decisions/samples;
- learner updates;
- optimizer examples after sample reuse.

The controlling matched budget is environment decisions/samples, not games. Record the c021 value in:

```text
results/byterl/budget/c021_matched_budget.json
```

If exact decisions cannot be recovered, use 76,800 games as the fallback and report the achieved decision count.

## 2. ByteRL stage allocation

### Conformance runs

Run every stage BR0→BR3 long enough to verify:

- complete execution;
- intended stage delta;
- stable losses and recurrence;
- legal actions and legal decks;
- external evaluation pipeline;
- OSFP promotion mechanics where applicable.

### Controlled rung attribution

Use an equal, preregistered smaller sample budget for adjacent-stage comparisons. Do not give one rung more samples and attribute the difference to the algorithmic change.

### Decisive long runs

Train from scratch to at least the c021 matched sample budget:

```text
A. BR3_FIXED_DECK
B. BR3_END_TO_END
```

If resources do not permit both simultaneously, train `BR3_FIXED_DECK` first because c021 demonstrated battle-learning signal, then `BR3_END_TO_END`. Both implementations and at least a nontrivial end-to-end run remain mandatory.

Do not warm-start from c021 weights.

## 3. Evaluation schedule

At fixed sample milestones, freeze checkpoints and evaluate against the same registered external field using paired seeds where possible.

Track:

- external field win rate and confidence interval;
- per-matchup results;
- policy-prior quality on a frozen decision set;
- MCGS transfer effect on a frozen paired decision/game set;
- held-out value MSE, correlation, calibration, and constant baseline;
- entropy and action diversity;
- recurrent-state contribution by hidden-state ablation;
- deck legality, diversity, and external strength;
- OSFP population exploitability/generalization.

Internal self-play or historical-policy win rate may not be the sole continuation criterion.

## 4. Plateau rule

The decisive BR3 run must first reach the matched c021 sample budget unless a hard failure occurs.

After the matched budget, continue only in fixed extension blocks equal to 25% of that matched budget.

Stop for plateau when three consecutive external evaluation milestones collectively show all of:

```text
1. external field improvement < 2 percentage points;
2. no statistically credible improvement in policy-prior/MCGS transfer metrics;
3. no improvement in held-out value or recurrence metrics;
4. confidence intervals substantially overlap and trend slope is non-positive.
```

Also stop immediately for:

- repeated numerical instability;
- entropy collapse with external regression;
- recurrent replay mismatch;
- queue/policy-lag failure that cannot be repaired without changing the method;
- illegal action/deck generation;
- sustained external regression across three checkpoints.

Rising training return alone does not override the plateau rule.

## 5. MCGS evaluation

Use a frozen opponent panel and paired seeds.

Minimum causal evidence:

- K=1/2/4/8 fixed-total-simulation comparison;
- K=1/2/4/8 fixed-simulations-per-world comparison;
- at least 200 paired games for shortlisted K values before claiming a six-point effect;
- calibration curves and Brier/log-loss where predicted probabilities exist;
- action disagreement and stability on at least 500 frozen decisions;
- unrestricted source-style timing evaluation;
- separate deploy-clock evaluation.

## 6. Final panel

Register before running:

- candidates;
- controls;
- decks/models/packages;
- opponent panel;
- seeds;
- game count;
- tie/incomplete handling;
- confidence method;
- submission gate.

No candidate enters the final panel after results are visible.
