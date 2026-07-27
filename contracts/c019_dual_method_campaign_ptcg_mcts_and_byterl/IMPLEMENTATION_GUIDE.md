# Implementation guide and reference sketches

These are interface/pseudocode guides, not copy-paste replacements for understanding the repository.

## 1. Shared legal option representation

Use one canonical serializer for evaluation identity, neural option encoding, MCTS root aggregation, and package execution.

```python
@dataclass(frozen=True)
class CanonicalOption:
    select_type: int
    select_context: int
    option_type: int
    fields: tuple[int, ...]       # ordered typed scalar fields
    referenced_card_id: int       # 0 when not applicable
    referenced_attack_id: int     # 0 when not applicable

    def key(self) -> tuple:
        return (
            self.select_type,
            self.select_context,
            self.option_type,
            self.fields,
            self.referenced_card_id,
            self.referenced_attack_id,
        )
```

Round-trip tests must prove:

```text
API option → CanonicalOption → submission select payload
```

## 2. Branch-local baseline policy

Do not call the stateful official agent through module globals inside a tree.

```python
@dataclass
class PolicyMemory:
    plan: object
    pre_turn: object
    ability_used: frozenset
    recurrent_or_extra: dict

class RolloutPolicy:
    def initial_memory(self) -> PolicyMemory: ...

    def act(
        self,
        observation,
        memory: PolicyMemory,
        legal_options: list[CanonicalOption],
    ) -> tuple[CanonicalOption, PolicyMemory]:
        # Pure from caller perspective: do not mutate input memory.
        ...
```

A child node receives the `next_memory` produced by the action actually executed on that branch.

## 3. MCTS node

```python
@dataclass
class MCTSNode:
    search_id: int
    observation: object
    obs_hash: str
    determinization_id: str
    memory: PolicyMemory
    parent: 'MCTSNode | None'
    action_from_parent: CanonicalOption | None
    prior: float
    player_sign: int
    visits: int = 0
    value_sum: float = 0.0
    children: dict[tuple, 'MCTSNode'] = field(default_factory=dict)
    unexpanded: list[CanonicalOption] = field(default_factory=list)
    terminal: bool = False

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0
```

## 4. PUCT selection

```python
def select_child(node: MCTSNode, c_puct: float) -> MCTSNode:
    root = max(1, node.visits)
    return max(
        node.children.values(),
        key=lambda child: (
            child.q
            + c_puct * child.prior * (root ** 0.5) / (1 + child.visits)
        ),
    )
```

When perspective changes to the opponent, values must be negated consistently. Add a two-ply zero-sum fixture with known expected backup.

## 5. Progressive widening

Large legal option sets may use:

```python
allowed_children = min(n_legal, 1 + floor(k_pw * node.visits ** alpha_pw))
```

Registered initial values may be `k_pw = 1.5`, `alpha_pw = 0.5`; calibrate once. Baseline action, lethal attacks, and mandatory selections must never be permanently pruned.

## 6. One MCTS simulation

```python
def simulate(root, cfg, rng):
    node = root
    path = [node]

    # Selection + expansion at EVERY depth.
    while not node.terminal and len(path) < cfg.max_tree_depth:
        ensure_legal_options_and_priors(node)

        if can_expand(node, cfg):
            action = choose_unexpanded(node, rng)
            successor = api.search_step(node.search_id, to_select(action))
            child = make_child_from_successor(node, action, successor)
            node.children[action.key()] = child
            node = child
            path.append(node)
            break

        node = select_child(node, cfg.c_puct)
        path.append(node)

    # Rollout/cutoff from the expanded/selected successor.
    value = rollout_or_leaf(node, cfg, rng)

    # Backup.
    for visited in reversed(path):
        visited.visits += 1
        visited.value_sum += value * visited.player_sign
```

The actual implementation must correctly handle the native search lifecycle and should not retain released `searchId`s.

## 7. Determinization

For each known deck multiset:

```text
remaining multiset = full deck
- revealed board cards
- discard cards
- legally visible hand cards
- known moved/revealed cards from logs
```

Sample hidden zones without replacement. Validate exact counts and multiplicities before `search_begin`. For unknown opponent archetype, sample one archetype/profile from a prior distribution derived only from public/revealed information, then sample its hidden zones. Never read the true local opponent deck inside submission mode.

Run multiple determinizations per pivotal decision and aggregate canonical root actions:

```python
aggregate[action].visits += tree_root_child.visits
aggregate[action].weighted_value += tree_root_child.value_sum
```

## 8. ByteRL dynamic action model

The simulator already decomposes complex effects into atomic selection contexts. Treat each atomic option set as the autoregressive step.

```python
class PTCGByteRL(nn.Module):
    def forward(self, obs_tokens, legal_option_tokens, lstm_state):
        card_features = self.card_encoder(obs_tokens.cards)
        board_context = self.pool_and_context(card_features, obs_tokens.global_features)
        recurrent_context, next_state = self.lstm(board_context, lstm_state)
        option_features = self.option_encoder(legal_option_tokens, card_features)
        logits = self.option_scorer(recurrent_context, option_features)
        logits = logits.masked_fill(~legal_option_tokens.mask, -torch.inf)
        value = self.value_head(recurrent_context).squeeze(-1)
        return logits, value, next_state
```

Required token features include card ID/embedding, type/stage, zone, owner, position, HP/damage, energy composition, status, attached tools, known/revealed flag, select type/context, option type, and option references.

## 9. Actor unroll schema

Each unroll step must include:

```text
observation encoding
legal option encodings/mask
action index/canonical action
behavior logits and chosen probability
behavior policy version
reward/discount/done
value prediction
LSTM state at unroll start
opponent checkpoint identity
seat/deck/game/trajectory IDs
```

## 10. V-trace reference

Implement a standalone numerically tested reference before the optimized GPU path.

```python
rho = target_prob / behavior_prob
c = rho.clamp(min=rho_min, max=c_max)
rho_bar = rho.clamp(min=rho_min, max=rho_max)

delta = rho_bar * (reward + gamma * next_value - value)
# Reverse recursion equivalent to the source equation.
acc = torch.zeros_like(value[-1])
for t in reversed(range(T)):
    acc = delta[t] + gamma[t] * c[t] * acc
    vtrace[t] = value[t] + acc
```

Use the V-trace target at `t+1` in the PPO-clipped policy advantage as described by the Hearthstone ByteRL paper. Preserve behavior and target probabilities before clipping.

## 11. UPGO

Implement UPGO as a separate auxiliary policy loss with a unit-tested recursive return. Do not set the term to zero or alias it to the V-trace loss. Log its magnitude and gradient contribution separately.

## 12. OSFP loop

```python
historical = []
count_without_add = 0

for lp in learning_periods:
    G = [0.0] * len(historical)
    C = [0] * len(historical)

    while not lp.complete:
        if not historical or rng.random() < p_current:
            opponent = current_learner_snapshot
            reason = 'CURRENT_SELF_PLAY'
        else:
            probs = payoff_sampler(G, C, historical, registered_cfg)
            i = categorical(probs)
            opponent = historical[i]
            reason = 'HISTORICAL_PAYOFF_SAMPLE'

        game = play_real_game(current_learner, opponent)
        train_queue.put(game.unrolls)
        if reason == 'HISTORICAL_PAYOFF_SAMPLE':
            G[i] += game.return_pm_one
            C[i] += 1

    sufficiently_sampled = all(c >= cfg.min_games_per_history for c in C)
    beats_all = sufficiently_sampled and all((g / c) > cfg.xi_return for g, c in zip(G, C))

    if beats_all or count_without_add > cfg.max_lp_without_add:
        add_immutable_checkpoint(historical, current_learner)
        promotion_reason = 'PERFORMANCE' if beats_all else 'FORCED_MAX_LP'
        count_without_add = 0
    else:
        count_without_add += 1
```

Because paper pseudocode leaves probability function `f` abstract, pre-register one PTCG implementation. Recommended:

```text
estimated learner win_i = (G_i / C_i + 1) / 2
hardness_i = exp((0.5 - win_i) / temperature)
uncertainty_i = sqrt(log(1 + sum C) / (1 + C_i))
weight_i = hardness_i * (1 + beta * uncertainty_i) + epsilon
```

Normalize weights. Save a sensitivity-free single registered configuration; do not launch a sampler tournament.

## 13. Lightweight hybrid interfaces

```python
class PolicyPriorProvider(Protocol):
    def priors(self, observation, memory, legal_options) -> dict[tuple, float]: ...

class LeafValueProvider(Protocol):
    def value(self, observation, memory) -> float: ...
```

Implement adapters, but keep `heuristic`, `baseline`, and `byterl` selectable in config. The pure MCTS path must not depend on ByteRL.
