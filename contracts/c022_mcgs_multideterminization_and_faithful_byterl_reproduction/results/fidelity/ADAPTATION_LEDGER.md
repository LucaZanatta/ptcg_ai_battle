# Adaptation ledger

`FIDELITY_RULES §2` requires every method change to carry one of five labels:

```text
MECHANICAL_ADAPTER        forced by the target API or runtime; no algorithmic content
SEMANTIC_GAME_ADAPTER     the games differ; the property is preserved, the mechanism differs
LEGAL_INFORMATION_ADAPTER a change to what information the agent may use
DEPLOYMENT_ADAPTER        a change made only to fit a deployment budget
ALGORITHMIC_ADAPTATION    a genuine change to the algorithm
```

and adds: "Only the first two may exist in a pure reference branch. Legal-information and
deployment changes require separately named branches. Algorithmic adaptations require isolated
ablations."

The branch names in this contract exist to satisfy that rule:

```text
MCGS_2019_PTCG_MULTI_DET_REFERENCE       mechanical + semantic + the legal-information adapter
MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY   the above plus deployment clocks
MCGS_MULTI_DET_ROBUST_LCB                the above plus one algorithmic adaptation
```

---

## MCGS

### A1 — K independent search sessions instead of per-rollout re-determinization

| field | value |
|---|---|
| **Label** | `LEGAL_INFORMATION_ADAPTER` |
| **Source behaviour** | `SingleThreadRollout` clones the leaf's game and calls `SabberUtils.Determinize(game, rnd, all: true)` before EVERY rollout, so each simulation evaluates a fresh hidden world inside one graph. |
| **Port behaviour** | K independent `search_begin` sessions per decision, each with its own hidden world, root statistics aggregated across them. |
| **Forced by** | probe M01b: `search_step` is deterministic within a session (12/12 trials, one successor); an interior observation carries no `search_begin_input` and `search_begin` on one raises `ValueError("Not agent observation.")`. Eleven source sites depend on interior hidden-state mutation. |
| **Alternative rejected** | reconstructing an observation to re-root a session mid-tree. The reconstruction is not the engine's state and would inject states the engine cannot produce. |
| **Why not source-identical** | `FIDELITY_RULES §3` is explicit that the K-session ensemble is an approximation. The source re-determinizes per ROLLOUT inside one graph; this re-determinizes per SESSION. |
| **Evidence** | `mcgs_hidden_information_source_map.md`, `mcgs_hidden_information_gap_analysis.md`, `results/probes/mcgs_world_probes.json` |

### A2 — the aggregation rule is a PORT, not an adaptation

| field | value |
|---|---|
| **Label** | none required — this is source behaviour |
| **Source** | `MonteCarloGraphSearch.AggregateDeterminizations` sums successor `VisitCount` and `Rewards` per `ActionIndex`; `MCGS.Select` picks `MaxChild` on the aggregate. |
| **Note** | This is the audit's substantive finding. The archive ships the complete ensemble — generator, per-simulation picker, aggregator, and between-decision replenishment — and it is unreachable only because `determinizations` is assigned nowhere and `NodeConfig.PIMC` ships `false`. c022 did not have to invent an aggregation rule. |

### A3 — even deterministic assignment of simulations to worlds

| field | value |
|---|---|
| **Label** | `MECHANICAL_ADAPTER` |
| **Source behaviour** | `PickDeterminization` chooses uniformly at random among not-in-use determinizations, under a lock, across threads. |
| **Port behaviour** | simulations are split evenly and deterministically: `total // K` per world, remainder distributed one per world. |
| **Forced by** | `MANDATORY_IMPLEMENTATION A4` requires "simulations per world = total / K" exactly. Uniform-random assignment in a single-threaded arm gives a ragged split, so the causal comparison would be confounded by sampling noise in the split itself. |
| **Evidence** | `test_m05_fixed_total_uses_exactly_equal_total_simulations` asserts the sum is EXACTLY the total for every K. |

### A4 — sessions do not survive a decision

| field | value |
|---|---|
| **Label** | `MECHANICAL_ADAPTER` |
| **Source behaviour** | `CleanUpDeterminizations` re-roots each determinization onto the played action and replaces any that no longer matches with a fresh one, so subtrees persist across decisions. |
| **Port behaviour** | each decision opens K fresh sessions. |
| **Forced by** | `search_end` invalidates every searchId, and an interior observation cannot open a session. |
| **Consequence recorded** | statistics could be carried across decisions by abstraction key (c021's `graph_reuse`), but worlds are resampled per decision, so slot *i* at decision *t+1* is not the world slot *i* held at *t*. Carrying a per-slot table would seed a world's search with another world's statistics. Reuse is therefore DISABLED in every K-sweep arm; a separate reuse-enabled K=1 arm exists only for probe M04. |

### A5 — the ensemble is bolted onto `!PIMC` semantics

| field | value |
|---|---|
| **Label** | `MECHANICAL_ADAPTER`, with a stated deviation |
| **Source behaviour** | the ensemble IS the source's PIMC configuration, under which `Node.Finalise` returns false and `Node.Update` applies an extra `if (IsEndTurn && PIMC) reward *= -1`. |
| **Port behaviour** | each world runs the c021 `!PIMC`-minus-unavailable-operations semantics, with the ensemble on top. |
| **Why** | so that K=1 is the c021 control and probe M04 has something to compare against. Adopting PIMC semantics as well would have changed two things at once. |
| **Observationally nil at this scale** | the frozen K1 control records `finalised: 0`, `terminal_leaves: 0`, `lethal_bonus: 0` over 226,277 rollouts, so neither PIMC-gated behaviour ever fired. Per-world counters keep this honest rather than assumed: `mixed_terminal_scale_decisions` fires if a terminal is ever reached. |

### A6 — a per-game decision budget

| field | value |
|---|---|
| **Label** | `MECHANICAL_ADAPTER` |
| **Source behaviour** | no per-game cap; the source plays until the game ends. |
| **Port behaviour** | past `decision_budget` searched decisions the agent still plays every decision, it stops searching. |
| **Why a DECISION count and not a clock** | under `fixed_per_world` a K=8 decision costs eight times a K=1 decision, so a wall clock cuts high-K arms earlier in decision space; since excluded games leave the field score, the surviving subsample would be K-dependent and "K=8 is worse" would be unfalsifiable. |
| **Evidence** | `decision_budget_exhausted_decisions` is reported per arm; the analyzer gates on exclusion spread across K. |

### A7 — a multi-select payload from a single-action ranking

| field | value |
|---|---|
| **Label** | `SEMANTIC_GAME_ADAPTER` |
| **Source behaviour** | one `PlayerTask` per edge; Hearthstone has no `minCount..maxCount` select. |
| **Port behaviour** | when `minCount > 1`, the payload names the top `minCount` action indices by the aggregate value the search already computed, chosen action first. |
| **Why not something simpler** | a random or option-order completion would discard the search's opinion about every element after the first — precisely the c019/c020 defect of scoring a k-element select as a single pick. |
| **Found by** | defect D13: 10 of 60 games ending `["INVALID","DONE"]` with `decision_budget_exhausted_decisions: 0`. |

### A8 — deployment clocks

| field | value |
|---|---|
| **Label** | `DEPLOYMENT_ADAPTER` |
| **Branch** | `MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY` — separately named, as §2 requires |
| **Change** | a cumulative match clock and a per-decision cap, neither of which the source has. |
| **Rule** | `FIDELITY_RULES §2` and `MANDATORY_IMPLEMENTATION A6`: deployment constraints never judge source transfer. The reference arm is simulation-budgeted and carries no clock. |

### A9 — robust lower-confidence aggregation

| field | value |
|---|---|
| **Label** | `ALGORITHMIC_ADAPTATION` |
| **Branch** | `MCGS_MULTI_DET_ROBUST_LCB` — separately named |
| **Change** | select by `mean − z·SE` over per-world action values instead of the summed value. |
| **Source counterpart** | none. `MANDATORY_IMPLEMENTATION A3` permits it only as "an explicitly adapted secondary arm". |
| **Isolated ablation** | it is computed for every decision alongside the primary rule, from the same raw per-world statistics, so the comparison costs no extra games. |

---

## ByteRL

ByteRL has **no author implementation** (`byterl_source_search.md`), so its authority is the
papers. Every entry below is an adaptation from a PAPER, and the asymmetry with MCGS — which has
an audited source archive — is structural and survives into the final report.

### B1 — the action grammar

| field | value |
|---|---|
| **Label** | `SEMANTIC_GAME_ADAPTER` |
| **Paper behaviour** | a Hearthstone action factorizes as action type → source → target → confirm. |
| **Port behaviour** | a PTCG decision is a `select` with `minCount..maxCount` over an option list, so the factorization is COUNT token → ELEMENT token × k. |
| **Property preserved** | a complete action is a sequence of masked categorical choices whose joint log-probability is the sum of per-token log-probabilities — exactly what V-trace and UPGO require. |
| **Why the COUNT is a token** | c021's sampler looped to `k_max` unconditionally, so its policy ALWAYS took the maximum and could never learn to discard two cards instead of three. Making the count a masked categorical puts it under the policy and inside the joint. Probe B04 requires more than one distinct count to be sampled and forbids always taking the maximum. |

### B2 — recurrence advances per DECISION, not per token

| field | value |
|---|---|
| **Label** | `SEMANTIC_GAME_ADAPTER` |
| **Reason** | a PTCG decision emits several tokens. If the LSTM advanced per token, an unroll's timestep count would depend on how many tokens each decision needed, and the learner could not replay it from a stored `(h0, c0)` without also replaying the tokenization. Within a decision, the autoregressive head conditions on tokens already chosen through a separate stateless summary. |
| **Evidence** | probe B06: 138 exact-weights checks, max recurrence delta 0.0. |

### B3 — B1.5's "published random initial construction choices"

| field | value |
|---|---|
| **Label** | `SEMANTIC_GAME_ADAPTER` |
| **Paper behaviour** | Hearthstone's B1.5 randomizes the initial deck-construction selections. |
| **Port behaviour** | the construction policy's initial choices are drawn from the legal mask rather than from the (near-uniform) freshly initialized head. |
| **Status** | recorded in `UNRESOLVED_REFERENCE_CHOICES.md`: the papers do not specify the distribution, and the closest semantic reading is used. |

### B4 — OSFP history eviction

| field | value |
|---|---|
| **Label** | `ALGORITHMIC_ADAPTATION` (small, but not paper-specified) |
| **Change** | the historical pool is capped and evicts the OLDEST entry. |
| **Why recorded** | the papers do not state a cap or an eviction rule. Whatever is evicted, what remains is byte-immutable (probe B16). The alternative (reservoir sampling) and a sensitivity test are in `UNRESOLVED_REFERENCE_CHOICES.md`. |

### B5 — actor count and scale

| field | value |
|---|---|
| **Label** | `MECHANICAL_ADAPTER` |
| **Change** | far fewer actors and far fewer samples than the papers. |
| **Permitted by** | `CONTRACT.md §4`: hardware may reduce actor count, sample count, duration and learning periods. It may not alter architecture, FIFO semantics, recurrence, objectives, autoregression or OSFP mechanics — and none of those are reduced here. |
| **Consequence** | `BYTERL_SCALE=COMPUTE_LIMITED` is the expected honest status under `DECISION_RULES §3`. |
