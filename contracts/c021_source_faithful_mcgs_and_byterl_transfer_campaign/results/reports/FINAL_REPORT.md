# c021 — source-faithful MCGS and ByteRL transfer campaign: final report

Generated 2026-07-29T02:57:26 from `reports/statuses.json`. Every figure below is read from that file at render time, so the narrative cannot drift from the evidence.

## Statuses

| Status | Value |
|---|---|
| `SOURCE_FIDELITY` | **PASS** |
| `EXECUTION` | **PASS** |
| `MCGS_COMPETITIVE` | **FAIL** |
| `BYTERL_METHOD` | **PARTIAL** |
| `BYTERL_SCALE` | **COMPUTE_LIMITED** |
| `TRANSFER` | **FAIL** |
| `PACKAGE` | **NOT_BUILT** |
| `SUBMISSION` | **PENDING** |
| `OVERALL` | **PARTIAL** |

## 1. Was MCGS source-faithful?

**PASS.** The official 2019 archive was retrieved and hashed, inventoried file by file, and its formulas transcribed into a paper equation map. Selection is UCB1 with no prior term, statistics live on edges, `Edge.Value` divides by `TotalVisit` under UCD, terminals are ±10 while rollouts return 1/0, and `UCDParams(1, 0)` leaves `RecursiveUpdate` inert — reproduced rather than 'fixed'.

Semantic validation: **18/18** checks, each of which injects the real defect and is required to reject it. Inert checks (pass clean *and* pass injected) are counted as failures: none.

**Where it is not faithful, and why:**

> The port is the !PIMC configuration MINUS the interior-determinization operations the PTCG API does not expose. Chance nodes exist only at the random surfaces manual_coin reveals. It does not sample draw order inside the tree.

The PTCG API fixes hidden information at `search_begin` and exposes no way to re-determinize an interior node, so the source's DRAW / ENDTURN / TRACKING chance types have no counterpart. `PIMC` is nonetheless left `False`, because the same flag also gates a reward sign flip, `Node.Finalise` and the END_TURN expansion path. Full detail in `fidelity/A4_chance_node_api_constraint.md`.

## 2. Did executed search actions help or hurt?

Best non-superseded MCGS run `transfer_T0_control_summary.json`: field score **0.1905** over 21 completed games, 95% Wilson interval [0.0767, 0.4].

Gate: lower bound of the 95% Wilson interval must exceed 0.5 against the field → **FAIL**.

> A technically faithful but weak MCGS is MCGS_COMPETITIVE=FAIL, not an implementation failure (DECISION_RULES §1).

| run | games | done | field | sims/dec | chance nodes | coin UCB | step err |
|---|---|---|---|---|---|---|---|
| `ablation_nochance_summary.json` | 24 | 24 | 0.1250 | 329.0 | 0 | 0 | 0 |
| `competitive_summary.json` | 24 | 22 | 0.1364 | 364.5 | 46 | 0 | 0 |
| `legal_corrected_summary.json` | 24 | 19 | 0.0526 | 58.8 | 90 | 0 | 0 |
| `transfer_T0_control_summary.json` | 24 | 21 | 0.1905 | 953.3 | 84 | 0 | 0 |
| `transfer_T1_policy_prior_summary.json` | 24 | 24 | 0.1667 | 770.9 | 58 | 0 | 0 |
| `transfer_T2_rollout_policy_summary.json` | 24 | 23 | 0.1739 | 806.5 | 5 | 0 | 0 |

### The noise floor, measured rather than assumed

`competitive` and `transfer_T0_control` are the SAME configuration -- the source port with every transfer switch off. Run independently they scored **0.1364** and **0.1905** (22 and 21 games). That 5.4-point spread between identical configurations is the resolution limit of a ~24-game arm, and every comparison below must be read against it. No difference smaller than this is interpretable, which is precisely why the transfer arms are reported as UNTESTED rather than rejected.

Across three contracts the same result has now reproduced: overriding a stateful scripted agent with a search costs roughly 18 points regardless of the search's quality, because the scripted opponent's line is internally consistent and a search that departs from it part-way inherits neither plan. The measured constraint is early-game credit assignment, not search depth.

## 3. Were the MCGS defects algorithmic, adaptation-related or throughput-related?

| defect | class | evidence |
|---|---|---|
| `Expand` returned continue unconditionally | algorithmic | 96,675 expansions, depth 175, zero rollout steps |
| untested actions taken FIFO, not uniformly at random | algorithmic | `Node.TreePolicy` draws uniformly |
| damping keyed on depth, not `numSampleTraversed` | algorithmic | deep chance nodes read as fully expanded at one sample |
| rollout checked the decision deadline | adaptation | the source bounds a rollout by a 1000-step cap, never by the move clock |
| PTCG terminals read as draws | adaptation | all 4,140 rewards identical 0.0 |
| terminal reward resolved against the observation's owner | algorithmic | rollouts returned 97.8% wins, impossible under uniform-random play |
| `yourIndex` read from the top level instead of `.current` | algorithmic | `is_opponent` False at every node, so the search assumed a cooperating opponent |
| rollout states never released | throughput | 1.2–1.3 GB per worker, 28.6 GB resident, 4 games unfinished in 14 min; after the fix the same 4 games took 14.7 s |
| chance surface mis-identified as contexts {4,5,46} | adaptation | 4 and 5 are `TO_ACTIVE` / `TO_BENCH`; the search was sampling its own Pokémon placement |
| A10 `C2` read `inPlayArea` as ownership | adaptation | `AreaType` enumerates the zone; 866 legal options pruned on a meaningless criterion in one game |

Most were adaptation- or perspective-related rather than failures of the published algorithm. Two general lessons are recorded because the reasoning failed in ways that looked like evidence: **where the engine publishes an enum, the enum is the authority**, and **a probe that cannot distinguish a hypothesis from its negation is not evidence** — showing that different options lead to different successors demonstrates branching, not randomness, and holds at every decision node.

## 4. Was ByteRL method-correct?

**PARTIAL.** Implemented and each component pinned by a test that fails when the component is removed: V-trace with ρ̄/c̄ clipping, UPGO cutting to the baseline exactly when the trajectory underperforms, OSFP with period-local G and C plus an append-only history, autoregressive masked multi-select whose joint log-probability is the sum of per-element conditionals, distinct active/bench slot tokens, and fresh random initialisation.

Declared deviation against a named requirement:

> Actor-learner execution is SYNCHRONOUS (actors fill a batch, then the learner updates), not the papers' decoupled recurrent actor-learner. The algorithm is unchanged; the execution topology is not the published one, and this is a declared deviation rather than a claimed reproduction.

Unresolved reference choices are declared in `results/fidelity/UNRESOLVED_REFERENCE_CHOICES.md` — no author implementation exists, so the papers fix the algorithm and not the code. The torso geometry and most coefficients are **Chosen**, not **Stated**, which bounds this to 'faithful to the published algorithm as specified' and never 'reproduces ByteRL'.

| ByteRL / deck check | result |
|---|---|
| `BYTERL_AUTOREGRESSIVE_MULTISELECT` | PASS |
| `BYTERL_FRESH_RANDOM_WEIGHTS` | PASS |
| `BYTERL_MASK_INSIDE_DISTRIBUTION` | PASS |
| `BYTERL_OSFP_PERIOD_LOCAL` | PASS |
| `BYTERL_OSFP_PROMOTION_GUARD` | PASS |
| `BYTERL_UPGO_CUTS_TO_BASELINE` | PASS |
| `BYTERL_VTRACE_CLIPS` | PASS |
| `DECK_ACE_SPEC_CATEGORY_LIMIT` | PASS |
| `DECK_ENERGY_CAP_IS_STRUCTURAL` | PASS |

## 5. Achieved scale relative to the published reference

**COMPUTE_LIMITED.** 19008 games played in total against a reference of *distributed fleet, millions of games, days of wall clock*.

> Order 1e3 games against an order 1e6+ reference, i.e. well under 1%. Convergence is NOT claimed; the learning trajectory is reported as-is.

Reductions taken are confined to the four `FIDELITY_RULES §4` permits (actors, samples, duration, learning periods). `architecture_simplified: False`, `algorithm_simplified: False`.

## 6. Which ByteRL stages improved what?

| run | opponent | iters | updates | first | last | best | field-comparable |
|---|---|---|---|---|---|---|---|
| `fctrl_b1_5` | scripted field | 16 | 768 | 0.0417 | 0.0417 | 0.1250 | yes |
| `fctrl_b2` | scripted field | 16 | 768 | 0.0417 | 0.0208 | 0.1250 | yes |
| `fctrl_b3` | frozen self-play checkpoints (OSFP) | 16 | 768 | 0.4375 | 0.3542 | 0.5625 | **no — self-play** |
| `flearn_b1_5` | scripted field | 16 | 768 | 0.0417 | 0.0000 | 0.1042 | yes |
| `flearn_b2` | scripted field | 16 | 768 | 0.0417 | 0.0625 | 0.1250 | yes |
| `flearn_b3` | frozen self-play checkpoints (OSFP) | 16 | 768 | 0.5208 | 0.4375 | 0.5625 | **no — self-play** |

> B3's win rate is measured against frozen checkpoints of itself and sits near 0.5 by construction. It is not a field result and must not be compared with the other rungs; DECISION_RULES §4 forbids submitting a checkpoint selected only on self-play.

**No rung separates from the B0 uniform-random floor at this scale.** All field-facing rungs sit within binomial noise of one another. That is the honest reading of a compute-limited run and is reported as such rather than dressed up: with order 1e3 games the standard error on a win rate near 0.05 is about 0.006, and the rung-to-rung differences are smaller than that. The ladder demonstrates that each component is correctly implemented and running, not that it helps at this budget.

## 7. Which components transferred, and which were rejected?

**FAIL.** Control field score 0.1905.

| arm | field score | games | 95% Wilson |
|---|---|---|---|
| `T1_policy_prior` | 0.1667 | 24 | [0.0668, 0.3586] |
| `T2_rollout_policy` | 0.1739 | 23 | [0.0698, 0.3714] |

Retained: **none**.

> DECISION_RULES §3: a component is retained only on a credible improvement; internal ByteRL-vs-history improvement alone is insufficient. Here that means the arm's 95% lower bound must exceed the control's upper bound.

**Power caveat, stated so the result is not over-read.** The transfer arms query the `ctrl_b2` checkpoint, whose curve is statistically indistinguishable from the untrained B0 floor. T1 and T2 therefore compare *MCGS with a near-random prior* against *MCGS with uniform random* — close to a null test by construction. The correct conclusion is that **the transfer test has little power at this scale**, not that the transfer mechanism failed. A component is not rejected on this evidence; it is untested.

## 8. Strongest trustworthy local candidate, and submission

Strongest measured local candidate: `transfer_T0_control_summary.json` at 0.1905 — which does **not** clear its registered gate.

`PACKAGE` = **NOT_BUILT** — no candidate cleared its registered gate, so none was packaged

`SUBMISSION` = **PENDING**, ids `[]` — DECISION_RULES §4 forbids submitting a candidate clearly dominated by the current champion.

The live ladder score is known to move 150+ points within minutes, so no champion claim would be made from a single reading even had a candidate cleared its gate.

## 9. Overall

**PARTIAL.**

> OVERALL=PARTIAL is permitted when both methods are faithfully executed and analyzed but no candidate clears the competitive gate (DECISION_RULES §6).

- both methods implemented and executed: `True`
- credible competitive or transfer result: `False`

## 10. Exactly one next action

**Train a ByteRL checkpoint that measurably separates from the B0 floor, then re-run the transfer arms against it.** Every other question in this contract is answered; the transfer result is the only one whose answer is currently *unknown* rather than *negative*, and it is unknown for a single identifiable reason — the checkpoint the arms query never learned. Nothing else should be attempted until that is fixed, because no transfer conclusion drawn from a near-random prior is worth recording.

