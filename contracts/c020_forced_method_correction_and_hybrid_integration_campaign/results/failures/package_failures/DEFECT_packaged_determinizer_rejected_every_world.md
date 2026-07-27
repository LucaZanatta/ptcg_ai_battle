# DEFECT — the packaged search played 0 searched decisions while looking healthy

**Found:** Phase 2 package smoke, `c020_mcts_smoke`.

## Symptom

The extracted package played every game to completion, on both seats, with zero errors and a
plausible win rate — and `searched_decisions = 0`. No exception was raised and no timeout was
recorded. The only visible trace was in counters the entry point did not originally expose:

```
determinizations_attempted: 336
determinizations_rejected:  336
```

## Cause

`c019_determinize.archetype_decks()` loads the public archetype decklists through
`cg.teachers.read_deck(...)`, which resolves paths under the c016 artifacts directory. Those
paths do not exist inside a package, so every call raised, every determinization was rejected by
the `except Exception: continue` guard, `roots` stayed empty, `_search` returned `None` before
incrementing `searched_decisions`, and the agent fell back to the branch-local baseline for every
decision.

The result is an agent that **is** the frozen baseline while reporting itself as corrected MCTS —
the c018 failure mode (a package that searched 3 of 84 decisions) reproduced by a different route.
It would have scored approximately baseline on the panel, which is precisely the range where the
number looks unremarkable rather than broken.

## Fix

Bake the decklists into the package at build time and rebind the loader, the same pattern already
used for the baseline agent path:

* `archetypes.json` is written from `archetype_decks()` during `build()`;
* the packaged `cg/c019_determinize.py` reads it when present and falls back to the c016 path
  only outside a package.

After the fix: 196 of 214 decisions searched, 4,300 simulations, both seats, zero errors,
`clean_extraction_ok: true`.

## Why the check caught it and the win rate did not

`method_actually_ran` is asserted from the agent's OWN counters, not from the package completing
games. A package that plays well because it silently degraded to the baseline passes every
liveness test built on games-completed or win-rate. This is why `CONTRACT §8` lists
package/source mismatch as a submission blocker separately from crashes.

The entry point now also surfaces `counters` and the first swallowed exception, so the next
failure of this shape is visible in the validation record rather than requiring a bisect.
