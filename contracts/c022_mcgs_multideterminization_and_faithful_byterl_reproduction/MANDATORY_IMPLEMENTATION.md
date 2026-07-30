# Mandatory Implementation

## A. MCGS hidden-information correction

### A1. Audit before code

Re-open the official MCGS archive already acquired in c021 and hash it again. Map the source classes/functions responsible for:

- private-information save/restore;
- determinization and re-determinization;
- random/chance handling;
- observer-specific information sets;
- graph identity and transpositions;
- simulation initialization and cleanup.

Produce:

```text
results/fidelity/mcgs_hidden_information_source_map.md
results/fidelity/mcgs_hidden_information_trace.jsonl
results/fidelity/mcgs_hidden_information_gap_analysis.md
```

Do not implement K-way aggregation until the source behavior and the PTCG API limitation are demonstrated with traces.

### A2. Fresh legal hidden worlds

Implement a deterministic test harness that can request repeated `search_begin` sessions from the same public root state while varying only the environment RNG seed.

For every generated world verify:

- public observation is identical;
- hidden hand/deck/prize completion is legal;
- card multiplicities are legal;
- no root-player-inaccessible information reaches the agent;
- terminal/result semantics match the live simulator;
- world identity is logged without revealing hidden contents to policy code.

### A3. Multi-determinization algorithms

Implement:

```text
MCGS_K1_CONTROL
MCGS_MULTI_DET_K2
MCGS_MULTI_DET_K4
MCGS_MULTI_DET_K8
```

If per-simulation re-determinization inside one graph is feasible, use that closest source-faithful mechanism.

Otherwise use independent source-faithful MCGS sessions per hidden world and aggregate root actions using a preregistered rule derived from source edge statistics. Evaluate at least:

- visit-count summation;
- expected terminal-return summation;
- robust lower-confidence or quantile aggregation only as an explicitly adapted secondary arm.

Choose the primary aggregation rule before broad game outcomes are unblinded.

### A4. Causal protocols

Run both:

#### Fixed total simulations

```text
total simulations per decision constant across K
simulations per world = total / K
```

This isolates world diversity.

#### Fixed simulations per world

```text
simulations per world constant across K
total compute grows with K
```

This measures strength scaling.

Use simulation counts for causal attribution, not wall-clock. Record elapsed time separately.

### A5. Calibration

For every root decision record:

- sampled-world outcomes;
- per-world root action estimates;
- aggregate estimate;
- selected action;
- actual game result;
- predicted win probability calibration bin;
- between-world disagreement;
- action stability across repeated runs.

The correction is not accepted merely because K>1 executes. It must reduce the c021 overconfidence and improve or preserve external decisions.

### A6. Unrestricted and deploy variants

After K and aggregation are selected:

```text
MCGS_2019_PTCG_MULTI_DET_REFERENCE
```

uses the closest feasible source-style timing, including the original approximately 15-second initial and 10-second continuing decision schedule where technically possible.

Separately create:

```text
MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY
```

with legal cumulative clock/resource controls. Never use deployment constraints to judge source transfer.

## B. Faithful ByteRL reproduction

### B1. Architecture

Implement from fresh random weights:

- shared card/Pokémon embeddings;
- explicit active slot and ordered bench slots;
- typed energy, status, tools, damage, prize, turn, hand, discard and visible deck-construction context;
- recurrent LSTM with hidden size 256;
- policy and value heads using recurrent features;
- no feed-forward substitute.

### B2. Complete autoregressive action

Represent a complete PTCG decision as a variable-length sequence such as:

```text
action type → source → target → selected objects/cards → amount/index → confirm/end
```

At each step:

- generate the exact legal mask;
- include dynamic option/object features;
- store chosen token and behavior log-probability;
- reconstruct the exact joint log-probability as the sum of token log-probabilities;
- terminate only on a complete legal environment action.

### B3. Actors, FIFO, and recurrence

Implement actual asynchronous versioned actors and one learner:

- actors pull immutable versioned weights;
- each unroll stores initial LSTM `h0/c0`;
- bounded FIFO queue;
- producers block when full;
- FIFO samples are consumed once unless published sample reuse explicitly applies learner-side;
- record policy version, queue age, occupancy, production/consumption ratio, and actor blocking;
- tune actor count only to keep production/consumption close to one without changing semantics.

Recompute recurrent outputs independently during learner replay and assert agreement before optimization.

### B4. Objectives

Implement independent numerical references and production versions for:

- V-trace value target;
- UPGO return/advantage;
- b3 two-sided importance-ratio clipping `[0.001, 1.007]`;
- b3 PPO-style clipped policy objective with epsilon `0.2` and V-trace advantage;
- value loss;
- entropy loss;
- complete autoregressive joint ratio.

Ordinary PPO, one-sided V-trace, first-token-only ratios, or zeroed recurrent starts are hard failures.

### B5. OSFP

Implement the paper-faithful population process:

- immutable historical policies;
- self-play probability 0.6;
- historical-policy mixture documented from the original ByteRL references;
- period-local payoff and count accumulators;
- promotion threshold 0.55;
- forced promotion after six periods without promotion where the reference specifies it;
- frozen evaluation checkpoint per promotion decision;
- no mutable object aliasing between learner and history.

If the exact historical-mixture function is underspecified, preregister the closest supported interpretation and one sensitivity variant.

### B6. Deck-construction meta-environment

Implement two arms:

```text
FIXED_DECK_BATTLE_CONTROL
END_TO_END_DECK_CONSTRUCTION_AND_BATTLE
```

The end-to-end arm must:

- expose the legal card pool permitted by the competition, not only the union of scripted decks, unless a clearly labelled reduced-pool smoke is used first;
- build a legal deck through masked categorical/autoregressive decisions;
- instantiate battle games with that deck;
- propagate terminal game return to both construction and battle decisions;
- preserve deck diversity and legality evidence.

B1.5 uses the published random initial construction-choice schedule. If an exact Hearthstone choice has no literal PTCG equivalent, implement the closest semantic adapter and document it.

### B7. Published stage toggles

One codebase must produce machine-verifiable stages:

```text
BR0
BR1
BR1_5
BR2
BR3
```

Adjacent stages may differ only by the published change named in `FIDELITY_RULES.md`. Tests must reject extra changes.

## C. Transfer laboratory

Transfer starts only after:

```text
MCGS_HIDDEN_INFO = PASS or PARTIAL_WITH_MEASURED_IMPROVEMENT
BYTERL_REFERENCE_FIDELITY = PASS
```

Preregister and test one component at a time:

```text
T0 corrected MCGS control
T1 + faithful ByteRL policy prior
T2 + faithful ByteRL rollout/default policy
T3 + faithful ByteRL value only if held-out calibration passes
```

Use identical hidden worlds, paired seeds, fixed simulations, and enough games to distinguish the measured c021 run-to-run noise. Do not run a combined hybrid until one isolated component passes.
