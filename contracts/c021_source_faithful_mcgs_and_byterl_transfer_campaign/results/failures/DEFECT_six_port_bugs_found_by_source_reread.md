# Six MCGS port defects, found by re-reading the source and by measuring rather than assuming

The port ran end-to-end on its first execution. Every number it produced was wrong in a way that
looked plausible.

## 1. `Expand` returned "continue" unconditionally (CRITICAL)

`Node.Expand` returns TRUE **only** when the tree phase must loop again — which happens when
`TranspositionCheck` merged into an existing node. A freshly created node returns FALSE and is
rolled out from.

My port returned `True` always, so the tree policy expanded without ever stopping: **96,675
expansions, max depth 175, and zero rollout steps** because the decision deadline was consumed
during descent. Fixed by threading the transposition result through as the continue flag.

After: expansions 96,675 → 4,837, max depth 175 → 8.

## 2. Untested actions were taken FIFO, not uniformly at random

`Node.TreePolicy()` is `_rnd.Next(UntestedActionIndices.Count)` — uniform random selection, then
removal. I popped index 0, which makes expansion order a deterministic function of the engine's
option ordering and correlates every node's first-explored branch.

## 3. `IsFullyExpanded` damping keyed on depth instead of chance nodes traversed

The source reduces the sample width by `DampingParameter ^ numSampleTraversed` — the number of
chance nodes traversed **in the current descent** — and compares it against the **sum of edge
SampleCounts**, not the edge count. I had used node depth and a count. Now
`reduce_function(24, k)` gives 24, 12, 6, … 1, matching the source.

## 4. Chance nodes are never created

`CheckRandom` marks a child random on choices, random effects, draws and end-turn transitions.
The port creates none, so `chance_samples = 0` and A4 is unimplemented at runtime. **Outstanding**
— tracked, not silently ignored.

## 5. The rollout checked the decision deadline (CRITICAL)

`PlayUntilTerminal` bounds a rollout by a 1000-step cap and a turn cap and **never** by the move
clock: the time budget governs how many searches run, not whether a started rollout finishes.

Checking the deadline inside the rollout aborted every one of them at 0.0.

## 6. PTCG terminal states were being read as draws (CRITICAL)

With 1–5 fixed, every rollout still returned **exactly 0.0** — 4,140 simulations per game with an
identical reward, which makes UCB selection pure noise. A search can be structurally perfect and
completely blind.

Measured cause: the engine signals a finished game by offering a select with an **empty option
list**, not a null select, and under uniform-random play PTCG games end by **deck-out** rather
than by prizes — every probed rollout ended with `opp_deck: 0`, after 59–239 atomic steps.

Before registering any adapter I checked the alternative explanation: that my payloads were
corrupting the state. They were not — determinization matches the live counts exactly
(`det_opp_deck: 47` against `opp_deck: 47`), and a turn-preserving policy reached
`my_prize: 0`, a genuine win.

`_terminal_reward` now decides a finished game by PTCG's own win conditions: prizes first, then
deck-out, and only a genuinely undecidable state returns the source's draw value. This is a
`SEMANTIC_ADAPTER` — Hearthstone's fatigue death, which the source's turn-45 cap anticipates, is
PTCG's deck-out. **No position is scored; only a finished game's winner is decided by the rules.**
`A7`'s prohibition on a handcrafted or neural leaf evaluator is untouched.

After: rewards **288 wins / 154 losses over 442 rollouts, 65% non-zero**.

## What this says about the first run

The first execution reported 3,437 simulations, 96,675 expansions, 3,142 transposition merges and
a live DAG. Every one of those numbers was real. The search was still worthless, because the
quantity it was maximising was constant.
