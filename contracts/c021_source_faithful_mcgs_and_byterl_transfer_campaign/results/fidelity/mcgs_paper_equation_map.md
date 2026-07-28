# MCGS formula map — read from the official 2019 source, not inferred

Archive `2019_UCDP_MCGS.zip`, SHA-256 `f00a54f310a8f868deb59964c17e71357d67ecfcedba01c0245053dcc5aa920a`,
retrieved 2026-07-28T20:39:02Z. 33 files, 7,261 lines.

Every formula below is transcribed from the source file named beside it. Where the source differs
from what a reader might assume from the paper, that is called out — `FIDELITY_RULES §5` requires
reproducing source behaviour including apparent defects.

## 1. Node value — `src/Node.cs::Node.Value(double c)`

```
if IsTerminal:
    x = +10  if PlayState == WON
        -10  if PlayState == LOST
          0  otherwise
else:
    x = Rewards / VisitCount

if c == 0: return x
return x + c * sqrt(2 * ln(Parent.VisitCount) / VisitCount)
```

**This is UCB1, not PUCT.** There is no prior term and no `P` factor. `c020` used
`Q + c·P·√N/(1+n)`; substituting that here is explicitly forbidden by `FIDELITY_RULES §3`.

Terminal states are valued at ±10 while rollouts return 1.0/0.0 — a deliberate order-of-magnitude
asymmetry that makes a proven terminal dominate any averaged estimate.

## 2. Edge value — `src/Edge.cs::Edge.Value(double c)`

```
x = Successor.Value(0)
if c == 0: return x
if SelectionStrategy == UCD:
    bonus = c * sqrt(2 * ln(Predecessor.TotalVisit) / VisitCount)
else:
    bonus = c * sqrt(2 * ln(Predecessor.VisitCount) / VisitCount)
return x + bonus
```

**The single modification that makes this "modified UCD":** the exploration term divides by
`TotalVisit` rather than `VisitCount`. `TotalVisit` is incremented both by ordinary backup and by
`RecursiveUpdate`, so in a DAG a node reachable by many paths accumulates a larger log-numerator
than its own traversal count.

## 3. Recursive incoming-edge update — `src/Algorithms/UCD.cs`, `src/Edge.cs::RecursiveUpdate`

```
Node.UCDUpdate(reward, d1, d2):
    Update(reward); TotalVisit++
    if IncomingEdges.Count > 1:
        for edge in IncomingEdges:
            if edge is LastTraversedEdge or edge.IsDummy: continue
            edge.RecursiveUpdate(reward, d1, d2)

Edge.RecursiveUpdate(reward, d1, d2):
    if IsDummy: return
    f1 = (d1 > 1);  f2 = (d2 > 0)
    if not f1 and not f2: return
    p = Predecessor
    if f1: p.Update(reward)
    if f2: VisitCount++; p.TotalVisit++
    for e in p.IncomingEdges: e.RecursiveUpdate(reward, d1-1, d2-1)
```

**Fidelity finding worth stating loudly.** `NodeConfig.UCDParams` defaults to `UCDParams(1, 0)`.
With `d1 = 1`, `f1 = (1 > 1) = false`. With `d2 = 0`, `f2 = (0 > 0) = false`. The very first
branch therefore returns immediately, and **the recursive incoming-edge update performs no work in
the shipped default configuration**.

The mechanism exists, is reachable, and is disabled as configured. The reference port must
reproduce that: implement the recursion exactly, register `(d1, d2) = (1, 0)`, and record that it
is inert at the default — not quietly enable it because it "looks intended". A registered
sensitivity test at other `(d1, d2)` belongs in the corrected branch.

## 4. Node update — `src/Node.cs::Node.Update(double reward)`

```
if IsOpponent:            reward *= -1
if IsEndTurn and PIMC:    reward *= -1
VisitCount += 1
Rewards += reward
```

Perspective is handled by sign-flipping at opponent nodes during backup, not by evaluating from a
fixed seat. `PIMC` is `false` in the shipped config, so the second flip is inactive.

## 5. Chance nodes, sparse and damped sampling — `src/Node.cs`, `src/Algorithms/DampedSamping.cs`

```
BestChild:
    if IsRandom:
        SampleChild(...)                       # weighted random over outgoing edges
        if OutgoingEdges.Count > 5: chanceNodeTraversed++
    else:
        bestEdge = argmax over OutgoingEdges of Edge.Value(c)    # StoreVisitsAtEdges = true

SampleChild:
    sampleEdge = weighted_random(OutgoingEdges, weight = edge.SampleCount)

DampedSampling = true
DampingParameter = 2
SampleWidth = 24
```

Chance outcomes are sampled proportionally to how often that outcome has already been drawn
(`SampleCount`), which concentrates sampling on outcomes the search has actually seen. The count
`5` is the sparse-sampling threshold that limits how many chance nodes one tree-policy descent may
traverse.

## 6. Backup — `src/MCGS.cs::Backup`

```
if node.IsTerminal and node.PlayState == WON and node.Game.Turn == node.StartTurn:
    reward *= 10                     # lethal-this-turn bonus
dispatch: BackupUCD | BackupEdges | plain,  by SelectionStrategy and StoreVisitsAtEdges
BackupEdges walks LastTraversedEdge upward, incrementing edge VisitCount at each step
```

## 7. Rollout — `src/MCGS.cs::SingleThreadRollout` / `PlayUntilTerminal`

```
repeat up to 5 times while value < 0:
    game = leaf.Game.Clone(true)
    if IIAlgorithm != PIMC: Determinize(game, random, true)
    value = PlayUntilTerminal(game, config)

PlayUntilTerminal:
    if step count > 1000: return -1          # abort sentinel, triggers retry
    if (turn+1)/2 == 45:   return 0.0        # draw-ish cap
    if state == COMPLETE:  return 1.0 if our player WON else 0.0
    policy.Play(game)                         # UniformRandomRollout
```

**The default policy is uniform random.** `FIDELITY_RULES §3` forbids substituting a handcrafted
or neural leaf evaluator — which is exactly what c020 did and what c020's own audit flags as the
reason its search optimised the wrong objective.

## 8. Final move selection — `src/MCGS.cs::Select`

```
StoreVisitsAtEdges = true:
    MaxChild    -> argmax over root.OutgoingEdges of Edge.Value(0)
    RobustChild -> argmax over root.OutgoingEdges of Successor.VisitCount
```

There is **no baseline-override gate**. The search's choice is played. c020's conservative
override machinery has no counterpart here and is forbidden in the reference branch.

## 9. Registered deck-specific parameters — `src/SearchConfig.cs`, `src/NodeConfig.cs`

```
UCTConstant                 0.285
SampleWidth                 24
DampingParameter            2
DeterminizationNumber       200
FirstMoveDurationSeconds    15
ContinuousMoveDurationSeconds 10
DoNotRemoveUnselectedNodes  true      # graph reuse across atomic decisions
SimpleAbstraction           true
Transposition               true
StoreVisitsAtEdges          true
PIMC                        false
```

`UCTConstant = 0.285` is small relative to the ±10 terminal scale, so exploration is deliberately
weak once a terminal is proven.

## 10. Graph reuse — `src/MCGS.cs::Select` + `DoNotRemoveUnselectedNodes`

`Select` re-roots by moving `root` to the selected successor rather than discarding the graph, and
unselected nodes are retained. Sequential atomic decisions within a turn reuse accumulated
statistics. The transposition table merges matching abstractions into a single rooted DAG, with
dummy edges (`VisitCount = int.MaxValue`, so never selected) marking already-connected pairs.
