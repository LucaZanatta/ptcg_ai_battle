# Every reported metric that is identically zero, and why

A counter reading 0 has three very different meanings, and a report that does not separate them is
misleading:

1. **Correct-and-required** — it *must* be 0, and a test proves the counter can move.
2. **Correct-and-explained** — 0 follows from the configuration, with a stated mechanism.
3. **Inert** — nothing could ever have set it. This is the dangerous one, and it is the shape of
   c020's end-turn veto test, which passed while the veto never fired.

Fourteen numeric fields are identically 0 across all 11 MCGS runs. Each is classified below.

---

## 1. Correct-and-required (a test proves the counter moves)

| Metric | Why 0 is the required value | Proof it can move |
|---|---|---|
| `manual_coin_node_ucb_selected` | A coin flip reaching the UCB path would let the search *choose* its own randomness and become clairvoyant. | `MCGS_A4_COIN_NEVER_UCB_SELECTED` injects an unmarked coin context and requires the counter to reach 1. |
| `step_errors`, `release_errors` | No engine call failed. | Both are incremented on the exception path, and `step_calls` / `release_calls` are in the millions, so the paths are exercised. |
| `begin_errors` | No determinization was rejected. | **Was inert until this audit** — declared and set by nothing. Now incremented on a `search_begin` failure. |

## 2. Correct-and-explained (0 follows from the configuration)

| Metric | Mechanism |
|---|---|
| `recursive_reward_updates`, `recursive_visit_updates` | `UCDParams(1, 0)` makes `RecursiveUpdate` **inert by design**, reproduced rather than "fixed" (`FIDELITY_RULES §5`). The proof that the code path is reached is `recursive_update_noops`, which is in the thousands. |
| `chance_sparse_cutoffs` | The cutoff needs a chance node with **more than 5** outgoing edges. `COIN_HEAD` is a two-outcome select, so a coin node can never exceed 2. Structurally unreachable in PTCG, not unimplemented. |
| `rollout_aborts`, `rollout_retries` | The 1000-step rollout cap was never hit; `rollout_terminal_rate` is 1.0, so every rollout reached a real terminal well inside the cap. |
| `rollout_turn_caps` | **Was inert until this audit** — the counter existed while the source's `if ((game.Turn + 1) / 2 == 45) return 0.0;` was never implemented. Now implemented; these runs predate it. |

## 3. The finding: an entire subsystem is inert in play

Three zeros travel together and share one cause:

| Metric | |
|---|---|
| `terminal_leaves` | 0 |
| `finalised` | 0 |
| `lethal_bonus` | 0 |

`terminal_leaves` increments when the **tree policy descends onto a terminal node**. It is 0 in
every run, so **the search tree never contains a terminal state**. Max depth across the campaign
is 8–12 plies while games run to hundreds of decisions, so every terminal is discovered inside a
*rollout* and never becomes a node.

That single fact makes three faithful source features dead weight here:

- **Terminal node values of ±10** (against 1/0 rollout returns) never enter the tree, because no
  tree node is terminal. The dramatic asymmetry that dominates `Edge.Value` in the reference is
  simply never evaluated.
- **`Node.Finalise`**, the lethal-sequence collapse that prunes a parent onto a proven winning
  edge, cannot fire — it requires a terminal node in the tree. Note this was *also* genuinely
  broken until this contract fixed `BackupUCD` to carry the `Finalise` block; the fix was
  necessary but is not sufficient to make it fire.
- **The lethal bonus** (`reward *= 10` for a win on the starting turn) likewise never applies.

**Why it matters.** These are exactly the mechanisms that make the reference decisive once a win
is in view. In this port they are implemented, unit-tested, and *never reached in play*. Any claim
that the port "reproduces the source's terminal handling" is true statically and vacuous
dynamically, and this file exists so that distinction is on the record.

It also compounds the finding in
`FINDING_single_determinization_overconfidence.md`: the search is simultaneously **over**-confident
about rollout outcomes (one determinization) and **blind** to proven terminal states inside its own
tree. Deepening the tree — or shortening the horizon so terminals fall inside it — is a
prerequisite for the terminal machinery to contribute at all.

## 4. Partially inert: A4's sampling half

| Metric | |
|---|---|
| `chance_samples` | 0 |
| `chance_nodes_created` | 46–132 per run |

Chance nodes are created and expanded, but `chance_samples` — incremented when `BestChild`
**samples** an existing chance node by `SampleCount` — never moves. The reason is
`IsFullyExpanded`: a chance node is only sampled once `SampleWidth = 24` samples have accumulated
on its edges, and no individual coin node is visited 24 times within one decision's budget.

So A4's **creation and expansion** paths are exercised in play; its **weighted-sampling** path is
implemented and unit-tested (`test_sample_child_is_weighted_by_sample_count`) but not reached at
this budget. Stated here rather than left for a reader to infer from a zero.
