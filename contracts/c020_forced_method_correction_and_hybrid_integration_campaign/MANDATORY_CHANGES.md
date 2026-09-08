# c020 Mandatory Changes — No Discretion

This file is normative. Every item must be implemented or explicitly reported `FAILED_IMPLEMENTATION`. Claude may not substitute an easier method.

# A. Corrected information-set MCTS

## A1. Shared information-set statistics across determinizations

c019 creates one independent tree per determinization and aggregates only root actions. c020 must share action statistics at legally observable information sets.

Implement an information-set key containing only information available to the acting player:

```python
InfoSetKey = (
    visible_observation_hash,
    acting_player,
    select_context_signature,
    canonical_legal_action_signature,
    public_branch_memory_signature,
)
```

The key must exclude:

- sampled opponent hand identities;
- sampled prize identities;
- sampled hidden deck order;
- native search IDs;
- other determinization-private values.

Maintain a shared table:

```python
class InfoSetStats:
    N: int
    actions: dict[ActionKey, ActionStats]

class ActionStats:
    N: int
    W: float
    Q: float
    P: float
    availability: int
```

Every determinization-specific native node references the shared `InfoSetStats`. Selection and backup update shared action statistics. Track action availability so actions unavailable in some determinizations are not incorrectly penalized.

Keep the c019 separate-tree PIMC path as a named control.

## A2. Branch-local baseline memory

Every branch carries a deep-copyable explicit baseline state:

```python
@dataclass(frozen=True)
class BaselineMemory:
    plan: ...
    pre_turn: ...
    ability_used: ...
```

Required API:

```python
recommend(observation, memory) -> (action, proposed_memory)
advance_after_executed(observation, executed_action, memory) -> next_memory
clone_memory(memory) -> memory_copy
```

No mutable module globals may influence a simulated branch.

Prove:

- search-disabled refactor action parity;
- sibling memory independence;
- override updates memory for the action actually executed;
- native rollout and real-game baseline states remain isolated.

## A3. Expansion and continuation at every depth

At every nonterminal node:

1. canonicalize legal actions;
2. obtain branch-local baseline recommendation;
3. include baseline action;
4. include up to three additional credible legal alternatives;
5. progressively expose more actions according to visit count;
6. create successors only through `search_step`;
7. continue to attack/end-turn/terminal/depth/time cutoff.

Forbidden:

- root-only branching;
- hardcoded option index continuation;
- static child scores without successor simulation;
- treating a legal-option-list hash as a complete state hash.

## A4. Real PUCT lifecycle and perspective-correct backup

Each simulation executes:

```text
sample determinization
→ traverse shared information-set tree using PUCT
→ expand a real successor
→ rollout or evaluate
→ backpropagate from root-player perspective
```

Registered PUCT:

```python
U = c_puct * P * sqrt(parent_N) / (1 + action_N)
score = Q + U
```

If player perspective changes, transform value consistently. Runtime traces must include selection scores, selected action, depth, leaf value, and backup path.

## A5. Baseline-guided rollout

Rollout uses branch-local baseline recommendations at successor states. It may add low-probability stochastic alternatives only under a preregistered rule.

Rollout stops at:

- terminal;
- attack or end of turn for own-turn search;
- configured depth;
- time budget.

Option index `0` is never the default rollout policy.

## A6. Tactical PTCG leaf evaluator

Replace c019's four-feature objective. Implement separately logged features:

```text
terminal win/loss
immediate game-winning lethal
immediate knockout
prizes gained by this line
damage dealt this turn
productive attack executed
attack enabled this turn
active attacker readiness
backup attacker readiness
correct typed energy for legal attacks
energy stranded or wasted
active survival / opponent visible KO threat
target prize value
bench liability / gust exposure
critical attacker/evolution/search/gust/recovery resources consumed
remaining viable prize route
hand/search flexibility
penalty for ending turn without productive attack when one exists
```

The evaluator must use exact card/attack metadata available in the starter kit. Do not infer attack readiness from total energy count alone.

Every sampled leaf trace records each feature and weighted contribution.

One registered weight vector only after the smoke/repair pass. No broad weight sweep.

## A7. Legal uncertainty handling

Determinizations must obey exact deck/card multiplicities and visible information.

For unknown archetype, do not default silently to Dragapult. Use an explicit prior mixture over frozen known archetypes plus an `unknown` fallback derived only from legal generic assumptions. Record prior weights and sampled archetype.

Reject and resample impossible worlds. Never duplicate filler cards.

## A8. Conservative override gate

Baseline is the default root action. Search may override only when all are true:

```text
minimum simulation count met
minimum determinization count met
candidate available in sufficient determinizations
candidate visit share above threshold
candidate Q margin above baseline threshold
cross-determinization agreement above threshold
no unsupported-effect flag
no unsafe latency flag
```

Mandatory veto:

- reject an `end turn` override when baseline has a productive non-end action unless the search line proves a tactical reason such as deliberate resource preservation with no legal attack benefit;
- reject unstable ties;
- reject overrides based on one determinization only in pivotal contexts.

Log every opportunity, retained baseline, override, veto reason, confidence, and later game outcome.

# B. Corrected ByteRL / OSFP

## B1. Slot-aware PTCG observation representation

Do not pool active and bench Pokémon together.

Represent separately:

```text
our active
our bench slots 1–5
opponent active
opponent bench slots 1–5
our hand tokens
our discard tokens
opponent visible discard tokens
prize counts
turn/select context
```

Each board Pokémon token includes, when available:

```text
card identity
owner
active/bench slot identity
evolution stage
damage / remaining HP
status identity
tool identity
attached energy counts by type
attached visible card identities
retreat cost
attack identities and typed costs
ability identity
prize value / rule-box status
```

Use explicit position embeddings. No mean/max pooling that destroys instance identity before option scoring.

## B2. Dynamic action-to-object representation

Each legal option encodes:

```text
action/select type
source hand card or source board card
target board slot/card
target player
attack/ability ID
energy type
searched/discarded/recovered card ID
selection ordinal and remaining count
```

The policy scores each legal option against the current state and referenced object representations, for example:

```python
option_logit = MLP([
    recurrent_state,
    option_embedding,
    source_object_embedding,
    target_object_embedding,
    context_embedding,
])
```

Canonical option round-trip must reproduce the exact environment payload.

## B3. Autoregressive multi-select with joint probability

For a decision selecting `k` items:

```text
select item 1
update mask/context
select item 2 conditioned on item 1
...
select item k
```

For variable count, model `STOP` only when legal.

Store:

- full ordered selection;
- environment payload;
- per-step logits/probabilities;
- joint behavior log probability;
- recurrent state before and after each sub-selection;
- masks and remaining-count context.

Joint probability:

```python
joint_logp = sum(log p(a_i | a_<i, state, mask_i))
```

The learner trains every sub-selection. Storing/training only the first item is forbidden.

## B4. Exact recurrent unroll semantics

At every actor unroll boundary store:

```text
initial hidden state h0
initial cell state c0
episode-start mask
actor policy version
observation/action/legal-mask sequence
complete action log probabilities
```

The learner must initialize from the recorded state. A burn-in alternative is allowed only when registered before scale and validated against recorded-state replay.

For every mid-game unroll, recomputed behavior/target logits must use the same recurrent history/state. Reset-to-zero mid-game is forbidden.

## B5. Correct V-trace and UPGO

Importance ratio uses complete joint action probability under identical observation, legal mask, and recurrent state:

```python
rho_t = exp(target_joint_logp_t - behavior_joint_logp_t)
```

Implement hand-computed fixtures for:

- single action;
- multi-select joint action;
- terminal sequence;
- truncated recurrent unroll;
- clipped rho/c boundaries;
- UPGO return recursion.

Live metrics must show nonzero V-trace and nonzero UPGO contribution.

## B6. Period-correct OSFP

At the start of every learning period:

```python
G_period = zeros(...)
C_period = zeros(...)
```

Do not carry these accumulators across periods.

At period end:

1. freeze the exact current checkpoint;
2. evaluate that frozen checkpoint against the historical population with fixed seeds/seats;
3. populate its payoff row from those games only;
4. compute the next payoff-driven opponent mixture;
5. promote only from frozen-checkpoint evidence;
6. record force-add separately from performance promotion.

Games from multiple evolving learner versions may not be pooled as promotion evidence.

## B7. Immutable historical population and actual mixture

Each historical model has:

```text
checkpoint hash
training step
learning period
creation reason: PERFORMANCE_PROMOTION | FORCE_ADD
payoff row
source evaluation IDs
```

Hashes must never change.

Record requested and actual completed games by opponent/checkpoint/seat. OSFP historical sampling must derive from the period-local payoff table, not a predetermined self-play ramp.

## B8. Fresh corrected training and package parity

Start from fresh random weights and fresh optimizer.

Package inference must reproduce repository:

- legal logits;
- autoregressive selected payload;
- recurrent transition;
- value output;
- deterministic/stochastic mode under fixed seed.

# C. Mandatory corrected hybrid

## C1. Branch-local neural memory in MCTS

Every search node stores a clone of corrected ByteRL recurrent state.

Advance neural memory through the exact simulated observation/action/sub-selection history. Siblings must not share mutable state.

`state=None` at every node is forbidden.

## C2. H0–H4 exact modes

```text
H0: baseline priors + tactical heuristic leaf
H1: ByteRL priors + tactical heuristic leaf
H2: baseline priors + ByteRL value leaf
H3: ByteRL priors + ByteRL value leaf
H4: ByteRL priors + preregistered blend:
    value = alpha * tactical_heuristic + (1-alpha) * calibrated_byterl_value
```

Register exactly one `alpha` before final results. No sweep.

## C3. Policy-prior admission

Before promotion, verify:

- exact action-key alignment;
- probabilities normalize over canonical children;
- credible-action prior floor;
- top-k coverage of baseline and tactically correct fixture actions;
- entropy/calibration;
- no catastrophic suppression of baseline action.

H1/H3/H4 still run smoke if admission fails but are non-promotable.

## C4. Value admission

Compare corrected ByteRL value against:

- constant mean predictor;
- c019 value control;
- random ranking;
- corrected tactical heuristic;
- actual outcomes on held-out MCTS leaves.

Use MSE/Brier/calibration/correlation/ranking metrics. H2/H3/H4 are non-promotable if value fails admission.

## C5. Hybrid comparison discipline

Use identical trees/budgets/seeds where isolating priors or values:

- H0 vs H1 changes only priors;
- H0 vs H2 changes only leaf value;
- H3 combines admitted corrected components;
- H4 changes only the registered blend.

The hybrid must beat the stronger pure parent to promote.
