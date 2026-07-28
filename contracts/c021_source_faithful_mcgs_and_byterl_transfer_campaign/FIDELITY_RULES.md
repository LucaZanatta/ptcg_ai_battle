# Non-Negotiable Fidelity Rules

## 1. Closest-possible definition

A reference branch maximizes fidelity to:

- original source behavior where source exists;
- original equations, architecture, control flow and disclosed hyperparameters where source does not exist;
- only unavoidable PTCG mechanical/semantic adapters.

## 2. Required adaptation labels

Every difference from the reference must be labelled:

```text
MECHANICAL_ADAPTER
SEMANTIC_ADAPTER
LEGAL_INFORMATION_CHANGE
DEPLOYMENT_CHANGE
ALGORITHMIC_ADAPTATION
UNRESOLVED_REFERENCE_CHOICE
```

Only `MECHANICAL_ADAPTER` and `SEMANTIC_ADAPTER` may exist in a reference branch.

## 3. MCGS forbidden substitutions

The reference branch may not substitute:

- PUCT for modified UCD;
- root-only enumeration for a graph search;
- separate determinization trees for the shared DAG/chance-node design;
- node statistics when official source uses edge/descendant statistics;
- traversed-path-only backup when source recursively updates incoming graph paths;
- a handcrafted or neural leaf evaluator for source rollouts;
- Mega Lucario baseline continuation unless it exactly implements an original obliged action/filter role and is explicitly justified;
- c020 conservative override gating;
- a single-turn horizon unless the source does so;
- removal of original category filters or obliged actions;
- silent correction of known source defects.

## 4. ByteRL forbidden substitutions

The reference ladder may not substitute:

- fixed-deck battle-only training for end-to-end deck construction plus battle;
- ordinary PPO for the published objective;
- ordinary self-play for OSFP;
- a replay ring for blocking FIFO actor–learner flow;
- transition-level replay for recurrent unrolls;
- zero-state learner replay for stored actor recurrent state;
- first-selected-item probability for complete autoregressive joint probability;
- active/bench pooling that destroys slot identity;
- non-versioned behavior policies;
- mutable historical checkpoints;
- cross-period payoff accumulation when the algorithm resets period-local evidence;
- c019/c020 weights as initialization;
- smaller/different network architecture merely to fit hardware.

## 5. Preserve defects in reference branches

When the official MCGS source contains behavior that appears theoretically flawed, reproduce and test it in the reference branch. A corrected implementation must be a separately named branch.

## 6. Unspecified ByteRL details

No hidden choice is permitted.

For every undisclosed detail, create an entry in:

```text
results/fidelity/UNRESOLVED_REFERENCE_CHOICES.md
```

Include:

- question;
- source evidence;
- alternatives;
- selected interpretation;
- rationale;
- expected sensitivity;
- sensitivity result when tested.

## 7. Hardware policy

Hardware may reduce scale, never method identity.

When an exact effective batch does not fit memory, use mathematically equivalent microbatching/gradient accumulation and verify update equivalence on a fixture.

## 8. No overclaiming

- Method names do not prove fidelity.
- Passing import tests does not prove execution.
- Internal self-play improvement does not prove external strength.
- A correct small run does not reproduce paper-scale results.
- A stale summary invalidates final reporting.
