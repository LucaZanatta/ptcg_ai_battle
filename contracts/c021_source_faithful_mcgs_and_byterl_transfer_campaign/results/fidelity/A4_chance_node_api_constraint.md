# A4 — chance nodes: what the PTCG search API does and does not permit

Status: **measured, not assumed.** Every claim below is backed by a probe that was run, and the
probe scripts and their raw output are listed at the end.

## Why this document exists

`MANDATORY_IMPLEMENTATION A4` requires chance nodes with `CheckRandom` marking, damped sampling
and sample merging. My first port created none (`chance_nodes_created: 0`, `chance_samples: 0`) and
I recorded that as an outstanding defect. Before implementing it I probed the engine to find out
what a "new sample from a chance node" actually means here. The answer changes which branch of the
source is the faithful one, so it is recorded before any code is written.

## The source's mechanism

`Node.Expand` on a chance node calls `PrepareChanceNode()`, which draws a fresh outcome by
**mutating the game object in place**:

```csharp
case RandomActionType.DRAW:            Game.CurrentPlayer.DeckZone.Shuffle();          break;
case RandomActionType.ENDTURN:         if (!IsDeterminized) SabberUtils.Determinize(Game, _rnd);
                                       else Game.CurrentOpponent.DeckZone.Shuffle();   break;
case RandomActionType.ENDTURN_OPPONENT:Game.CurrentOpponent.DeckZone.Shuffle();        break;
case RandomActionType.TRACKING:        Game.CurrentPlayer.DeckZone.Shuffle();          break;
```

Every one of these re-randomizes hidden information **at an interior node**, mid-tree. That is the
operation a chance node samples over.

## Probe 1 — the engine is deterministic given a search session

Stepping the *same* action from the *same* state repeatedly, 12 times each, across 4 captured
decision points and the first 3 options of each:

```
capture0 opt0 otype=1  -> 1 distinct successors out of 12 : [12]
capture0 opt1 otype=2  -> 1 distinct successors out of 12 : [12]
capture1 opt0 otype=8  -> 1 distinct successors out of 12 : [12]
...
capture3 opt1 otype=14 -> 1 distinct successors out of 12 : [12]
```

**10/10 probes returned exactly one distinct successor.** `search_step` carries no randomness. The
deck order, the prizes and the opponent's hand are fixed when `search_begin` is called and never
re-rolled.

## Probe 2 — the randomness lives at `search_begin`, and only there

Re-calling `search_begin` with a fresh determinization and stepping the same action:

```
re-begin w/ fresh determinization -> 8 distinct of 8: [1, 1, 1, 1, 1, 1, 1, 1]
```

All 8 differ. So hidden information *is* the source of stochasticity, and it is sampled exactly
once per search session.

## Probe 3 — interior states cannot be re-determinized

```
root     obs.search_begin_input is None: False
interior obs.search_begin_input is None: True
```

`search_begin` raises `ValueError("Not agent observation.")` without `search_begin_input`, and only
the observation handed to the agent function carries it. **There is no API by which an interior
node can be re-determinized or its deck reshuffled.**

## What this means

The source's DRAW / ENDTURN / ENDTURN_OPPONENT / TRACKING chance types all reduce to "reshuffle
hidden information at an interior node". That operation is unavailable. Within one search session
a draw is deterministic, so a chance node of those types would have exactly one reachable
successor: sampling over it is degenerate, and `SampleWidth = 24` samples would return 24 copies
of one state.

This is not a gap between the source and the port. **It is the source's own `PIMC` regime**, and
the source handles it explicitly. `CheckRandom` opens with:

```csharp
if (NodeConfig.PIMC)
{
    if (child.IsRandomHappened)
    {
        CreateChanceNode(selectedAction, actionIndex, child.ActionAbstraction,
            RandomActionType.RANDOMEFFECT, ref child);
        return;
    }
    return;
}
```

Under PIMC the source creates chance nodes for **`IsRandomHappened` only** — genuine random
effects — and creates none for draws or end-turns, for precisely the reason above: the deck is
already determinized, so a draw is not a chance event.

### But `PIMC` is NOT flipped, and must not be

It is tempting to conclude "the engine implements PIMC, so set `NodeConfig.PIMC = true`". That
would be wrong, and `c021_mcgs_graph.py` keeps `PIMC = False` with `test_pimc_stays_false`
asserting it. The flag is not a local branch selector for `CheckRandom`; the source gates at
least four unrelated behaviours on the same field:

| Site | Behaviour under PIMC |
|---|---|
| `Node.Update` | `if (IsEndTurn && PIMC) reward *= -1` — an extra sign flip on top of the opponent flip |
| `Node.Finalise` | disabled entirely |
| `Node.Expand`, END_TURN block | the determinize / `ENDTURN_OPPONENT` path is `!PIMC` only |
| `PrepareChanceNode`, RANDOMEFFECT | the `RandomOpponentHand` determinize is `!PIMC` only |

Flipping the flag to justify one chance-node decision would silently change three other things,
including double-flipping the reward sign on every end-turn backup.

The honest statement is narrower, and neither branch ports cleanly:

> The port is the **`!PIMC` configuration minus the interior-determinization operations the API
> does not expose**, with chance nodes at the random surfaces the API *does* expose. The `!PIMC`
> end-turn path is also unavailable — both of its halves require either an interior determinize
> or an opponent information-set restore. The PIMC branch of `CheckRandom` is cited as evidence
> that the source itself treats "no interior re-determinization" as a coherent regime, not as the
> configuration being run.

## Probe 4 — genuine random effects ARE exposed, via `manual_coin`

`api.search_begin(..., manual_coin=True)` — "If True, the coin's heads or tails can be chosen."
Walking a session with and without it, from the same root and the same RNG seed:

```
contexts WITHOUT manual_coin: [-1, 1, 2, 3, 7, 8, 21, 22, 26, 30, 38, 41, 43]
contexts WITH    manual_coin: [-1, 1, 2, 3, 4, 5, 7, 8, 21, 22, 26, 30, 38, 41, 43, 46]
CONTEXTS ONLY WITH manual_coin: [4, 5, 46]
   ctx 46 -> 2 options, option_types (1, 2), minCount 1, maxCount 1
```

### Corrected: the chance surface is context 46 ONLY, and the enum settles it

I first marked contexts **4, 5 and 46** as chance surfaces. That was wrong, and the way the
reasoning failed is worth recording because both arguments looked like evidence.

**Bad argument 1 — the set-difference above.** It is confounded. Once a coin resolves differently
the two walks diverge, so contexts that exist in *both* configurations appear as "only with
manual_coin".

**Bad argument 2 — the "direct check".** I then stepped every option from one identical state and
found several distinct successors for contexts 4, 5 and 46, and treated that as confirmation.
It confirms nothing: **every decision node has distinct successors per option.** The check
measured branching, not randomness, and could never have separated a chance node from an ordinary
choice.

The engine's own enum settles it in one line:

```python
api.SelectContext.COIN_HEAD = 46   # "YesNo. Do you want to choose heads?"
api.SelectContext.TO_ACTIVE = 4    # "Select the Pokemon to put into your Active Spot."
api.SelectContext.TO_BENCH  = 5    # "Select the Pokemon to put onto your Bench."
```

Contexts 4 and 5 are ordinary player decisions. Marking them random made the search **sample its
own Pokemon placement instead of optimising it** — it discarded the decision at exactly the nodes
where board development is decided.

`MANUAL_COIN_CONTEXTS` is therefore `{46}`, defined as `COIN_HEAD_CONTEXT` against the enum rather
than inferred from behaviour. The lesson generalises: where the engine publishes an enum, the enum
is the authority, and a behavioural probe that cannot distinguish the hypothesis from its negation
is not evidence.

This is the engine's own representation of `IsRandomHappened`: the random effect stops being
resolved silently inside the step and becomes a node whose outcomes the searcher enumerates. That
is exactly a chance node, and it is what A4 is implemented against.

## The resulting implementation

1. `search_begin(..., manual_coin=True)` in the MCGS agent, so random effects surface as nodes.
2. A successor landing in context 46 (`COIN_HEAD`) is `IsRandomHappened`; the node is marked
   `is_random` with `random_action_type = "RANDOMEFFECT"`, which is the only type the API can
   support.
3. The chance node's outcomes are the coin options. It is expanded by damped sampling
   (`SampleWidth = 24`, `DampingParameter = 2.0`, `numSampleTraversed`), selected by
   `SampleChild` weighted-random on `SampleCount` rather than by UCB, and merged through
   `TranspositionCheck`'s chance-node path — all as already implemented in
   `c021_mcgs_graph.py`.
4. Root hidden-information sampling stays where the API puts it: at `search_begin`, which is also
   where the source's `DeterminizationNumber` operates.

## Registered adapter

| Field | Value |
|---|---|
| Kind | `MECHANICAL_ADAPTER` (forced by the target API, not a simplification) |
| Source behaviour | interior `DeckZone.Shuffle()` / `SabberUtils.Determinize` in `PrepareChanceNode` |
| Port behaviour | root-only determinization; interior chance nodes for manual-coin random effects |
| Forced by | no `search_begin_input` on interior observations (Probe 3) |
| Source branch used | `NodeConfig.PIMC == true` branch of `CheckRandom` — the source's own handling |
| Alternative rejected | fabricating interior outcomes by re-rooting a new session from a reconstructed observation: the reconstruction is not the engine's state and would inject states the engine never produces |

## What must NOT be claimed

The port does not sample draw order inside the tree. Any statement that MCGS here "searches over
hidden card draws below the root" is false. It searches one determinization per session, with
chance nodes at genuine random effects. Aggregate hidden-information coverage comes from repeated
sessions, not from within one.

## Counters that keep this honest

| Counter | Meaning | Required |
|---|---|---|
| `manual_coin_node_ucb_selected` | a chance context reached the UCB branch | **exactly 0** |
| `chance_nodes_created` | chance nodes marked | > 0 under `manual_coin` |
| `chance_ctx_46` | per-context breakdown, kept so a stray context would show | — |
| `chance_expansions` | samples drawn from chance nodes | > 0 |

`test_the_ucb_guard_fires_if_a_coin_context_is_left_unmarked` injects the defect and asserts the
counter catches it, so a zero reading means the guard works rather than that it is inert.

## Reproduce

- `probes/probe_chance.py` — Probe 1
- `probes/probe_chance2.py` — Probes 2 and 3
- `probes/probe_coin.py` — Probe 4, walk-diff (confounded, kept for provenance)
- `probes/probe_coin_direct.py` — Probe 4, direct both-options check (the one relied on)
