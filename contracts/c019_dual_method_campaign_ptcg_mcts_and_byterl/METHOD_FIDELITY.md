# Method-fidelity specification

A branch may use the names `MCTS`, `ISMCTS`, `ByteRL`, or `OSFP` only when every mandatory property below is present in source and runtime evidence.

## A. PTCG-ISMCTS mandatory properties

### Information and state

- Uses only information legally available to the submitted agent.
- Generates legal hidden-state determinizations without replacement from a known/prior deck multiset.
- Rejects impossible determinizations; never tops up with duplicate filler IDs.
- Stores a determinization/sample ID in every simulation trace.
- Refactors any stateful baseline/rollout policy into explicit branch-local memory.

### Tree

- Node contains parent/action, children, visit count `N`, total value `W`, mean value `Q`, prior `P`, player-to-move or perspective, simulator `searchId`, observation hash, and terminal flag.
- Selection uses UCT or PUCT. Default registered rule:

```text
score(s,a) = Q(s,a) + c_puct * P(s,a) * sqrt(N(s)) / (1 + N(s,a))
```

- Expands at non-root depths. Runtime traces must show multiple children from at least one non-root node when multiple legal actions exist.
- Progressive widening is allowed for large legal sets, but the rule must depend on visit count and must eventually expose additional legal actions.
- Every expanded child is produced by `search_step`, not by a static action score.
- Simulations/rollouts use a real policy at successor states: branch-local baseline, stochastic legal rollout, or later learned policy. Repeated option index `0` is forbidden.
- Backup updates all nodes on the selected path; zero-sum perspective/sign is tested.
- Multiple simulations revisit and update existing nodes. Root visit count must greatly exceed root child count.
- Aggregates root actions across multiple determinizations using canonical serialized actions and visits/values.
- Releases native search states correctly and enforces cumulative match time.

### Chance/randomness

- Record whether `search_step` samples random outcomes.
- When repeated identical action/state calls produce different successor hashes, represent them as sampled chance outcomes or redirect/chance children; do not silently overwrite one outcome.

### Valid names

- `PTCG_ISMCTS_V0` may use heuristic priors/leaf value and baseline rollouts.
- `PTCG_NEURAL_MCTS` is forbidden until a validated neural policy/value is actually integrated.

## B. PTCG-ByteRL mandatory properties

### Policy/value model

- Primary ByteRL model is initialized from fresh random weights. It is not a continuation of c018’s failed distilled/PPO checkpoints.
- Canonicalizes observation to current-player perspective.
- Encodes visible PTCG cards/zones/board/global state and current select context.
- Encodes each currently legal option and scores dynamic legal options; unavailable options receive exactly zero probability after masking.
- Uses recurrent memory across atomic decisions; registered default LSTM hidden size is 256.
- Provides both policy logits and value estimate.
- Simulator’s sequential selection contexts serve as the PTCG autoregressive action decomposition; every atomic decision and recurrent state transition is logged.

### Actor-learner and losses

- Actors record behavior-policy logits/probabilities and policy version.
- Learner records target-policy logits and importance ratio `rho = pi/mu`.
- Uses real V-trace targets, not ordinary GAE renamed V-trace.
- Uses UPGO auxiliary policy loss.
- Uses the paper-inspired V-trace/PPO-clipped policy objective; conventional PPO alone is not ByteRL.
- Default registered source hyperparameters, adapted only with explicit justification:
  - gamma 1.0;
  - learning rate 7e-5;
  - entropy weight 0.01;
  - policy/V-trace weight 1.0;
  - UPGO weight 1.0;
  - value loss weight 1.0;
  - PPO clip epsilon 0.2;
  - lower c/rho 0.001;
  - upper c/rho 1.007;
  - sample reuse 2.
- Uses a bounded FIFO/queue actor buffer and measures actor/learner staleness; do not silently use an uncontrolled replay ring.
- Every training claim requires actual completed simulator games, nonzero optimizer steps, finite losses, gradient evidence, and changed checkpoint hashes.

### OSFP

- Maintains current learner and immutable historical checkpoint list `H`.
- Defines learning periods from actual completed games/decisions.
- Uses `p = 0.6` probability of current learner self-play unless a measured single-machine calibration justifies one registered value.
- Otherwise samples a historical opponent according to a registered payoff-based function `f`.
- Maintains actual `G[i]` return sums and `C[i]` game counts for current learner versus each `H[i]`.
- After each LP, adds current learner to `H` when it exceeds `xi = 0.55` versus every sufficiently sampled historical opponent, or after more than `c = 6` LPs without promotion, matching source pseudocode.
- A forced addition is labeled `FORCED_MAX_LP`, never performance promotion.
- Records complete payoff matrix and opponent sampling probabilities.
- Predetermined self-play ramps are forbidden.

## C. Shared pipeline/hybrid fidelity

The project pipeline may import only switchable adapters:

- ByteRL legal-option logits → normalized MCTS priors;
- ByteRL value → leaf evaluation;
- MCTS root visit distribution → optional auxiliary-target record.

Each adapter must be individually disabled. c019 does not require hybrid training or submission.

The hybrid may be called an improvement only when it beats the stronger pure parent under the common panel or materially reduces search cost without strength loss.
