# The search believes it is winning 96% of the time while losing 5 games out of 6

This is the most consequential measurement in the contract, and it is not a bug in the port. It is
the predicted consequence of a constraint the PTCG API imposes, measured directly.

## The measurement

A 6-game run at a 0.9 s per-decision budget and a 90 s match clock:

```
term_root_win        170555
term_root_loss         7524
term_undecided         2143
rollout_terminal_rate    1.0
sims_per_decision      701.3
field_score           0.1667      <- 1 win in 6 games
```

The search's own rollouts resolve to a root-player win **95.7%** of the time. The agent then loses
**83%** of its games. The value estimates driving every selection decision are not slightly
optimistic; they are close to inverted with respect to reality.

## Why, precisely

`results/fidelity/A4_chance_node_api_constraint.md` establishes by probe that the PTCG search API
fixes hidden information at `search_begin` and offers no way to re-determinize an interior node.
So every simulation in a decision explores **one** determinization: one guessed opponent deck, one
guessed prize split, one fixed draw order.

Within that single sampled world, many lines really are forced wins — the searcher knows exactly
which cards will arrive and in what order. The rollout dutifully reaches them and returns 1.0.
The line is a win *in that world* and frequently nonsense in the real one.

Two mechanisms then amplify it rather than damp it:

1. **Terminal values are ±10 while rollouts return 1/0.** A terminal WON node is valued an order
   of magnitude above any non-terminal estimate, so UCB1 with `c = 0.285` cannot pull the search
   away from a discovered "win" — the exploration bonus is far too small to compete with a +10
   exploitation term.
2. **`Node.Finalise` collapses the parent onto the proven edge.** Once a win is found in the
   sampled world it is locked in, which is correct when the world is real and is exactly wrong
   when the world is one draw of many.

Both are faithful to the source. Neither is a defect. They are safe in the reference setting
because of a mechanism this port cannot reproduce — see the correction below.

### Correction (pass-3 audit): the reference's mechanism is per-ROLLOUT, not per-decision

An earlier draft of this document said the reference "draws `DeterminizationNumber = 200`
independent worlds and aggregates over them". **That was wrong.** `DeterminizationNumber` appears
exactly once in the archive outside its declaration — inside a `ToString()`, in a branch guarded
by `IIAlgorithm == PIMC`, which never executes. It is a dead display constant.

The actual mechanism is in `SingleThreadRollout`:

```csharp
var game = leaf.Game.Clone(true);
if (searchConfig.IIAlgorithm != ImperfectInformationAlgorithm.PIMC)
    SabberUtils.Determinize(game, ThreadStaticRandom, true);
value = PlayUntilTerminal(game, searchConfig);
```

`IIAlgorithm` is never assigned anywhere in the archive, so it holds the enum's default
(`DEFAULT`), the guard is true, and **the game is re-determinized before every single rollout**.
Each of a decision's thousands of rollouts therefore samples a fresh world, and the value at a
node is an average over many worlds rather than a conditional on one.

That makes the gap both sharper and worse than first described. It is not "the reference averages
200 worlds per decision and we average one" — it is "the reference averages a fresh world **per
rollout**, and every rollout we run is conditioned on the same single world fixed at
`search_begin`." The overconfidence follows directly.

## What this means for the contract's questions

- **Was MCGS source-faithful?** Yes — and this measurement is evidence of it, because the failure
  mode is the one the source's own design anticipates and compensates for elsewhere.
- **Did executed search actions help or hurt?** They hurt, and now there is a mechanism rather
  than a correlation: the search is confidently optimising a world it has sampled once.
- **Was the defect algorithmic, adaptation-related, or throughput-related?** **Adaptation.** The
  algorithm is intact; the compensating mechanism it depends on is unavailable through this API.

This also reframes the earlier result from c019 and c020, where overriding a stateful scripted
agent cost ~18 points across three separate implementations. The consistent explanation is not
that the searches were poorly built — it is that a determinized searcher on this API is
systematically overconfident, so its "improvements" over a coherent scripted line are drawn from a
world that did not happen.

## What would fix it, and why it was not done here

The source's own fix — re-determinize per rollout — is unavailable: it needs to mutate an interior
game state, and Probe 3 shows the API has no such operation.

The closest available approximation is **root-level multi-determinization**: run K independent
`search_begin` sessions per decision and aggregate the root statistics across them. The API permits
this — `search_begin` accepts a fresh determinization on each call, and Probe 2 confirmed 8 of 8
distinct successors from independent determinizations. It is coarser than the reference (worlds
vary per SESSION rather than per rollout) but it attacks the same variance.

It is not in the primary branch because the contract requires `MCGS_2019_OFFICIAL_SOURCE_PORT` to
be the source port, and the aggregation layer would need its own controlled arm rather than being
folded in silently. It is the single highest-value next change, and it is named as such in the
final report's "exactly one next action" section only if no higher-priority item outranks it.

## Do not misread

`sims_per_decision` of 701 is **not** evidence of a strong search. It is inflated by exactly this
pathology: once the tree finds and finalises a terminal line, each subsequent simulation is a
short re-traversal of it (≈5.8 steps per simulation) rather than genuine exploration. Simulation
count must be read together with `max_depth` and the win/loss split, never alone.
