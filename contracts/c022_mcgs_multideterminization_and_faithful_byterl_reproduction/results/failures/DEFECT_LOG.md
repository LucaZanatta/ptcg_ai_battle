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
