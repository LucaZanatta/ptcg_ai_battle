# MCGS hidden-information gap analysis

What the official source does, what the PTCG search API permits, and what c022 therefore implements. `FIDELITY_RULES §3` fixes the priority order:

```text
1. fresh legal hidden-world sample per simulation inside one graph
2. otherwise independent search sessions with fresh legal hidden worlds and
   source-equivalent root-statistic aggregation
3. if neither is possible, MCGS_HIDDEN_INFO=BLOCKED
```

## The three operations the API refuses

Every UNAVAILABLE site below reduces to one of three operations, and all three need the same thing: the ability to modify hidden state at an INTERIOR node of a live search session.

| operation | source sites | why the PTCG API refuses it |
|---|---|---|
| re-determinize an interior game | D1, D2, D3, D4 | `search_begin` requires `observation.search_begin_input`, which only the agent-facing root observation carries; an interior observation has none, and `search_step` carries no randomness at all |
| save and restore an opponent hand | P1, P2, P3 | the API exposes no write path into a search state's hidden zones; hidden contents enter only as `search_begin` arguments |
| attach several concrete games to one node | O1, O2, O3, O4 | a search node IS an engine state id inside one session; there is no object to attach a second state to |

These are re-verified by probe in `results/probes/` rather than inherited from c021's A4 document — the finding is load-bearing for the whole contract, so it is measured again against the engine as shipped today.

## Priority 1 is unavailable, and the reason is narrow

The blocker is **not** "the engine is deterministic". It is that hidden state is bound at `search_begin` and no interior handle exists to rebind it. Priority 1 asks for a fresh world per simulation *inside one graph*; every graph node here is a state id belonging to the one session whose world was fixed when the session opened. Rebinding would mean reconstructing an observation the engine never produced — which would inject states the engine cannot reach and is worse than the disease.

## Priority 2 is available, and the source already specifies it

This is the audit's substantive finding. The archive does not merely permit a K-session ensemble; it **contains one**, complete except for its initialization:

| piece | source | status in archive |
|---|---|---|
| build K distinct hidden worlds | `PerfectInformationMonteCarlo.GenerateDeterminizationsAtOnce` | present, deduplicated by world hash, never called |
| spend the budget across them | `MCGSAgent.GetMove` pimc branch | present, one simulation per randomly-picked determinization |
| pick one per simulation | `MonteCarloGraphSearch.PickDeterminization` | present, uniform over not-in-use |
| aggregate root statistics | `MonteCarloGraphSearch.AggregateDeterminizations` | present and exact |
| carry the ensemble to the next decision | `MonteCarloGraphSearch.CleanUpDeterminizations` | present, replenishes stale worlds |
| ensemble size | `SearchConfig.DeterminizationNumber = 200` | present, read only by `ToString()` |

So c022 does not invent an aggregation rule. It ports one:

```csharp
// MonteCarloGraphSearch.AggregateDeterminizations, src/MCGS.cs
rootEdge.Successor.VisitCount += edge.Successor.VisitCount;   // matched by ActionIndex
rootEdge.Successor.Rewards    += edge.Successor.Rewards;
...
root.VisitCount = root.OutgoingEdges.Sum(p => p.Successor.VisitCount);
root.Rewards    = root.OutgoingEdges.Sum(p => p.Successor.Rewards);
```

Both `MANDATORY_IMPLEMENTATION A3` aggregation rules — visit-count summation and expected-terminal-return summation — are the same two lines of the source, and final selection is the source's unchanged `MaxChild` over `Edge.Value(0)`, i.e. `Rewards/VisitCount` of the summed statistics. The robust lower-confidence variant A3 permits has **no** source counterpart and is therefore run only as an explicitly adapted secondary arm.

## Three ways the port must differ, stated before it is written

1. **Uniform-random world choice per simulation vs. round-robin.** The source picks uniformly at random from the not-in-use set (`PickDeterminization`), which under threads approximates an even split. c022 runs one worker per game, so uniform random sampling of K worlds would give an uneven and unmeasurable split. The port assigns simulations to worlds **deterministically and evenly**, which is what the source's protocol converges to and what `MANDATORY_IMPLEMENTATION A4` requires ("simulations per world = total / K", exactly). Labelled `MECHANICAL_ADAPTER`.
2. **Sessions are not re-rooted across decisions.** The source's `CleanUpDeterminizations` keeps each determinization's subtree alive between decisions. The PTCG API invalidates every searchId at `search_end`, so each decision opens K fresh sessions. What can carry across is the abstraction-keyed statistics table, exactly as c021's `graph_reuse` already does — but it must be carried **per world**, never shared between worlds within a decision, or world independence is destroyed. Labelled `MECHANICAL_ADAPTER`, and enforced by a probe rather than by intent.
3. **The ensemble does not make the port source-identical.** `FIDELITY_RULES §3` is explicit: the K-session ensemble is an approximation, labelled `LEGAL_INFORMATION_ADAPTER`. The source's DEFAULT (non-PIMC) configuration re-determinizes per rollout inside one graph; the ensemble re-determinizes per session. They are not the same algorithm, and the ensemble is the closest legal equivalent, not the original.

## Where the gap bites hardest

`Node.Value` returns ±10 for a proven terminal while rollouts return 1/0, and `Node.Finalise` collapses a parent onto a proven winning edge. Inside a single fixed world both are correct — the world really is won. Across worlds they are the amplifier that turns one lucky determinization into a 96%-confident decision.

This dictates a design decision that must be made **before** any sweep, because making it implicitly in code and discovering it afterwards would be fitting the mechanism to the result. It is recorded in `results/mcgs/PREREGISTERED_AGGREGATION.json`.

## Status

- Priority 1 (per-simulation re-determinization in one graph): **UNAVAILABLE** — 11 source sites depend on interior hidden-state mutation that the API does not expose.
- Priority 2 (independent sessions + source-equivalent root aggregation): **AVAILABLE** — and the aggregation is a port of `AggregateDeterminizations`, not an invention.
- `MCGS_HIDDEN_INFO=BLOCKED` is therefore **not** the outcome; the correction proceeds under priority 2.
