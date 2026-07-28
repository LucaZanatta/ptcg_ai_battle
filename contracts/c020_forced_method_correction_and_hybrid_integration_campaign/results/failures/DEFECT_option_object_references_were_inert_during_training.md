# DEFECT — B2's option-to-object references resolved 0% and were inert during scaled training

**Found:** by code audit, while the scaled runs completed. Not by a test, not by a crash, and not
by any metric the campaign was already watching.

**Severity: material.** The first scaled ByteRL run — 104,000 games, ~107,000 optimizer steps,
eight learning periods — trained a model in which one of the two headline ByteRL corrections was
non-functional.

## What was wrong

`build_option_refs` resolved each option's source, target, hand card, card id and attack id by
scraping integers out of the canonical key:

```python
kk = list(o.key()) if isinstance(o.key(), (list, tuple)) else []
nums = [int(x) for x in kk if isinstance(x, int)]
```

The canonical key is `(select_type, select_context, option_type, fields, card_id, attack_id)`,
where `fields` is a **nested tuple** holding `area`, `index`, `playerIndex`, `inPlayArea`,
`inPlayIndex` and the rest. `isinstance(x, int)` skips a tuple, so every reference the resolver
needed was invisible to it.

Measured over a full game before the fix:

```
options seen                556
with source reference       0   (0.0%)
with target reference       0   (0.0%)
with hand reference         0   (0.0%)
with attack id              0   (0.0%)
```

Every option gathered the learned NULL token for both source and target. The mechanism existed,
was covered by a passing probe, and did nothing — which is exactly the failure mode
`references/C019_AUDIT_FINDINGS.md` #17 names: *method names and file existence are insufficient
fidelity evidence.* My own validator check for B2 asserted that `opt_src`/`opt_tgt`/`OptionRef`
appear in the source and that twelve energy types are encoded. All of that was true. None of it
established that a reference ever resolved.

## What was NOT affected

`B1` slot-awareness was fully functional throughout: twelve fixed board slots with position
embeddings, typed energy counted per type, statuses, tools, retreat cost, prize value and
per-Pokemon attack legality. The probe evidence for B1 — an active/bench swap changing option
logits — is genuine and unaffected, because that test perturbs the board tensor rather than the
option references.

The MCTS branch is entirely unaffected: it does not use this encoder. Its floors, ablations and
panel results stand.

## Consequence for the trained model

The policy saw a correct slot-aware board but could not tell **which** board object each option
referred to. It scored options by select type, context, list position and the shared state
context alone. It therefore could not distinguish "attach energy to bench slot 2" from "attach
energy to bench slot 3" — which is precisely the audit-#7/#8 failure c020 exists to correct.

So the first run demonstrates corrected recurrent semantics (B3–B7, all verified independently)
on top of a **partially uncorrected observation**.

## Fix

`build_option_refs` now reads the structured fields the engine actually provides — `area`,
`index`, `playerIndex`, `inPlayArea`, `inPlayIndex`, `cardId`, `attackId` — indexed by NAME
through `c019_core.OPTION_FIELDS` so a reordering cannot silently repoint them, and maps
(area, index, owner) onto the fixed twelve-slot board layout.

After the fix, over a full game:

```
options seen                622
any object reference        307 (49.4%)
source reference            18.0%
target reference            29.4%
hand reference              31.4%
card id                     31.4%
attack id                    8.4%
```

The remaining ~50% are options that genuinely reference no board or hand object — end turn, pass,
deck and prize selections — so 100% is the wrong target and would indicate a different bug.

## Disposition: the run is superseded and ByteRL is retrained

The first run is retained in full, marked superseded, and cited as the evidence for this record.
Corrected ByteRL is retrained from fresh random weights with the working resolver.

Reporting "B2 is implemented, and the submitted model was trained without it" would be a method-
fidelity failure dressed as a pass, and the campaign's whole purpose is to not do that. The 96-hour
box has ample room; the cost is wall clock, and a missed correction cannot be bought back later.

## What this says about the validator

The validator has 34 negative controls and caught none of this, because its B2 check tested the
SOURCE for the presence of the mechanism rather than the RUNTIME for its effect. A check added
here asserts a nonzero resolution rate on real observations — a rate of 0 now fails — and a
regression test pins the structured-field decoding directly.
