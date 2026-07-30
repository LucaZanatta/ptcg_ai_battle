# c022 — MCGS Hidden-Information Repair and Faithful ByteRL Reproduction

## 0. Executive mandate

c022 must complete both of these tasks:

```text
A. Fix the dominant c021 MCGS failure by implementing the closest legal equivalent of the
   original source's repeated hidden-state re-determinization, then evaluate MCGS as a real
   competitive agent.

B. Replace the c021 custom feed-forward learner with the actual published recurrent ByteRL
   LOCM→Hearthstone B0→B3 system, then train and analyze it at a matched c021 data budget
   unless a preregistered plateau or hard failure occurs.
```

Strategic roles:

```text
MCGS   → primary winning/submission branch
ByteRL → mandatory faithful implementation, method analysis, and reusable-component branch
```

Both must be implemented, executed, and analyzed. ByteRL being compute-limited does not permit a simplified algorithm. MCGS being the competitive branch does not permit skipping ByteRL.

## 1. Starting state and immutable parent

Expected c021 final result-generation commit:

```text
cdbd4438496c905eaf38ee257abfe0c822c588f4
```

Expected branch:

```text
contract/c021_source_faithful_mcgs_and_byterl_transfer_campaign
```

Before editing, record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --all --decorate -100 --oneline
```

Resolve the actual latest legitimate c021 descendant. If it differs, document why in:

```text
results/git/parent_resolution.md
```

Create branch:

```text
contract/c022_mcgs_multideterminization_and_faithful_byterl_reproduction
```

Commit messages begin with `c022:`. Preserve c005–c021 code, packages, checkpoints, evaluations, and unrelated user work immutably.

## 2. Frozen controls

Freeze exact hashes and identities for:

```text
BASELINE_OFFICIAL_MEGA_LUCARIO
CHAMPION_C005_DRAGAPULT
C020_H1_PRIOR_HYBRID_CONTROL
C021_MCGS_K1_CONTROL
C021_FIXED_DECK_B2_FINAL
C021_FIXED_DECK_B2_SELECTED_IT0160
C021_RANDOM_FLOOR
```

The c021 fixed-deck B2 final checkpoint is a control and transfer comparator only. Do not continue its training and do not initialize the faithful recurrent ByteRL model from it.

## 3. Correct interpretation of c021

The following findings are starting facts to verify from raw artifacts, not optional narrative:

1. c021 MCGS reused one hidden-world determinization across all rollouts for a decision and showed severe overconfidence: predicted root wins near 96% while actual outcomes were poor.
2. c021 MCGS core formulas were materially ported, but the full hidden-information system was not source-faithful.
3. c021 fixed-deck feed-forward V-trace+UPGO learning improved to roughly 24–26% externally after about 76,800 games, so local policy learning is real but weak.
4. c021 did not reproduce the published ByteRL ladder: it lacked LSTM recurrence, the published b2 blocking FIFO actor–learner balance, and the published b3 two-sided V-trace/PPO-style objective.
5. c021 OSFP end-to-end evidence was invalid or insufficient.
6. c021 transfer gains were below run-to-run noise and therefore inconclusive, not a proven failure.

Create `results/references/c021_audit_reconciliation.md` that resolves every number directly from c021 raw data.

## 4. Hardware policy

Use the user's Ryzen 9 7900X, 64 GiB RAM, and RTX 5070 12 GB for scheduling and throughput measurement only.

Hardware may reduce:

- MCGS simulations completed;
- MCGS worker count;
- ByteRL actor count;
- ByteRL wall-clock duration;
- learning periods reached;
- total samples achieved;
- microbatch size when exact gradient accumulation preserves the effective update.

Hardware may not alter:

- MCGS graph/search formulas;
- hidden-world sampling semantics;
- ByteRL recurrent architecture;
- actor–learner/FIFO semantics;
- trajectory recurrence and burn-in semantics;
- published objectives;
- action autoregression;
- OSFP population mechanics.

## 5. Time policy

Do not invent an open-ended overnight run.

Mandatory order:

1. conformance and throughput;
2. MCGS hidden-information correction and causal ablation;
3. faithful ByteRL implementation and numerical validation;
4. matched-budget ByteRL training;
5. optional continued ByteRL training only under the plateau rules;
6. transfer tests only after both parent methods pass their method-fidelity gates;
7. final panel, package, source capture, and report consistency.

MCGS gets exclusive CPU during decisive scaling and final panels. ByteRL may run concurrently only when CPU contention is measured and shown not to taint timing/evaluation.

## 6. Required deliverables

### MCGS

- exact audit of original source hidden-information/re-determinization behavior;
- legal PTCG mechanism for fresh hidden worlds;
- K=1/2/4/8 multi-determinization experiments;
- fixed-total-simulation and fixed-simulations-per-world protocols;
- predicted-versus-real outcome calibration;
- unrestricted source-style timing arm;
- Kaggle deployment arm separated from the unrestricted reference arm;
- broad paired field evaluation and candidate package if gates pass.

### ByteRL

- actual published B0→B1→B1.5→B2→B3 stage ledger;
- LSTM-256 recurrent policy/value system;
- complete masked autoregressive PTCG action probability;
- asynchronous versioned actors;
- bounded blocking FIFO queue and production/consumption control;
- correct recurrent unroll start/burn-in/replay;
- exact V-trace, UPGO, and b3 PPO-style clipped objective;
- correct OSFP periods and immutable historical policies;
- fixed-deck and end-to-end deck-construction arms;
- matched c021 sample budget and plateau-governed continuation;
- external, transfer-prior, value, recurrence, decoder, population, and deck-construction analysis.

## 7. Prohibited scope

Do not:

- add a third algorithm;
- rebuild the c021 feed-forward learner and call it ByteRL;
- use ordinary PPO in place of published b3;
- use a replay ring in place of the blocking FIFO;
- replace recurrence with independent transitions;
- use one root determinization and call the MCGS issue fixed;
- add multiple ByteRL components to MCGS simultaneously;
- tune against final-panel outcomes after unblinding;
- submit a candidate that fails the registered credible gate;
- generate final summaries before final raw evidence exists.
