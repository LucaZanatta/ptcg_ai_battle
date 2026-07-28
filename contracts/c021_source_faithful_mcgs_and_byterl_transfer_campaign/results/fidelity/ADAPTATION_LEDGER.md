# Adaptation ledger

Every place where the ported code departs from the reference, with the kind of departure, what
forced it, and what would be needed to remove it.

`FIDELITY_RULES` distinguishes two kinds:

* **MECHANICAL_ADAPTER** — forced by the target API or by hardware. The algorithm is unchanged.
* **SEMANTIC_ADAPTER** — a Hearthstone concept re-expressed in PTCG terms. The structure is
  preserved; what fills it is different.

A third column, **SIMPLIFICATION**, is present so its emptiness is a claim rather than an
omission: `FIDELITY_RULES §3/§4` forbid simplifying the architecture or the algorithm, and nothing
in this campaign does.

---

## MCGS — `MCGS_2019_OFFICIAL_SOURCE_PORT`

| # | Site | Kind | Reference behaviour | Port behaviour | Forced by | Removable if… |
|---|---|---|---|---|---|---|
| M1 | `PrepareChanceNode` DRAW / ENDTURN / TRACKING | MECHANICAL | reshuffles or re-determinizes the game **at an interior node** | no interior chance types; chance nodes only at genuine random effects | interior observations carry no `search_begin_input`, so no interior state can be re-determinized (Probe 3) | the API exposes interior re-determinization |
| M2 | chance surface | SEMANTIC | `IsRandomHappened` on a mutable game | `SelectContext.COIN_HEAD = 46` under `search_begin(manual_coin=True)` | PTCG resolves randomness inside the step unless `manual_coin` is set | — |
| M3 | `StateAbstraction` fields | SEMANTIC | minion board, hero, hand, deck | active + bench slots, prizes, deck counts, hand | different game | — |
| M4 | `ActionAbstraction` | SEMANTIC | `PlayerTask` type/source/target | `option_type`, area/index, `inPlayArea`/`inPlayIndex`, card and attack ids | different game | — |
| M5 | rollout terminal | SEMANTIC | `PlayState.WON` | PTCG win conditions in rule order: prizes, then deck-out; resolved to a player index and compared to the root | different game | — |
| M6 | empty option list | SEMANTIC | a null select signals the end | the engine signals a finished game with a select carrying an EMPTY option list | engine convention | — |
| M7 | move clock | MECHANICAL | 15 s first move, 10 s continuing | 1.5 s / 1.2 s | the PTCG cumulative match clock; the source's budget would exhaust it | more wall-clock budget |
| M8 | `max_simulations_per_decision` | MECHANICAL | unbounded | optional ceiling, 0 = unbounded, every activation counted | so a measurement run terminates | — |
| M9 | rollout state lifetime | MECHANICAL | `ReleaseGameResources` frees the game at a node | each rollout state released as the rollout steps past it | measured at 1.2–1.3 GB per worker and 28.6 GB resident otherwise | — |
| M10 | multi-select payload | MECHANICAL | actions are single `PlayerTask`s | one option, padded to `minCount` | PTCG selects carry `minCount..maxCount` | corrected in A10/C1 |

**Not adapted, deliberately reproduced:**

* `UCDParams(1, 0)` leaves `RecursiveUpdate` inert — reproduced, not "fixed" (`FIDELITY_RULES §5`).
* `NodeConfig.PIMC` stays `False`, even though root-only determinization resembles the PIMC
  regime, because the same flag gates a reward sign flip, `Node.Finalise` and the END_TURN
  expansion path.
* Values are stored in the mover's frame while `BestChild` argmaxes without negating, so the
  end-turn successor is ranked by the negation of its value to the root player. This is the
  source's own convention and is asserted by a test rather than corrected.

---

## MCGS — `MCGS_2019_PTCG_LEGAL_CORRECTED` (A10, separately named)

| # | Correction | Kind | Why the port needs it |
|---|---|---|---|
| C1 | multi-select actions are SETS | corrects M10 | deterministic padding meant the search explored 10 of 45 legal pairs at a `minCount = 2` node over 10 options: the action space searched was not the one played |
| C2 | category filter on target owner | SEMANTIC port of `Filters.CategoryBasedFilter` | Hearthstone card-ID sets do not transfer; PTCG names the valence in `SelectContext` and the owner in `playerIndex`. Fires only for DAMAGE / DAMAGE_COUNTER / HEAL / REMOVE_DAMAGE_COUNTER |
| C3 | obliged actions collapse | port of tree-phase pruning | no simulations spent proving the only legal move is the only legal move |
| — | `MAX_COMBINATIONS = 24` | MECHANICAL | C(n, k) is unbounded; every cap activation is counted in `legal_combination_capped` |

---

## ByteRL

| # | Site | Kind | Reference | Implementation | Forced by |
|---|---|---|---|---|---|
| B1 | actor–learner topology | **declared deviation, not an adapter** | decoupled recurrent actor–learner | synchronous: actors fill a batch, then the learner updates | implementation scope. This is why `BYTERL_METHOD = PARTIAL` |
| B2 | action space | SEMANTIC | LOCM's fixed action set | variable PTCG option sets, scored bilinearly | different game |
| B3 | multi-select | SEMANTIC | absent in LOCM | autoregressive joint log-probability over the running mask | PTCG `minCount..maxCount` |
| B4 | draft stage | SEMANTIC | 30 picks from offered triples | 60 open picks from a 52-card pool under a per-prefix legal mask | different game; a materially larger, less guided space |
| B5 | slot tokens | SEMANTIC | no counterpart | distinct active / bench-index / side embeddings | PTCG board structure |
| B6 | scale | MECHANICAL | distributed fleet, millions of games, days | 6–10 local actors, order 1e3 games, tens of minutes | hardware. `FIDELITY_RULES §4` permits exactly actors, samples, duration and periods |
| B7 | set-size choice | **Chosen** | no counterpart | how many elements to take is sampled uniformly over `minCount..maxCount` | the papers give no distribution; see `UNRESOLVED_REFERENCE_CHOICES` |

---

## SIMPLIFICATIONS

**None.** No architectural element of either method was removed, narrowed or replaced:

* MCGS keeps UCB1 with no prior term, edge statistics, the transposition DAG, dummy edges, damped
  sampling and the inert UCD recursion.
* ByteRL keeps V-trace with clipping, UPGO with baseline cutting, OSFP with period-local
  bookkeeping and immutable history, autoregressive masked multi-select, separate value heads and
  fresh random initialisation.

Each of these is pinned by a check in `tools/c021_validate.py` that injects its removal and is
required to reject it (17/17 detect).
