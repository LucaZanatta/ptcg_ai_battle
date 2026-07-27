# DEFECT — a forward search cannot be layered on a stateful scripted agent by overriding it

**Severity: invalidates the campaign's central gameplay comparison.** Found by disbelieving the
campaign's own headline number rather than reporting it.

## The number that did not add up

`m01_heuristic_search` **is** `official_mega_lucario` plus a real official-API forward search
that keeps the baseline action as candidate 0 and never prunes it. On the frozen panel it scored
**0.210** against the baseline's **0.580** over 400 identical games each.

A search that always considers the baseline should be roughly bounded below by the baseline. A
37-point collapse is close to impossible from action quality alone, so the number was treated as
a symptom, not a finding.

## The control

Same baseline agent, search replaced by a **random legal action** at the same override rate:

| arm | override rate | win rate | n |
|---|---|---|---|
| never override | 0% | **0.596** | 240 |
| random legal override | 18.6% | **0.192** | 240 |
| real search (panel) | ~26% | 0.210 | 400 |

Two things follow immediately. The harness is sound — with overriding disabled it reproduces the
panel baseline (0.596 vs 0.580). And **random overrides reproduce the entire collapse**: the real
search, with 609,875 verified simulator steps behind its choices, scores barely above random.

## Mechanism

The official agent maintains module-level state across decisions — `global plan`,
`global pre_turn`, `global ability_used`. Its recommendations assume its own previous
recommendations were executed. Playing something else desynchronises that state from the actual
game, so every later baseline action — **including the search's own candidate 0** — is computed
from a false model of the position.

That is why "the baseline is always candidate 0" fails to bound the result from below. It would
bound it for a *stateless* baseline. For a stateful one, consulting the agent and then ignoring
it poisons the very candidate that was supposed to be the safety net.

## Consequence

Either the baseline must be a pure function of the observation, or the search must own the whole
policy rather than sit on top of a scripted one. This is a design-level constraint, not a bug
with a patch — and it applies to `submission_K` and `submission_L`, which embed this exact
wrapper. Their panel numbers are therefore faithful to what those archives would do on the
ladder, which makes the pre-registered gate blocking them correct rather than unlucky.

## What this does NOT establish

It does not show real forward search is useless for this game, and it does not cleanly measure
the leaf evaluator — because state corruption dominates, a good and a bad leaf evaluator would
both score near random here. The separate alignment measurement (heuristic Pearson 0.180 versus
learned 0.284 against actual outcomes, over 42,857 decisions) is the better evidence on that
question, and it points the opposite way from what this panel superficially suggests.

## Generalisable lesson

The campaign's most expensive artifact — 82k curriculum games, 43k trusted search decisions —
was evaluated through a wrapper whose failure mode made every candidate look equally bad. A
result that is *too* decisive deserves a control before it deserves a write-up.
