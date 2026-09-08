# c021 defect log

Every defect found during this contract, what it did, how it was caught, and what now prevents its
return. Ordered by how badly it corrupted evidence, not by when it was found.

A defect is only listed as fixed if a check exists that FAILS when the fix is reverted. The
validator (`tools/c021_validate.py`) injects each one and is required to reject it: 18/18 detect.

---

## 1. `yourIndex` read from the wrong level — the search assumed a cooperating opponent

**Class:** algorithmic. **Severity:** invalidates every search result.

`yourIndex` lives on `observation.current`, not at the top level, so
`getattr(obs, "yourIndex", default)` **always** fell through to the default. Consequences:

- `is_opponent` was `False` for **every** node, so `Node.Update`'s sign flip never fired and the
  search maximised the same objective at both players' nodes — it played as if the opponent would
  cooperate.
- The root player was pinned to seat 0, so every seat-1 game was scored from the wrong side.

**Caught by:** an implausible rollout win rate, traced by printing both attribute paths.
**Prevented by:** `MCGS_YOURINDEX_THROUGH_CURRENT`; `test_your_index_reads_through_current_not_the_top_level`.

## 2. Terminal reward resolved against the observation's owner

**Class:** algorithmic. **Severity:** the reward signal was noise.

`visible_view(obs, None)` resolves "my" against the observation's own `yourIndex`, and at a
rollout terminal the owner is whoever is to act — not the root player. Rollouts returned **2142
wins against 48 losses (97.8%)**, which uniform-random play cannot produce. The winner is now
resolved to a player index and compared to the root; the split became 2193/2707 (44.8%).

**Prevented by:** `_winner_index`; the same validator check family.

## 3. Chance surface mis-identified as contexts {4, 5, 46}

**Class:** adaptation. **Severity:** the search sampled its own decisions.

Contexts 4 and 5 are `SelectContext.TO_ACTIVE` and `TO_BENCH` — ordinary choices about where to
put a Pokémon. Marking them random made the search **sample** its board development instead of
optimising it. The correct surface is `COIN_HEAD = 46` alone.

**Two bad arguments put them there, both of which looked like evidence:**

1. a set-difference between a `manual_coin` walk and a normal walk — confounded, because once a
   coin resolves differently the trajectories diverge;
2. a "direct check" that stepped every option from one state and found distinct successors — which
   is true of **every** decision node. It measured branching, not randomness.

**Lesson recorded:** where the engine publishes an enum, the enum is the authority; and a probe
that cannot distinguish a hypothesis from its negation is not evidence.

## 4. Rollout states never released

**Class:** throughput. **Severity:** made measurement impossible.

`_track` was called on every rollout step and nothing was released until the decision ended. At
~120 simulations per decision against a 1000-step rollout cap that pinned tens of thousands of
live engine states: workers measured **1.2–1.3 GB each, 28.6 GB resident, 1 GB system memory
free**, and four games did not finish in fourteen minutes. After releasing each state as the
rollout steps past it, the same four games took **14.7 seconds**.

## 5. `BackupUCD` omitted the `Finalise` block

**Class:** algorithmic. **Severity:** dead code in the executed configuration.

The source repeats the same terminal/`Finalise` block in `BackupEdges` and `BackupUCD`. The port
carried it only in `BackupEdges` — and UCD is the **active** strategy, so the lethal-sequence
collapse never ran at all.

**Prevented by:** `MCGS_FINALISE_RUNS_UNDER_UCD`.

## 6. A10 `C2` read `inPlayArea` as ownership

**Class:** adaptation. **Severity:** pruned legal moves on a meaningless criterion.

`api.AreaType` enumerates the **zone** — DECK, HAND, DISCARD, ACTIVE, BENCH, PRIZE — and carries no
ownership. The filter pruned **866 legal options in a single game**. It now uses `playerIndex` for
the owner and `SelectContext` for the valence, and fires only where the engine documents the
valence.

## 7. ACE SPEC limit missing from deck construction

**Class:** adaptation. **Severity:** every generated deck was rejected.

The engine returned `INVALID` for 100% of sampled decks while accepting the reference deck.
Isolating one rule at a time: 1 ACE SPEC → DONE, 2 distinct → INVALID, 2 copies of one → INVALID.
The limit is on the **category**, not per card, and 0 of 20 sampled decks satisfied it. B0 went
from 0/12 completed games to 12/12.

**Prevented by:** `DECK_ACE_SPEC_CATEGORY_LIMIT`.

## 8. Energy cap decided by a name substring

**Class:** algorithmic. **Severity:** admitted illegal decks.

`"energy" in name.lower()` classified *Energy Retrieval* — a Trainer, `cardType` 1 — as uncapped
basic energy, so twenty copies read as legal. Replaced with the structural `cardType == 5` test.

This is the **same defect shape** as the c020 A8 end-turn veto, which substring-matched words
against a tuple of integers. Second occurrence in two contracts.

**Prevented by:** `DECK_ENERGY_CAP_IS_STRUCTURAL`.

## 9. B3 had no self-play

**Class:** method. **Severity:** would have been a false BYTERL_METHOD claim.

`osfp.sample_opponent()` was never called and `osfp.checkpoints` was never loaded into an opponent
— every rung played the same four scripted teachers while the manifest would have recorded
`osfp: true`. Compounding it, `min_games=len(done)` made the promotion guard `len(done) >=
len(done)`, always true, disabling the sample-size condition its own test enforced.

## 10. Behaviour log-probability could describe a different action than the one played

**Class:** algorithmic. **Severity:** biased every V-trace ratio when it fired.

If the option-index filter dropped an element, the recorded behaviour log-probability still
described the unfiltered set, so V-trace would divide by the wrong behaviour probability. Now
recomputed for the set actually played, and the drop is recorded.

## 11. The policy always took the maximum allowed count

**Class:** algorithmic. **Severity:** an entire class of decisions unavailable.

`sample_select` looped to `k_max` unconditionally, so with `minCount < maxCount` the policy could
never learn to discard two cards instead of three. The count is now itself a sampled decision.

## 12. Control arm reported a false legality metric

**Class:** reporting. **Severity:** would have published a wrong number.

`_UniformActor` never evaluated legality when handed a fixed deck, so the control arm reported
`legal_deck_rate 0.0` while all 64 of its games completed.

## 13. In-place mask writes broke multi-select gradients

**Class:** algorithmic. `picked` feeds the option-summary term in `battle_logits`, so its backward
pass needs the tensor it saw; the in-place write bumped the version counter and autograd refused
the earlier step's gradient.

## 14. Measurement contention

**Class:** throughput / methodology. Covered in
`results/hardware/environment_throughput.json` and the project memory. Orphaned pool workers were
measured stealing seven cores at 99% CPU each, and two `pgrep`-gated background scripts raced so a
latency-bounded run executed concurrently with training. All measurement runs now execute from one
sequential driver.

---

## The test that was validating the bug

Worth repeating from c020 because it is the reason every check here is injection-tested: c020's
end-turn veto test **passed while the veto never fired**, because the test used a string action
key and the real one is a tuple of integers. A check that cannot fail proves nothing. The
validator classifies any check that passes clean *and* passes injected as `INERT`, and counts it
as a failure.
