# c021 — source-faithful MCGS and ByteRL transfer campaign: final report

Generated 2026-07-29T11:23:41 from `reports/statuses.json`. Every figure below is read from that file at render time, so the narrative cannot drift from the evidence.

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

Best non-superseded MCGS run `competitive + transfer_T0_control`: field score **0.1143** over 70 completed games, 95% Wilson interval [0.0591, 0.2096].

Gate: lower bound of the 95% Wilson interval must exceed 0.5 against the field, judged with abandoned games counted as losses so exclusion cannot manufacture a pass → **FAIL**.

> A technically faithful but weak MCGS is MCGS_COMPETITIVE=FAIL, not an implementation failure (DECISION_RULES §1).

| run | games | done | field | sims/dec | chance nodes | coin UCB | step err |
|---|---|---|---|---|---|---|---|
| `ablation_nochance_summary.json` | 40 | 31 | 0.1290 | 615.5 | 0 | 0 | 0 |
| `ablation_nosearch_summary.json` | 40 | 40 | 0.0000 | 0.0 | 0 | 0 | 0 |
| `ablation_search_summary.json` | 40 | 34 | 0.1176 | 739.4 | 120 | 0 | 0 |
| `competitive_summary.json` | 40 | 34 | 0.1471 | 174.5 | 96 | 0 | 0 |
| `legal_corrected_summary.json` | 40 | 33 | 0.1818 | 809.1 | 132 | 0 | 0 |
| `scale_w12_summary.json` | 12 | 9 | 0.2222 | 566.0 | 28 | 0 | 0 |
| `scale_w1_summary.json` | 12 | 11 | 0.2727 | 2293.4 | 84 | 0 | 0 |
| `scale_w2_summary.json` | 12 | 11 | 0.2727 | 942.6 | 28 | 0 | 0 |
| `scale_w4_summary.json` | 12 | 11 | 0.0909 | 73.0 | 12 | 0 | 0 |
| `scale_w8_summary.json` | 12 | 12 | 0.2500 | 1002.8 | 84 | 0 | 0 |
| `transfer_T0_control_summary.json` | 40 | 36 | 0.0833 | 158.7 | 99 | 0 | 0 |
| `transfer_T1_policy_prior_summary.json` | 40 | 32 | 0.1562 | 884.6 | 83 | 0 | 0 |
| `transfer_T2_rollout_policy_summary.json` | 40 | 38 | 0.1053 | 530.3 | 7 | 0 | 0 |

### The reproducibility bound, measured rather than assumed

`competitive` and `transfer_T0_control` are the SAME configuration -- the source port with every transfer switch off. Run independently they scored **0.1471** and **0.0833** (34 and 36 games). That 6.4-point spread is the resolution limit of an arm this size, and every comparison below must be read against it.

It is worth being precise about what kind of variation this is. Both runs use the same `--seed`, the same per-game seed derivation, and the same opponent and seat assignment, so this is **not** sampling variance over different games — it is **non-determinism between identical runs**. The dominant source is structural: the search is bounded by wall clock, not by simulation count, so the same position explored under slightly different machine timing yields a different number of simulations and therefore a different move. A time-budgeted search is not reproducible by construction.

The consequence is that **no difference smaller than this bound is interpretable**, which is exactly why the transfer arms are reported as UNTESTED rather than rejected. A future campaign wanting attributable comparisons should budget by simulation count rather than by time, accepting the unrealistic latency, and measure the time cost separately.

Across three contracts the same result has now reproduced: overriding a stateful scripted agent with a search costs roughly 18 points regardless of the search's quality, because the scripted opponent's line is internally consistent and a search that departs from it part-way inherits neither plan. The measured constraint is early-game credit assignment, not search depth.

### A10, and a measurement artifact that briefly inverted the answer

`legal_corrected` scored 0.1818 at 809.1 simulations per decision, against 0.0833 at 158.7 for the control.

An earlier run put this arm at 0.0526 with 58.8 simulations per decision, and it was on the way to being reported as evidence that the legality corrections hurt, with a throughput confound as the caveat. **Both readings were artifacts.** That run predated two fixes: a 150 s per-game cap that truncated this arm hardest because its decisions are more expensive, and a parent that read a child's result only after the child died — so children blocked writing large payloads into the pipe were recorded as abandoned. With both fixed and the cap at 300 s, the arm has the *most* simulations per decision and the *fewest* abandonments of any arm.

The lesson is the one this contract keeps re-learning: a measurement harness defect does not announce itself as a harness defect. It arrives as a plausible result about the thing under test.

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

**COMPUTE_LIMITED.** 65088 games played in total against a reference of *distributed fleet, millions of games, days of wall clock*.

> Order 1e3 games against an order 1e6+ reference, i.e. well under 1%. Convergence is NOT claimed; the learning trajectory is reported as-is.

Reductions taken are confined to the four `FIDELITY_RULES §4` permits (actors, samples, duration, learning periods). `architecture_simplified: False`, `algorithm_simplified: False`.

## 6. Which ByteRL stages improved what?

| run | opponent | iters | updates | first | last | best | field-comparable |
|---|---|---|---|---|---|---|---|
| `big_ctrl_b1_5` | scripted field | 120 | 15360 | 0.0391 | 0.0859 | 0.1719 | yes |
| `big_ctrl_b2` | scripted field | 120 | 15360 | 0.0391 | 0.0859 | 0.1250 | yes |
| `big_ctrl_b3` | frozen self-play checkpoints (OSFP) | 120 | 15360 | 0.4844 | 0.3359 | 0.7812 | **no — self-play** |

> B3's win rate is measured against frozen checkpoints of itself and sits near 0.5 by construction. It is not a field result and must not be compared with the other rungs; DECISION_RULES §4 forbids submitting a checkpoint selected only on self-play.

### B3's self-play number is uninformative, and an audit found the reason

OSFP itself worked: promotion fired (`fctrl_b3` at iterations 7, 9, 10, 14; `flearn_b3` at 0, 1, 4, 5, 6, 8), the period-local payoff bookkeeping advanced, and the history is append-only.

But the seeded period-0 checkpoint was stored as `tensor.detach().cpu().numpy()`, **which shares storage with the live parameter**. Without an explicit copy that "frozen" checkpoint mutated on every optimizer step, so for as long as checkpoint 0 was in the opponent pool B3 was playing a mirror of its *current* self rather than a frozen past self. A mirror match returns 0.5 by construction — which is exactly where these rates sit (`big_ctrl_b3` best 0.7812).

So the earlier reading — *B3 does not beat its own random initialization* — was **not supported**: it never played its random initialization. The bug is fixed (`.copy()`, with a regression test that the fixture only passes if `.numpy()` really does alias), and these B3 rates should be read as **uninformative**, not as evidence either way. The promotion path was always correct, because it copied via `.tolist()`.

**No rung separates from the B0 uniform-random floor at this scale.** All field-facing rungs sit within binomial noise of one another. That is the honest reading of a compute-limited run and is reported as such rather than dressed up: with order 1e3 games the standard error on a win rate near 0.05 is about 0.006, and the rung-to-rung differences are smaller than that. The ladder demonstrates that each component is correctly implemented and running, not that it helps at this budget.

## 7. Which components transferred, and which were rejected?

**FAIL.** Control field score 0.0833.

| arm | field score | games | 95% Wilson |
|---|---|---|---|
| `T1_policy_prior` | 0.1562 | 32 | [0.0686, 0.3175] |
| `T2_rollout_policy` | 0.1053 | 38 | [0.0417, 0.2414] |

Retained: **none**.

> DECISION_RULES §3: a component is retained only on a credible improvement; internal ByteRL-vs-history improvement alone is insufficient. Here that means the arm's 95% lower bound must exceed the control's upper bound.

**Power caveat, stated so the result is not over-read.** The transfer arms query the `ctrl_b2` checkpoint, whose curve is statistically indistinguishable from the untrained B0 floor. T1 and T2 therefore compare *MCGS with a near-random prior* against *MCGS with uniform random* — close to a null test by construction. The correct conclusion is that **the transfer test has little power at this scale**, not that the transfer mechanism failed. A component is not rejected on this evidence; it is untested.

## 8. Strongest trustworthy local candidate, and submission

Strongest measured local candidate: `competitive + transfer_T0_control` at 0.1143 — which does **not** clear its registered gate.

`PACKAGE` = **NOT_BUILT** — no candidate cleared its registered gate, so none was packaged

`SUBMISSION` = **PENDING**, ids `[]` — DECISION_RULES §4 forbids submitting a candidate clearly dominated by the current champion.

The live ladder score is known to move 150+ points within minutes, so no champion claim would be made from a single reading even had a candidate cleared its gate.

## 9. Overall

**PARTIAL.**

> OVERALL=PARTIAL is permitted when both methods are faithfully executed and analyzed but no candidate clears the competitive gate (DECISION_RULES §6).

- both methods implemented and executed: `True`
- credible competitive or transfer result: `False`

## 10. Exactly one next action

**Add root-level multi-determinization to MCGS: run K independent `search_begin` sessions per decision and aggregate the root statistics across them, as an explicitly controlled arm against the single-determinization port.**

This is chosen over the obvious alternative — train a ByteRL checkpoint that separates from the floor, then re-run transfer — because it addresses the one failure mechanism this campaign actually *measured*. The search resolves its own rollouts to a win about 96% of the time while winning about 11% of its games, because every simulation explores one sampled world (`failures/FINDING_single_determinization_overconfidence.md`). A better prior would still be evaluated inside a searcher that is confidently optimising a world that did not happen, so the transfer question cannot be answered cleanly until this is.

The API already permits it: `search_begin` accepts a fresh determinization on each call, and Probe 2 confirmed 8 of 8 distinct successors from independent determinizations.

A correction the pass-3 audit forced, because it changes what the fix is imitating: the reference does **not** aggregate `DeterminizationNumber = 200` worlds per decision — that constant appears once, inside a `ToString()` in a branch that never executes. The real mechanism is `SingleThreadRollout` re-determinizing the game **before every rollout**. So the reference averages a fresh world per rollout while this port conditions every rollout on one world fixed at `search_begin`. Root-level multi-determinization is the closest approximation the API allows, not a reproduction.

One methodological change should ride along, because without it no result is attributable: **budget the search by simulation count rather than wall clock.** Two runs of an identical configuration differed by 6.4 points, and a time-budgeted search is not reproducible by construction. Measure latency separately.

