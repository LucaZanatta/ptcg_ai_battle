# Why methods that won their competitions underperform in this campaign

Both source methods were competition winners: the MCTS-plus-evaluation line for Hearthstone
(Świechowski et al.) and ByteRL for LOCM (Xi et al., Xiao et al.). c020 implements both faithfully
— 38 probes, 31 invariants, three inert mechanisms found and fixed — and both underperform a
hand-written scripted agent. That deserves an explanation, and most of it is already measured
rather than speculative.

## 1. We are not running MCTS. We are performing surgery on a stateful scripted agent.

This is the largest difference and it is structural, not a matter of tuning.

The published Hearthstone work builds a **complete agent**: the search chooses every action, and
its rollout policy is its own. c020's search wraps the official Mega Lucario agent, uses it as the
rollout policy and the default action, and replaces roughly 8% of its decisions.

The ablation isolates exactly what that costs:

| arm | field | n |
|---|---|---|
| corrected machinery, overrides **disabled** | **0.5536** | 560 |
| corrected machinery, overrides **enabled** | 0.3729 | 480 |

The machinery is neutral: with overrides off it reproduces the baseline (0.5536 against a baseline
mean of 0.5575). Every point is lost at the moment the search acts on its own conclusion.

c018 established the mechanism independently: overriding the same agent at the same rate with
**random** actions reproduced almost the same collapse (0.192 versus 0.210 for real search, against
0.596 for never overriding). The damage is not mostly about action quality. The baseline is
stateful — it carries `plan`, `pre_turn`, `ability_used` and assumes its own previous
recommendations were executed — so an override invalidates a multi-turn plan, and the agent
continues executing a strategy whose premise no longer holds.

**No published result is being contradicted here.** None of those papers wraps a stateful scripted
agent and overrides a fraction of its moves. That configuration is this contract's, and it is
measurably hostile.

## 2. Our search budget is one to two orders of magnitude below theirs

Measured, not estimated:

```
simulations per decision       74.6
search_step calls per decision  891
maximum tree depth               15
mean search time per match     38.9 s
```

Competitive Hearthstone MCTS work operates at thousands of simulations per move with a fast
in-process forward model. Here every expansion is a native `search_step` across an FFI boundary,
and the ten-minute cumulative match clock with a 45% safety margin caps the whole match at ~5
minutes of search — roughly 700 ms per decision. Seventy-five simulations over a branching factor
of 10-40 does not resolve a deep tactical line; it mostly re-ranks the top few options using a
heuristic.

## 3. The published MCTS result depends on an evaluator we do not have

Świechowski et al.'s central finding is that **state evaluation quality dominates** — they combine
MCTS with *supervised learning on human game data* and report that better evaluation improves win
rate while reducing required computation.

c020's evaluator is an eighteen-feature hand-written heuristic over real card metadata. It is a
large improvement on c019's four features, and it is not a learned evaluator trained on strong
play. We have no corpus of strong human Pokémon TCG games to learn one from.

So the component the paper identifies as the decisive one is precisely the component we
substituted with something weaker. That is a coherent explanation for why more search does not
help: the search faithfully maximises an objective that is not a good enough proxy for winning.

## 4. Our ByteRL training is small by the standards of the papers

```
games            104,000
decisions      5,478,250
optimizer steps   97,649
wall clock           7.6 h on a single 24-core box with one GPU
```

The ByteRL papers train at a scale associated with large distributed actor fleets over days. A
single-box, 7.6-hour run is not a reproduction of their result; it is the same algorithm at a
small fraction of the compute. Reporting the gap as "the method underperforms" would misattribute
a resource difference to the method.

What the run does establish is that the implementation **learns**: five performance promotions
from clean frozen-checkpoint evidence, each requiring the current policy to beat every frozen
ancestor at above ξ=0.55, and two correct refusals when it could not.

## 5. LOCM is a smaller game than the Pokémon TCG

LOCM was designed as a research testbed with a deliberately compact action space. The Pokémon TCG
has larger and more structured decisions — multi-card selections, typed energy attachment, target
choice across twelve board slots — which is why B1/B2/B3 exist at all. A method that converges on
LOCM within a given budget need not converge here within the same one.

## 6. The baseline is a strong, specialised opponent

The frozen agent is a hand-written policy for this exact deck, and it holds a live ladder score of
632.3. "Underperforming" here means failing to beat a well-engineered special-purpose program at
its own deck — not failing to play the game.

## What would actually be needed

- **MCTS**: a learned evaluator (the paper's own prescription), and either a full-agent search
  rather than an override layer, or an override gate calibrated on far more evidence than 8% of
  decisions can supply.
- **ByteRL**: one to three orders of magnitude more training, which is a compute question rather
  than an implementation question.

## The honest summary

The campaign's negative results are about **this configuration at this budget**, not about the
published methods. The one finding that does generalise is not about either paper: overriding a
fraction of a stateful scripted agent's decisions is destructive across three contracts, three
implementations, and both random and searched replacements — and the corrected machinery
reproduces the baseline exactly when it stops doing that.
