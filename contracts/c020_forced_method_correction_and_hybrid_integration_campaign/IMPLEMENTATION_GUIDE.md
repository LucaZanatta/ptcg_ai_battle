# c020 Implementation Guide

This guide provides required implementation shapes. Exact filenames may differ only when the repository requires it; semantic requirements do not.

## 1. Suggested source layout

```text
cg/c020_infoset.py
cg/c020_ismcts.py
cg/c020_tactical_leaf.py
cg/c020_override.py
cg/c020_byterl_encode.py
cg/c020_byterl_model.py
cg/c020_byterl_actor.py
cg/c020_vtrace.py
cg/c020_osfp.py
cg/c020_hybrid.py
tools/c020_mcts_run.py
tools/c020_byterl_train.py
tools/c020_hybrid_run.py
tools/c020_panel.py
tools/c020_package.py
tools/c020_submit.py
tools/c020_validate.py
tests/test_c020_*.py
```

Keep c019 files unchanged as controls.

## 2. Information-set shared statistics

```python
@dataclass(frozen=True)
class InfoSetKey:
    visible_hash: str
    player: int
    select_signature: tuple
    legal_signature: tuple
    public_memory_signature: tuple

@dataclass
class SharedActionStats:
    n: int = 0
    w: float = 0.0
    prior: float = 0.0
    availability: int = 0

    @property
    def q(self) -> float:
        return self.w / self.n if self.n else 0.0

@dataclass
class SharedInfoSetStats:
    n: int = 0
    actions: dict[ActionKey, SharedActionStats] = field(default_factory=dict)
```

A native determinization node contains `search_id`, observation, private sampled world ID, and branch-local memories, but reads/writes action statistics from the shared table keyed by `InfoSetKey`.

Availability-aware PUCT must not treat unavailable actions as losses.

## 3. One simulation skeleton

```python
def simulate(root_world, shared_table, deadline):
    path = []
    node = root_world

    while True:
        if terminal(node) or cutoff(node) or time.monotonic() >= deadline:
            value = evaluate(node)
            break

        info_key = make_infoset_key(node)
        shared = shared_table.setdefault(info_key, SharedInfoSetStats())
        legal = canonical_legal_actions(node.observation)
        update_availability(shared, legal)

        action = select_puct(shared, legal, priors(node))
        path.append((shared, action, root_perspective(node)))

        if action not in node.native_children:
            node = expand_via_search_step(node, action)
            value = rollout_or_evaluate(node, deadline)
            break

        node = node.native_children[action]

    backup(path, value)
    return value
```

Runtime tests must prove non-root selection and expansion.

## 4. Tactical evaluator decomposition

Return both score and components:

```python
@dataclass
class LeafFeatures:
    terminal: float
    lethal: float
    ko_value: float
    prizes_taken: float
    damage_dealt: float
    productive_attack: float
    active_ready: float
    backup_ready: float
    typed_energy_ready: float
    energy_waste: float
    survival: float
    target_prize_value: float
    bench_liability: float
    critical_resource_cost: float
    future_prize_route: float
    flexibility: float
    unproductive_end_turn: float
```

Do not calculate readiness from total energy only. Use card metadata and actual attached energy types.

Every final score must be reconstructable from logged features and one registered weight file.

## 5. Conservative override

```python
@dataclass
class OverrideDecision:
    selected_action: ActionKey
    baseline_action: ActionKey
    override: bool
    veto_reason: str | None
    visit_share: float
    q_margin: float
    determinization_agreement: float
    simulations: int


def decide_override(root_stats, baseline_action, context):
    best = best_candidate(root_stats)
    if insufficient_budget(...):
        return retain("insufficient_budget")
    if best.action == END_TURN and context.baseline_productive:
        return retain("unproductive_end_turn_veto")
    if best.q - baseline.q < Q_MARGIN:
        return retain("q_margin")
    if agreement(best) < AGREEMENT_MIN:
        return retain("determinization_disagreement")
    return override(best)
```

Thresholds are registered after smoke and before scaled evaluation.

## 6. Slot-aware encoder

Use a tensor/list retaining object identity:

```text
state_global
board_tokens[12]  # our active + 5 bench + opp active + 5 bench
hand_tokens[max_hand]
discard_summary/tokens
context_token
```

Each legal option stores indices into source/target tokens. Use attention or concatenated gathers; do not reduce board objects to one mean before option scoring.

## 7. Dynamic option scorer

```python
state_ctx, board_ctx, recurrent_next = encoder(obs, recurrent_state)

for option in legal_options:
    source = gather(board_ctx, option.source_index)
    target = gather(board_ctx, option.target_index)
    option_vec = option_encoder(option.features)
    logits.append(policy_head(torch.cat([
        state_ctx, option_vec, source, target
    ], dim=-1)))
```

Missing source/target uses a learned null token, not zero ambiguity.

## 8. Autoregressive multi-select

```python
joint_logp = 0.0
selected = []
state = recurrent_state
mask = initial_mask

for step in range(required_or_until_stop):
    logits, state = model.select_step(obs, selected, mask, state)
    choice = sample_or_argmax(logits, mask)
    selected.append(choice)
    joint_logp += log_softmax(logits)[choice]
    mask = update_mask(mask, choice)
    if choice == STOP:
        break
```

Store all step-level records and exact final environment payload.

## 9. Recurrent unroll record

```python
Unroll(
    h0,
    c0,
    episode_start,
    actor_version,
    observations,
    canonical_options,
    selected_full_actions,
    behavior_joint_logp,
    rewards,
    done,
)
```

Learner starts from `h0/c0`. Add a probe that recomputes behavior logits with the stored actor checkpoint and obtains the recorded log probabilities within tolerance.

## 10. Period-correct OSFP

```python
for lp in learning_periods:
    G = np.zeros((population_size, population_size))
    C = np.zeros_like(G)

    train_against(osfp_mixture(previous_payoff_table), games_per_lp)
    frozen = freeze_current_checkpoint()
    eval_games = evaluate_frozen_checkpoint(frozen, historical_population)
    G, C = aggregate_only(eval_games)
    payoff_row = safe_divide(G, C)
    promotion = decide_promotion(frozen, payoff_row)
    update_population_and_next_mixture(promotion, payoff_row)
```

The promotion evaluation must never include games from changing learner weights.

## 11. Hybrid neural-state propagation

```python
@dataclass
class HybridNodeState:
    native_search_id: int
    baseline_memory: BaselineMemory
    neural_h: Tensor
    neural_c: Tensor
    observation: Observation
```

When `search_step` produces a successor, advance the neural model through the exact executed action/selection transition. Clone tensors for siblings or use immutable references.

## 12. Exact ablations

Implement named config files:

```text
mcts_c019_control.json
mcts_c020_corrected.json
byterl_c019_control.json
byterl_c020_corrected.json
hybrid_h0.json
hybrid_h1.json
hybrid_h2.json
hybrid_h3.json
hybrid_h4.json
```

No hidden config mutation between final-panel candidates.

## 13. Validator semantic checks

The validator must inspect source and runtime, not file existence only. It must fail when:

- c020 corrected MCTS instantiates one independent shared-stat table per determinization;
- leaf score lacks attack/lethal/typed-energy features;
- active/bench tokens are pooled before option scoring;
- multi-select stores one index only;
- a mid-game unroll has zero state without an episode boundary;
- target/behavior replay uses different recurrent state;
- OSFP G/C totals monotonically accumulate across periods;
- hybrid model calls use `state=None` for non-root nodes;
- H0–H4 are missing;
- c019 checkpoints initialize corrected ByteRL;
- skipped criteria are reported PASS.
