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

The PTCG API determinizes once per session and forbids interior re-determinization. That makes
PIMC the branch the engine actually implements, and the faithful port is the PIMC branch of
`CheckRandom`, not the non-PIMC branch.

## Probe 4 — genuine random effects ARE exposed, via `manual_coin`

`api.search_begin(..., manual_coin=True)` — "If True, the coin's heads or tails can be chosen."
Walking a session with and without it, from the same root and the same RNG seed:

```
contexts WITHOUT manual_coin: [-1, 1, 2, 3, 7, 8, 21, 22, 26, 30, 38, 41, 43]
contexts WITH    manual_coin: [-1, 1, 2, 3, 4, 5, 7, 8, 21, 22, 26, 30, 38, 41, 43, 46]
CONTEXTS ONLY WITH manual_coin: [4, 5, 46]
   ctx 46 -> 2 options, option_types (1, 2), minCount 1, maxCount 1
```

Context 46 is a two-outcome, exactly-one-choice select that exists only under `manual_coin` — a
coin flip surfaced as an explicit selectable node. Contexts 4 and 5 also appeared; they are
confirmed separately in `A4_chance_context_confirmation.md` rather than assumed here.

This is the engine's own representation of `IsRandomHappened`: the random effect stops being
resolved silently inside the step and becomes a node whose outcomes the searcher enumerates. That
is exactly a chance node, and it is what A4 is implemented against.

## The resulting implementation

1. `search_begin(..., manual_coin=True)` in the MCGS agent, so random effects surface as nodes.
2. `check_random()` ports the **PIMC branch**: a successor landing in a manual-coin context is
   `IsRandomHappened`, and a `RANDOMEFFECT` chance node is created for it.
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

## Reproduce

- `probe_chance.py` — Probe 1
- `probe_chance2.py` — Probes 2 and 3
- `probe_coin.py` — Probe 4

All three are archived under `results/fidelity/probes/`.
