# Fidelity Rules

## 1. Authority order

### MCGS

```text
official 2019 source archive
> source runtime behavior
> Choe–Kim paper equations/pseudocode
> official competition metadata
> documented inference
```

### ByteRL

```text
verified author code/config if discovered
> LOCM ByteRL paper
> Hearthstone ByteRL paper
> primary IMPALA/V-trace reference where explicitly inherited
> official COG material
> documented inference
```

c019–c021 code is infrastructure or negative evidence, never the algorithmic authority.

## 2. Reference/adaptation labels

Every method change must be labelled one of:

```text
MECHANICAL_ADAPTER
SEMANTIC_GAME_ADAPTER
LEGAL_INFORMATION_ADAPTER
DEPLOYMENT_ADAPTER
ALGORITHMIC_ADAPTATION
```

Only the first two may exist in a pure reference branch. Legal-information and deployment changes require separately named branches. Algorithmic adaptations require isolated ablations.

## 3. MCGS hidden-information fidelity

First determine precisely when and how the official source:

- restores private information;
- samples opponent hand/deck information;
- samples random outcomes;
- re-determinizes during simulations;
- shares graph nodes across observer information sets.

The closest implementable legal PTCG equivalent must be used.

Priority order:

1. fresh legal hidden-world sample per simulation inside one graph, if the API supports it without leakage;
2. otherwise independent search sessions with fresh legal hidden worlds and source-equivalent root-statistic aggregation;
3. if neither is possible, stop and report `MCGS_HIDDEN_INFO=BLOCKED`; do not conceal the limitation with a heuristic value.

The K-session ensemble is an approximation to the source behavior and must be labelled `LEGAL_INFORMATION_ADAPTER`, not full source identity.

## 4. ByteRL fidelity

The published stage meanings are mandatory:

```text
B0   end-to-end baseline ByteRL system
B1   B0 with gamma changed to 1.0
B1.5 B1 with published random initial deck-construction selections
B2   B1.5 with bounded blocking FIFO and balanced actor production/learner consumption
B3   B2 with two-sided clipped V-trace and PPO-style clipped policy objective
```

OSFP, UPGO, recurrence, action masking, autoregression, and end-to-end deck construction are foundational ByteRL components; they are not redefined as separate later rungs merely for convenience.

Minimum disclosed Hearthstone settings to preserve unless a higher-authority artifact contradicts them:

```text
LSTM hidden size = 256
gamma B1+ = 1.0
learning rate = 7e-5
sample reuse = 2
entropy coefficient = 0.01
value / PPO / UPGO weights = 1 / 1 / 1
importance-ratio bounds = [0.001, 1.007]
PPO-style clip epsilon = 0.2
OSFP self-play probability = 0.6
promotion threshold = 0.55
maximum periods without promotion = 6
```

Unspecified details belong in `UNRESOLVED_REFERENCE_CHOICES.md`, with alternatives and sensitivity tests. Never silently inherit c021 values.

## 5. Compute-limited truthfulness

A correct method at small scale may receive:

```text
METHOD_FIDELITY=PASS
SCALE=COMPUTE_LIMITED
COMPETITIVE=INCONCLUSIVE or FAIL_BY_OBSERVED_GATE
```

Do not convert undertraining into method failure. Do not convert a rising internal curve into competitive success.

## 6. Source integrity

Final source must come from one exact final Git commit:

- `git archive` from final HEAD;
- independent plain inspection export from the same HEAD;
- byte-level cross-checks;
- package-to-source-to-evaluated-candidate identity proof;
- final reports generated after raw final data and validated against it.
