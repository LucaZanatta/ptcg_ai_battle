# c022 defect log

Every defect found in c022's own code, with how it was found and what it would have done to the
evidence if it had shipped. Defects inherited from c021 are in
`results/references/c021_audit_reconciliation.md`; this file is about mistakes made *here*.

The pattern worth noting across all of them: none produced an error, a crash, or an obviously
wrong number. Each produced a plausible number computed on the wrong thing.

---

## D01 — the leakage guard rejected public information

**Found by** probe M03 failing on my own `WorldHandle.summary()`.

The guard flagged any dict key named after a hidden zone. `summary()` reports the zone SIZES,
which are public — a PTCG player can see the opponent's deck count — and they are the evidence
that a sampled world is legally sized.

**If it had shipped:** the sizes would have been pushed out of every trace to prevent a
disclosure that cannot occur, removing the evidence for `MANDATORY_IMPLEMENTATION A2`'s "hidden
hand/deck/prize completion is legal".

**Fix:** the guard draws the line at card IDENTITY, not at names. A hidden-field key carrying a
scalar passes; carrying a collection does not. The real guarantee is static: no c022 module
outside `c022_mcgs_worlds.py` may read `WorldHandle.zones`, checked by the probe.

---

## D02 — worlds could be legal, multiplicity-correct, and a different game

**Found by** an advisor observation that the world probes only exercised opening positions,
where every world has `opponent_hand: 0` and `opponent_prize: 0`.

Nothing verified that a sampled world had the same PUBLIC zone sizes as the real game. A world
handing the opponent an empty hand passes every legality and multiplicity check and makes the
opponent trivially weak inside the search.

**Fix:** `check_zone_sizes` compares the sampled sizes against `VisibleObservation.counts()`, and
a world that fails is not admitted to the ensemble. Probes now capture mid-game decisions.

---

## D03 — the ±10 terminal-scale story was wrong

**Found by** reading the frozen K1 control's raw counters instead of c021's prose.

I had written that `Node.Value`'s ±10 terminal scale and `Node.Finalise`'s parent collapse were
the amplifier turning one lucky determinization into a confident decision. The control records
`finalised: 0`, `terminal_leaves: 0`, `lethal_bonus: 0` over 226,277 rollouts. The tree policy
never reached a terminal, so neither mechanism ever executed.

**If it had shipped:** a preregistration built around a scale-mixing decision that does not
arise, and a plausible-sounding causal story with no support in the data.

**Fix:** the claim is retracted in the gap analysis. Per-world terminal counters are kept so that
if a larger K budget ever does reach a terminal, the mixed scale surfaces as a flag rather than
as a distorted calibration plot.

---

## D04 — `predicted_win_probability` recorded −0.0446

**Found by** reading a single calibration row from a superseded arm.

`Node.Update` applies `if (IsOpponent) reward *= -1`. The flip is correct and load-bearing for
SELECTION — MaxChild on the signed scale still prefers the child best for the root player — but
it makes the value of an action that ENDS THE TURN negative. My preregistration asserted "the
aggregate value is already a probability".

**If it had shipped:** every end-turn decision would have scored as a catastrophic Brier miss for
a reason with nothing to do with the search, and M08 would have blamed K for it.

**Fix:** the aggregate tracks whether each action's successor is an opponent node; the
probability negates and clamps accordingly; the raw signed value is recorded alongside so the
conversion is auditable. `opponent_flag_conflicts` counts the case where worlds disagree about
the flag, which is impossible on public information and would mean action indices are misaligned.

---

## D05 — the B06 recurrence check compared `h0` against `h0`

**Found by** it passing.

The first version compared the learner's stored start state against the same stored start state.
Identically zero, and it would have passed under a zeroed start, a shifted unroll boundary, or an
encoder that disagreed between actor and learner.

**Fix:** compare the learner's RECOMPUTED end-of-unroll `(h, c)` against the state the actor
actually held, and the recomputed joint log-probability against the stored behaviour value.

---

## D06 — the publish race mislabelled every unroll's policy version

**Found by** the fixed D05 check failing at 1.07 while the same replay run in-process gave
exactly 0.0.

`publish()` wrote `shared["blob"]` and `shared["version"]` as two separate Manager writes. An
actor reading between them got version N's number with version N+1's weights, so every unroll it
produced was LABELLED N while generated under N+1.

**If it had shipped:** the importance ratio π/μ is computed against the behaviour
log-probability, so the mislabelling silently biases every off-policy correction. No loss curve
would show it.

**Fix:** version and blob are published as one atomic key and read as one value. After the fix:
138 exact-weights checks, 0 failures, max recurrence delta 0.0, max joint log-probability delta
0.0.

---

## D07 — `_start_states` was a shared class attribute

**Found by** inspection while fixing D05.

Every `EpisodeRunner` in a process would have appended to one list, so episode 2's unroll starts
would have been appended to episode 1's and every unroll after the first episode would have
replayed from the wrong state.

---

## D08 — a per-game wall clock would have made "K=8 is worse" unfalsifiable

**Found by** an advisor observation about `fpw_k8`'s per-decision cost.

Under `fixed_per_world` a K=8 decision costs eight times a K=1 decision, so a fixed per-game wall
clock cuts the K=8 arm eight times earlier in DECISION space. Abandoned games are excluded from
the field score, so the K=8 survivors would have been systematically shorter games.

**If it had shipped:** "K=8 is worse" and "K=8 dropped its long games" would have been
indistinguishable — the same shape as c021's contention artifact, where the counts looked right
and the attribution was wrong.

**Fix:** a per-game DECISION BUDGET identical across K. The wall clock is derived from the arm's
own per-decision cost and is a backstop, not the cut.

---

## D09 — arm re-runs were not reproducible

The agent seed was `a.seed + len(results) + len(running)`, both of which depend on completion
TIMING. Worlds were safe (they come from `world_base_seed`) but the out-of-budget fallback and
every agent-side tie-break were not — enough to break M13's matched seeds and F03's requirement
that reported numbers recompute from raw data. Now `a.seed + job_index`.

---

## D10 — the agent invalidated its own long games, and they left the field score uncounted

**Found by** an advisor observation that the first arm's buckets did not sum: `games: 60`,
`completed: 46`, `abandoned: 4`, and 10 games in no category at all.

The unscored games ran a NORMAL duration — 168 s mean against 164 s for completed games, while
abandoned games sat at exactly the 1200 s guard — so they were not timeouts. Recording terminal
statuses showed `["INVALID", "DONE"]`.

The out-of-budget fallback returned a SINGLE option always. A PTCG select carries
`minCount..maxCount`, and the engine rejects a payload naming fewer than `minCount` options, so
the environment marked the agent INVALID.

**If it had shipped:** this is worse than losing those games. The field score is computed over
completed games, so an agent that invalidates its own games looks BETTER than it is — the games
it ruins are disproportionately the long ones it was losing slowly. Every arm's headline number
would have been computed on a population its own defect had selected.

**Fix:** `_fallback_payload` names between `minCount` and `maxCount` distinct options, clamped to
what is on offer, still preferring END_TURN when a single pick is legal. UNSCORED became a
first-class category with a terminal-status histogram and an `all_games_accounted` assertion, and
the field score carries bounds computed as if every excluded game were a win or a loss.

**Before/after, same configuration:** 1 unscored (`INVALID|DONE`) with 7 budget-exhausted
decisions → 0 unscored, 8/8 completed.

**But this was only half of it — see D13.**

---

## D11 — a terminated game could be counted twice

**Found by** inspection while fixing D10.

A game whose process was killed on the wall-clock guard produced an abandoned marker, and the
child may already have queued a real result. Both were appended, so `games_accounted` could
exceed `games` and an abandoned marker could shadow a genuine score. Deduplicated by `game_id`,
preferring the real result, with the collapse count reported.

---

## D12 — a stale arm from a killed sweep survived as evidence

**Found by** the relaunched sweep's log being corrupted mid-word.

`pkill -f c022_sweep.sh` killed the driver script but not the arm it had already spawned. The
orphan ran to completion, wrote a full set of result files into the live results directory, and
wrote into the relaunched sweep's log through its inherited file descriptor.

**Fix:** the files are quarantined in `results/failures/superseded/` with a `WHY_SUPERSEDED.md`
naming the specific evidence that they predate the fix — their `config` block has no
`decision_budget` field. They are cited nowhere as a c022 result. A result that vanishes cannot
be audited; one that stays in place becomes evidence.

---

## D13 — the SEARCHED path emitted a single option too

**Found by** the m04 arm still reporting `unscored: 10, unscored_status_histogram:
{"INVALID|DONE": 10}` after D10 was fixed — with `decision_budget_exhausted_decisions: 0`.

That zero is the whole diagnosis. The out-of-budget fallback had not fired once, so the invalid
actions were coming from the path that *had* searched. `chosen = K.to_select_payload([opts[action]],
sel)` names exactly one option, and a select with `minCount > 1` rejects it.

The two defects are indistinguishable in every aggregate counter — same INVALID games, same
missing scores, same `completed` deficit. Only the terminal-status histogram plus the
budget-exhaustion count separates them, and both had to be added (D10) before the second could be
seen at all. Fixing D10 and stopping there would have left 10 of 60 games still invalid while the
counter that used to reveal them read zero.

**Why it exists:** the graph search ranks single action indices, because
`MonteCarloGraphSearch` has one `PlayerTask` per edge. A PTCG select with `minCount > 1` is a SET.
The source has no counterpart for this, so it is a `SEMANTIC_GAME_ADAPTER`.

**Fix:** `_payload_for` takes the top `minCount` action indices by the aggregate value the search
already computed, with the chosen action first, padding with unexpanded options only if the search
expanded fewer than `minCount`. Any other completion — random, or the first `minCount` options —
would discard the search's opinion about every element after the first, which is exactly the
c019/c020 defect of scoring a k-element select as a single pick.

`multiselect_decisions` and `obliged_decisions` are now counted, so the path is visible in every
arm rather than only when it breaks.

**Verified:** 12 games, 11 completed, 1 abandoned, **0 unscored**, `all_games_accounted: true`,
`multiselect_decisions: 1`, `obliged_decisions: 1`.

---

## D14 — "equal total simulations" is not equal compute, and the guard assumed it was

**Found by** the exclusion-spread bound I had pre-committed to two hours earlier being breached
by the second arm of the sweep.

`ft_k1` abandoned 2 of 40 (5.0%); `ft_k2` abandoned 6 of 40 (15.0%). A 10-point spread against
an 8-point bound.

The cause is a fact about the algorithm, not about the machine:

```text
ft_k1   192 simulations/decision   122.4 ms per simulation per worker
ft_k2   192 simulations/decision   164.0 ms per simulation per worker
```

**At an identical simulation budget, K=2 costs 34% more.** Opening K sessions per decision — each
with its own `search_begin`, world sample, root construction, transposition table and teardown —
is a real per-decision cost that grows with K and is completely invisible to a simulation count.

So `MANDATORY_IMPLEMENTATION A4`'s fixed-total protocol equalises SIMULATIONS but not COMPUTE.
That is worth stating in its own right: the protocol isolates world diversity from search
quantity exactly as intended, and it does not isolate it from wall-clock cost.

**If it had shipped:** the per-game wall guard was derived from a K-independent cost, so it
under-provisioned every high-K arm, cut more of their long games, and — because excluded games
leave the field score — scored them on a shorter population. This is defect D08 returning through
a third door. D08 was the wall clock cutting arms unequally by K; the contention finding was load
doing it; this is the algorithm's own per-K overhead doing it.

**Fix:** the guard is now `decision_budget × total_sims × sec_per_sim × (1 + 0.34·(K−1)) × 2.0`,
with the 0.34 measured from the two arms above rather than assumed. Every arm records its
`effective_seconds_per_simulation` and `derived_game_timeout_s`, so the correction is auditable
rather than buried in a shell variable.

**What I did with the two completed arms:** quarantined to
`results/failures/superseded/ft_k_guard_not_k_aware/`. They are not cited as results. Discarding
1.6 hours of finished compute for a bound I set myself is the whole point of setting it before
the data existed — the alternative was to notice the spread, observe that it was "only" 10 points,
and keep going.

**Sweep parameters were also reduced** (40→32 games, 192→128 simulations for fixed-total,
48→16 per world for fixed-per-world) so the K-aware guard does not push the high-K arms past
feasible wall clock. The sweep is explicitly a SHORTLIST; its primary output — the M08 calibration
comparison — is computed per DECISION, so 32 games still yields roughly 1,280 calibration rows per
arm. Field-score confidence intervals at 32 games are wide and are reported as such;
`TRAINING_AND_EVALUATION §5`'s 200-game paired arms remain the evidence for any field-score claim.

---

## D15 — abandonment is the stalemate rate, and the guard was sized as if it were slowness

**Found by** looking at the per-game durations behind an abandonment number instead of the
number itself.

`ft_k1` at a 1881.6 s guard:

```text
completed  29 games   mean 148.7 s   MAX 275.0 s
abandoned   3 games   1881.9 s, 1881.9 s, 1881.8 s
```

The abandoned games did not take slightly too long. They ran to the guard **to a tenth of a
second**, and the slowest game that ever finished took 275 s — a seventh of the guard. There is
no continuum between them: normal games finish in under five minutes and a small number of games
do not terminate at all.

So `abandoned` is not measuring "games too slow for the budget". It is measuring the **stalemate
rate**, which is a property of the game under this play, not of the search configuration.

**Two consequences, and I had the second one backwards.**

1. **The confound is milder than I feared.** A stalemate rate is K-independent to first order, so
   the exclusion spread across K should be small — unlike a cost-driven cut, which scales with K
   and was the D14 confound. This is good news that only appears if you look at the durations.

2. **The guard IS the arm's wall time.** An arm cannot finish until its stalemates time out, so
   sizing the guard to the search budget bought nothing except a longer arm. Three
   non-terminating games held `ft_k1` open for 1882 s while its other 29 finished inside 275 s.
   Every previous recalibration in this contract (D14, and the two before it) was tuning a
   quantity that only ever affected the *stalemates* — which is why lowering the decision budget
   from 120 to 50 barely moved the arm's duration.

**Fix:** `--game-timeout-base`, derived from measured completed-game duration and scaled by the
same K factor, replaces the search-cost derivation. 700 s at K=1 is 2.5× the slowest completed
game and cuts nothing real; the K=8 guard becomes 2359 s instead of 6360 s. Each summary records
`game_timeout_basis` so a reader can tell which derivation produced it.

**Expected effect:** arm wall time roughly a third of what it was, with abandonment unchanged —
because the games being abandoned were never going to finish.

---

## D16 — whose turn follows an action is not always public, so the cross-world sum was adding
opposite signs

**Found by** the validator's V08 check firing: `ft_k2` reported **21 opponent-flag conflicts**,
in 10 of 64 traced decisions.

I had written that this was impossible. The comment in `c022_mcgs_multidet.py` read: "Public
information decides whose turn follows an action, so this cannot differ across worlds. If it ever
does, the action indices are not aligned." **That claim is false**, and the traces show why: the
option signature MATCHED in every conflicting decision, so the indices were perfectly aligned.
The successor genuinely differed.

In PTCG an action's resolution can depend on hidden information — a card that reveals, draws,
or searches can end the turn in one sampled world and not in another. So the successor's player
is a function of the hidden state, not only of the action.

**Why it matters.** `Node.Update` stores `-reward` at an opponent node. So for the same action
index, a world whose successor is the agent's own turn contributes `+p`, and a world whose
successor is the opponent's contributes `-q`. The source's `AggregateDeterminizations` sums raw
`Rewards`, which is a root-frame sum **only because Hearthstone's successor player is determined
by the action alone**. Here it is not, and summing raw rewards adds quantities in opposite frames.

Concretely, two worlds each scoring the root player 0.6 and 0.8 for one action summed to
`(6.0 − 8.0)/20 = −0.10` — a number that is not a return in any frame — instead of
`(6.0 + 8.0)/20 = 0.70`.

**Fix:** `root_frame_rewards()` converts each world's contribution to the root player's frame
before summing, and `predicted_win_probability` reads that. `SEMANTIC_GAME_ADAPTER`: the
operation reduces exactly to the source's raw sum whenever the flags agree, which is always the
case in Hearthstone.

The source's SIGNED value — the quantity `MaxChild` selects on — is reconstructed from the
root-frame sum using the MODAL flag, so at K=1, where no disagreement is possible, it is
bit-for-bit the c021 control's value and probe M04's identity is preserved.

`opponent_flag_conflicts` is kept as a counter rather than removed: it no longer indicates
misalignment, but a sudden rise still would, and it quantifies how often the adapter is doing
real work (10 of 64 decisions, ~16%).

**The general lesson, which is the third time this contract has produced it:** a comment
asserting that something cannot happen is a hypothesis. This one was written into the code as
justification for a counter, and the counter then refuted it.

---

## D17 — the B1.5 rung was a no-op: its flag was declared, asserted, and read by nothing

**Found by** `ctrl_BR1_5` producing no manifest while the other four rungs did, and its
evaluation reporting `checkpoint_loaded: false` — i.e. the number recorded against "BR1.5" was
fresh random weights.

Chasing that turned up the larger defect. `random_initial_construction` appeared in exactly two
places in the whole repository:

```text
tools/c022_byterl_train.py:56   "BR1_5": {... "random_initial_construction": True ...}
tools/c022_byterl_train.py:66   ("BR1", "BR1_5"): {"random_initial_construction"}
```

The stage table and the stage-delta table. **No implementation read it.** So `BR1` and `BR1_5`
were the same system, and `MANDATORY_IMPLEMENTATION B7`'s "adjacent stages may differ only by the
published change" was satisfied vacuously — they differed by nothing.

**Why the existing test did not catch it.** `test_b14_adjacent_stages_differ_only_by_the_
published_change` compares the two dictionaries and asserts the changed key set equals
`{"random_initial_construction"}`. It passed. It was asserting a property of a *table*, not of
the *system* the table claims to describe — an inert test in the precise sense this contract keeps
finding.

**Fix, three parts:**

1. `random_initial_construction` is implemented: the first `RANDOM_INITIAL_CONSTRUCTION_STEPS`
   (10) construction choices are drawn uniformly from the legal mask instead of from the policy.
   `SEMANTIC_GAME_ADAPTER` — the exact Hearthstone schedule has no literal PTCG equivalent and
   the step count is a CHOSEN value recorded in `UNRESOLVED_REFERENCE_CHOICES.md`.
2. **The behaviour log-probability on a randomised step is the UNIFORM one**, not the network's.
   This is the whole correctness content: V-trace's ratio is `pi(a|s)/mu(a|s)` and `mu` is
   whatever actually chose the action. Recording the network's log-probability while sampling
   uniformly would corrupt every importance ratio on those steps, and no loss curve would show it.
3. Two new tests. One greps every stage flag and fails if any is read by no implementation file —
   which would have caught this on the day the flag was written. The other runs two
   `EpisodeRunner`s differing only in the flag and asserts the randomised one makes exactly 10
   uniform choices whose recorded behaviour log-probability equals `-log(n_legal)`, and that the
   un-randomised one does not.

**What happened to the affected results.** The four controlled-rung manifests are copied to
`results/failures/superseded/ctrl_rungs_br15_noop/` and the rung comparison is re-run. BR0, BR1,
BR2 and BR3 were each internally valid, but the ladder they belong to had a missing rung and a
mislabelled one, so the comparison as a whole is not reportable.

## D18 — the pre-b2 rungs measure machine load, and BR0 ran under an MCGS arm

**Found** 2026-07-30 19:20, comparing `ctrl_BR0` against `ctrl_BR1` in `byterl_ctrl2.log`.

`ctrl_BR0` was launched at 18:41 while the 200-game `paired_k8` MCGS arm was still running at
`nproc 14`. `paired_k8` finished at 18:56. `ctrl_BR1` began at 19:10 on a quiet machine. The two
rungs differ **only by gamma** (0.99 -> 1.0).

| at equal consumed decisions | `ctrl_BR0` | `ctrl_BR1` |
|---|---:|---:|
| learner updates/s @ 5k | 1.24 | 11.24 |
| learner updates/s @ 20k | 1.73 | 11.66 |
| learner updates/s @ 24k | 2.01 | 11.57 |
| learner updates/s @ 80k | **4.60** | **11.38** |
| steps per update | 13.5 | 13.5 |
| decisions per episode | 84 | 84 |
| production/consumption | 41.9 -> 12.1 | 7.5 (flat) |
| queue age (s) @ 24k | 841.6 | 114.9 |
| policy lag @ 24k | 95.5 | 85.7 |

`steps/update` and `decisions/episode` are identical, so the batches and the episodes are the
same shape. The entire difference is the **learner's update rate**, and it *ramps monotonically*
— 1.24, 1.73, 2.01, 4.60 — as the competing MCGS arm drains away. Gamma cannot do that. Nothing
in the BR0 -> BR1 delta can.

**What is contaminated.** `ctrl_BR0`'s `production_consumption_ratio`, `queue_age_s` and
`policy_lag` are load measurements, not stage measurements. And because the learner consumed data
that was on average seven times staler, the *policy it learned* is contaminated too — so
`ctrl_BR0`'s external evaluation cannot be compared with the rungs above it. `conf_BR0` shares the
defect: it ran at 15:43 under the K sweep, and its ratio of 12.06 agrees with `ctrl_BR0`'s 12.07
because both were contended, not because 12.06 is a property of BR0.

**Fix.** `ctrl_BR0` is re-run alone. `results/EXECUTION_BUDGET.md`'s concurrency column is
amended: it said items 8–11 run concurrently with 2–5, which is measurably wrong for the
**pre-b2** rungs.

**The finding underneath the defect, which is worth more than the fix.** With an unbounded queue
the production/consumption ratio is not a property of the algorithm at all — it is the ratio of
two throughputs, and it moved from 41.9 to 12.1 *within a single run* as unrelated load left the
machine. The bounded blocking FIFO pins it at 1.02 under every load tested, because actors block
when the queue is full. That is a stronger argument for the b2 change than the ladder was designed
to make: b2 does not merely reduce staleness, it makes the system's behaviour reproducible at all.

**Why it was not caught earlier.** The contention experiment in `hardware/contention_tests.json`
measured what load does to *MCGS* field scores and correctly concluded that latency-bounded MCGS
arms must run alone. It did not ask the mirrored question — what an MCGS arm does to a
*latency-sensitive ByteRL rung* — and the concurrency plan was written on the assumption that
decision-budgeted training is contention-tolerant. It is, for BR2 and BR3. It is not for BR0,
BR1 and BR1.5, whose entire subject matter is an unbounded queue's throughput imbalance.

## D19 — the B06 replay check compared the learner against mu, and D17's fix made mu uniform

**Found** 2026-07-30 19:28. `ctrl_BR1_5` died on its first fidelity check, 37 seconds in:

```text
RuntimeError: B06 recurrent replay mismatch:
  {'recurrence_delta': 0.0, 'logp_delta': 0.00685429573059082, 'policy_version': 0, 'steps': 32}
  (tolerance 0.0001)
```

`recurrence_delta` is exactly 0.0 — the recurrence replays perfectly — and only the
log-probability disagrees. That shape is the whole diagnosis.

**The conflation.** Two different quantities had been one:

| | what it is | who needs it |
|---|---|---|
| `mu` | the log-probability of the distribution that **actually chose** the action | V-trace, UPGO, PPO: the ratio is `pi/mu` |
| `pi` | the acting **network's** score for that same action | the B06 replay check: does the learner rescore it identically at identical weights? |

Before D17 they were always equal, because the network always chose. D17 implemented B1.5 and
made the first ten construction choices uniform, correctly recording `mu = -log(n_legal)` — and
the B06 check then asked the network to reproduce a uniform draw. It cannot, and should not.

So the check was **correct code failing on correct code**, because it was asserting a property
that had been true incidentally rather than the property it was written to assert. Every rung
from BR1.5 upward was affected: `random_initial_construction` is cumulative, so BR2 and BR3
carry it too and would have died the same way.

**Fix.** `Step` carries `policy_logp` (pi) and `uniform_behaviour` alongside `behaviour_logp`
(mu); `_pack` carries both across the queue — omitting them there would have silently restored
the old comparison through the fallback; the check compares replay against pi.

**And the check is strictly stronger afterwards, not weaker.** Comparing against pi removes the
old implicit guarantee that mu was the network's value, so mu is now verified directly from
stored data by `behaviour_consistency`: a uniform step must carry `-log(n_legal)` for the mask it
drew against, and every other step must carry exactly pi. Both run on every fidelity check, and
`behaviour_delta` joins the strict-mode failure condition and the manifest.

**Why nothing caught it.** There was no test for B06 at all — it existed only inside a training
run. `tests/test_c022_byterl_b06.py` now covers it, with an injection per failure mode: a
corrupted pi, a step that lies about being uniform, a uniform step carrying the wrong uniform,
and a shifted recurrent start.

**A vacuous injection, caught while writing those tests.** The shifted-recurrent-start injection
zeroed `pack["h0"]` on unroll **0** — whose `h0` is legitimately zeros, since an episode starts
from a zero state. The corruption changed nothing, `recurrence_delta` stayed 0.0, and the test
reported a green check for an injection that was never made. It now corrupts a mid-episode
unroll and asserts `h0` is non-zero first, and a companion test asserts that every unroll after
the first carries a non-zero stored start — the property B06 exists to protect, which the
vacuous version was silently failing to check.

**What happened to the affected results.** The entire rung ladder, `conf_*` and `ctrl_*`, is
quarantined in `results/failures/superseded/ladder_pre_d19/` and re-run from one commit. The
clean re-run immediately confirmed D18 as well: `ctrl_BR0` alone runs at 142 consumed
decisions/s with a production/consumption ratio of 7.79, against 16.7/s and 12.06 under
contention — so 12.06 was never a property of BR0.

## D20 — B06 ran ONCE in a fourteen-minute run, and reported PASS

**Found** 2026-07-30 19:50, reading the first clean `ctrl_BR0` manifest:

```json
"recurrence_checks": 1,
"recurrence_check_failures": 0,
"policy_versions": 556
```

One check. The run published 556 policy versions and executed the B06 exact-weights fidelity
check exactly once, then reported it as a pass.

**Why.** The check needs the weights an unroll was produced under, so it looks for an unroll in
the current batch whose `policy_version` is still in the published-blob history. That history kept
`keep = 8` versions. The pre-b2 rungs have an unbounded queue and a policy lag of tens of
versions, so by the time an unroll reached the learner its weights had been evicted, `cand` was
`None`, and the check was skipped — **silently**, with no counter and no line in the manifest.

**The part that makes this more than a tuning miss.** The failure is worst exactly where the check
matters most. A pre-b2 rung's entire subject is an unbounded queue's staleness; the rungs with the
largest lag are precisely the rungs whose replay fidelity went unverified. And `MANDATORY_
IMPLEMENTATION B3` requires recomputing recurrent outputs "during learner replay and assert
agreement before optimization" — a requirement met once in 556 versions is not met.

**Fix.**

1. `keep` is now `--blob-history`, default **48**. At 6.9 MB per blob that is 329 MB, which the
   machine has, and it covers the lag these rungs reach.
2. `recurrence_checks_skipped_no_retained_blob` and `recurrence_check_coverage` are recorded.
   The count alone cannot distinguish "verified throughout" from "the weights had already been
   evicted every time we looked", and a manifest that cannot express the difference will be read
   as the flattering one.
3. `tools/c022_byterl_ladder.py` reports a rung with zero checks as `NO_DATA`, never as a pass,
   and flags a BR1.5+ rung whose checks never saw a uniform construction step — because such a
   rung has not exercised the D19 case at all, however green it looks.

**Cost, and why it was paid.** The ladder had already produced a clean BR0 under `keep = 8`. It
was discarded and the ladder restarted, because `MANDATORY_IMPLEMENTATION B7` requires ONE
codebase to produce the stages and a ladder assembled from two versions of the fidelity check is
not that. Fifteen minutes to convert a near-vacuous probe into real evidence.

**The pattern this is the fourth instance of.** D13, D17, D19 and now D20 are all the same shape:
a check that ran, reported success, and verified nothing — an inert test, a no-op flag, a
category error, and now a check starved of the data it needed. The manifests looked identical in
every case.

## D21 — the validator's inventory omitted the arms the contract turns on

**Found** 2026-07-30 20:25, while extending `tools/c022_validate.py`.

`load_context` built its MCGS inventory from three directories: the fixed-total sweep, the
fixed-per-world sweep, and the M04 identity arm. Not `paired/`. Not `transfer/noise_floor/`. Not
`kaggle_deploy/` or `unrestricted_reference/`.

So every check in the file — field scores recomputing from raw per-game records, game accounting,
budget delivery, probabilities in range, action-index alignment — **silently skipped the 200-game
paired arms**, which are the contract's decisive MCGS evidence and the ones `MCGS_HIDDEN_INFO`
rests on. The validator reported `13/13 PASS` while validating the shortlist and not the result.

This is the inverse of the inert-check family. There, a check ran and asserted nothing; here, the
checks were sound and were never pointed at the data that mattered. Both produce the same
artifact: a green report that means less than it says.

**Fix.** The inventory now includes `paired`, `noise_floor`, `kaggle_deploy` and
`unrestricted_reference`, so all nineteen checks cover them. Adding them immediately turned up a
second problem.

### D21b — and then V08 failed on correct behaviour

With the paired arms in scope, `V08` failed on seven arms. Its condition was:

```python
if s.get("signature_mismatches"):        bad.append(...)
if s.get("opponent_flag_conflicts"):     bad.append(...)   # <- wrong
```

Those are not the same thing. A **signature mismatch** means two worlds disagreed about the
option list, so summing their statistics by action index sums different actions — a real defect,
and it is 0 everywhere. An **opponent-flag conflict** is D16: whose turn follows an action is not
always public, so two worlds can legitimately disagree about whether an action's successor is an
opponent node. The fix was root-frame summation, which converts each world's reward into the root
player's frame before summing. `paired_k8` records 1,001 such conflicts and handles every one.

Failing on it made the validator report FAIL for correct behaviour on every K>1 arm. That is
worse than a missing check: **a validator that cries wolf is how a real FAIL gets scrolled past.**

V08 now asserts signature mismatches only. The handled-ness of the conflicts is asserted where it
can actually be tested — `V06` checks the observable consequence (no probability outside [0,1],
which is what an unconverted opponent-frame value produces), and a new **V19** asserts that
conflicts appear only where two worlds exist, since one world cannot disagree with itself and a
K=1 arm reporting one would mean the counter measures something other than its name.

**State after the fix:** 19 checks, 17 ran, 17 pass, 0 inert, 0 undetected injections, 2 NO_DATA
(`V14` and `V17`, awaiting the rung ladder and the timed arms) — and `NO_DATA` is still not a pass.

## D22 — I contaminated my own quiet window, one hour after establishing that it exists

**Found** 2026-07-30 20:36, comparing the two clean rungs' learner rates.

| rung | consumed dec/s | prod/cons | wall clock |
|---|---:|---:|---:|
| `ctrl_BR0` | 91.1 | 8.73 | 1318 s |
| `ctrl_BR1` | 115.1 | 8.22 | 1042 s |

They differ only by gamma, which cannot change learner throughput — the same reasoning that made
D18 conclusive. A 26% rate difference needs an explanation, and the explanation is me: during
BR0's and BR1's training windows I ran the full 695-test suite (~65 s of multi-core work), the
validator, the status tool and the numerical fixtures. D18 established that the pre-b2 rungs must
run alone, and then I ran my own tooling on top of them.

**Why this is recorded rather than fixed by a third re-run.**

The effect is 26% in learner rate against D18's 9x, and — this is the part that decides it —
**it changes no reported conclusion.** The ladder's output is adjacent-rung effects on external
win rate at 128 evaluation games, where a Wilson interval spans roughly 8 points. BR0 scores
0.0531 and BR1 0.0558, both indistinguishable from the 0.0625 random floor. Every adjacent pair
will read "no resolvable effect at 128 games" whatever the learner rate was, so a third restart
would buy a cleaner provenance for a conclusion that does not move.

What it does change is what may be CLAIMED. The ladder report states the measured per-rung rates
and this contamination alongside them, and does not claim the rungs ran in isolation. `V14`
still applies its `[0.6, 1.7] x median` bound, which both rungs pass — the bound was set for
D18's 9x, and it correctly does not fire on 1.26x.

**The rule this makes explicit, since "run it alone" evidently was not enough:** during a pre-b2
rung, the only permitted foreground work is editing files. No test suite, no validator, no
analysis tool, no `git add` over a 295 MB checkpoint tree. Writing is free; running is not.
