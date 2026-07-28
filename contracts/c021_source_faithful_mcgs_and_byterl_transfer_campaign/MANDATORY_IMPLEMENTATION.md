# Mandatory Implementation

## A. MCGS_2019_OFFICIAL_SOURCE_PORT

### A1. Source acquisition and mapping

Retrieve:

```text
https://hearthstoneai.github.io/files/bots/UserCreatedDeckPlaying2019/2019_UCDP_MCGS.zip
https://ieee-cog.org/2020/papers2019/paper_257.pdf
```

Store external reference snapshots outside competition packages when licensing is unclear. Record hashes and inventory.

Create:

```text
results/fidelity/mcgs_official_source_inventory.json
results/fidelity/mcgs_source_to_ptcg_map.md
results/fidelity/mcgs_paper_equation_map.md
results/fidelity/mcgs_license_assessment.md
```

### A2. State abstraction and graph identity

Implement a PTCG abstraction with the same functional role as the official source:

- active-player information set;
- observable board and resources;
- hidden/private information excluded according to the source perspective;
- source-equivalent commutative-action aggregation;
- exact explicit handling for PTCG distinctions that change legal actions or future effects.

The transposition table must create a single rooted DAG keyed by the abstraction. Log every merge and collision audit.

### A3. Modified UCD

Implement the source's exact edge-statistic structures and selection formulas, including descendant-depth aggregates and every parameter used by the source.

Implement recursive updates for non-traversed incoming edges exactly where the source does.

Independent numerical fixtures must calculate selection and update results without calling production code.

### A4. Imperfect information and chance

Implement source-faithful chance-node generation when hidden information/randomness is encountered, not root-only determinization.

Implement:

- chance outcome sampling;
- transposition lookup of sampled outcomes;
- sparse-sampling threshold;
- damped-sampling behavior;
- source probability/count semantics;
- legal PTCG hidden-state generation.

### A5. Atomic actions and graph reuse

Search legal PTCG selections as atomic actions and preserve/re-root the graph across sequential selections/atomic actions as the source does.

Do not collapse the entire turn into one opaque action unless the original source does so for the analogous category.

### A6. Expert knowledge

Port the source's category filters and obliged-action framework by semantic role.

Every PTCG translation must document:

- original Hearthstone behavior;
- PTCG counterpart;
- why it is semantically equivalent;
- fixture states;
- effect on legal actions and rollout distribution.

Do not add opportunistic c020 heuristics to the reference branch.

### A7. Simulation and payoff

Use the source rollout/default behavior and terminal reward semantics. Do not insert a learned or handcrafted leaf evaluator.

If a practical guard is required for infinite/invalid games, register it as a mechanical safety adapter and report every activation.

### A8. Time and parallelization

Implement source time-allocation and available root/leaf parallelization behavior. Preserve per-deck/source parameters in the reference configuration.

Use the local hardware to measure scaling, but do not change search semantics.

### A9. Known defect reproduction

Create a controlled test demonstrating the known information-set/memory limitation described by the paper/source. The reference branch must reproduce source behavior. The corrected branch may fix it.

### A10. Corrected/legal branch

After all reference conformance probes pass, create:

```text
MCGS_2019_PTCG_LEGAL_CORRECTED
```

Allowed separately registered corrections:

- competition-legal opponent information regime;
- corrected information memory;
- PTCG abstraction precision necessary for legal/future distinctions;
- deployment scheduling/time budget;
- implementation optimizations proven behavior-preserving.

No correction may mutate the reference branch.

## B. ByteRL reference ladder

### B1. Source search

Search author pages, paper supplements and official competition material for a complete ByteRL implementation/configuration. Record queries, URLs, dates and conclusions.

Do not assume a source exists. Do not claim source fidelity when only paper fidelity is available.

### B2. End-to-end PTCG meta-environment

Implement one episode containing:

```text
legal PTCG deck construction
→ deck freeze/validation
→ battle initialization
→ complete match
→ terminal reward propagated to construction and battle decisions
```

The reference must not be fixed-deck-only.

Provide deterministic deck legality tests, duplicate/count constraints, evolution/basic constraints, energy/card-pool constraints and exact submitted-deck serialization.

### B3. Representation and recurrent architecture

Preserve disclosed ByteRL/Hearthstone architecture and shared representations.

At minimum encode without identity loss:

- active slot;
- every bench slot;
- Pokémon/card identity and features;
- HP/damage;
- typed energy;
- status;
- tools;
- attacks/abilities and use state;
- hand/discard/deck/prize observables;
- turn/resources;
- opponent-visible information;
- construction-stage choices/card pool;
- dynamic legal options and their exact source/target/object references.

Use the disclosed recurrent width and network structure. Unspecified dimensions enter the unresolved-choice ledger.

### B4. Complete autoregressive actions

Represent a complete PTCG action as a sequence until termination/confirmation:

```text
action type
→ source/object
→ target
→ additional selected objects/cards
→ confirmation/termination
```

At each step:

- recompute the legal mask for the current prefix;
- condition logits on observation, recurrent state and prior prefix;
- store selected item probability/log-probability;
- sum log-probabilities for the complete joint action;
- verify actor/package/learner reconstruction.

### B5. Actor–learner

Implement:

- versioned actor checkpoints;
- asynchronous actor processes;
- bounded blocking FIFO queue;
- no random replay sampling;
- exact episode/unroll ordering;
- stored `h0/c0` or equivalent recurrent start;
- behavior joint log-probabilities;
- episode boundaries and reset flags;
- queue occupancy, age and policy lag;
- producer/consumer control.

### B6. V-trace, UPGO and published improved objective

Implement exact equations from primary sources. Create independent numerical fixtures and gradient checks.

Do not reuse c020 code unless it passes equation-level equivalence tests.

### B7. OSFP

Implement:

- immutable historical policy population;
- paper-defined current-vs-history opponent mixture;
- period-local payoff evidence;
- frozen-checkpoint evaluation;
- promotion threshold/counter rules;
- checkpoint hash immutability;
- requested-versus-realized opponent frequencies;
- population exploitability/diversity diagnostics.

### B8. Cumulative stages

Implement stage manifests with exact deltas:

```text
BR0    base end-to-end ByteRL/Hearthstone transfer
BR1    BR0 + gamma=1
BR1_5  BR1 + published random deck-construction initialization
BR2    BR1_5 + blocking FIFO and producer/consumer balancing
BR3    BR2 + modified V-trace and published PPO-style policy objective
```

No other difference is allowed between adjacent stage comparisons.

### B9. Training scale

Use fresh initialization. Preserve architecture/hyperparameters. Run at attainable scale.

Report:

- samples, games, decisions and updates;
- actor count and learner throughput;
- learning periods completed;
- fraction of published reference scale where computable;
- wall-clock;
- queue utilization;
- external strength trajectory.

### B10. Component analysis

Analyze separately:

1. policy-prior quality;
2. state/card/Pokémon representation;
3. autoregressive action accuracy;
4. recurrent-state contribution;
5. OSFP diversity and external generalization;
6. deck-construction usefulness;
7. value calibration.

A standalone weak policy does not end the analysis.

## C. Transfer laboratory

After both source/method fidelity gates pass, run isolated transfers:

### C1. Policy priors

Compare under identical MCGS budgets:

```text
reference MCGS priors/default
vs
one fixed conservative mixture with ByteRL priors
```

Pre-register the mixture and baseline-action floor. Do not tune after final-panel inspection.

### C2. Value

Admit ByteRL value only if held-out calibration passes predefined MSE/correlation/ranking thresholds against heuristic and constant baselines.

### C3. Other components

Each additional transfer requires one changed component, one explicit hypothesis and one controlled panel.

No simultaneous multi-component full hybrid.
