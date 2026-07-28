# DEFECT — an override in a multi-select context emitted an ILLEGAL payload

**Found:** during a code audit while the scaled runs completed, not by a failing test or a
crashing game.

## What was wrong

`c020_agent.act()` built the executed action for an override as:

```python
opt = next((o for o in opts if o.key() == decision.selected_action), None)
chosen = K.to_select_payload([opt], sel)
```

`to_select_payload` resolves options by key and does **not** pad to `minCount` — that is correct
behaviour for a function whose job is key resolution. The caller was responsible for cardinality
and did not honour it, so any override landing in a context with `minCount > 1` produced a
one-index payload where the engine requires several, and the engine rejects it:

```
ValueError: Must be Observation.select.minCount <= len(select) <= Observation.select.maxCount.
```

`CONTRACT §8` lists **illegal actions** as a submission blocker.

## This is repair-pass R1 in a second place

R1 fixed exactly this cardinality error inside the search — `_expand` and `_rollout` stepped every
multi-select context with a single option, costing 1,318,265 failed steps. The agent's own
**live-play** action path had the identical defect and was not covered by that fix, because the
search path and the execution path build payloads independently.

That makes three occurrences of one idea across this campaign: c019 modelled a multi-select action
as its first item in the ByteRL actor (audit #9); c020 repeated it in the search; and c020
repeated it again in the override execution path. Each was found by a different method — the audit
finding, error-string classification, and a manual read.

## Fix

The override now uses the same `build_payload` the search uses, with priors that place the chosen
action first:

```python
priors = {o.key(): (1.0 if o.key() == decision.selected_action else 0.0) for o in opts}
chosen = SEARCH.build_payload(sel, opt, opts, priors)
```

Four regression tests added, covering single-select cardinality, reaching `minCount`, deterministic
prior-ordered fill, and the degenerate case where `minCount` exceeds the option set (no
duplication).

## Why the panels did not surface it

The baseline action is produced by the scripted agent and already carries the correct cardinality,
so only the ~6% of decisions that override could hit this, and only the fraction of those in a
multi-select context. The 900-game post-repair run completed 900 of 900 games, so either no
override landed in a multi-select context or the affected games were rare enough not to appear —
`errors: 0` is consistent with both. A latent illegal-action path is a blocker whether or not it
fired in a particular sample.

## Budget

Recorded as an outstanding defect found AFTER the consolidated repair pass, and fixed rather than
deferred because `CONTRACT §8` makes illegal actions a submission blocker: shipping a package with
a known illegal-action path would not have preserved a submission. This is the same treatment
already applied to the packaged-ByteRL recurrent-state leak, and it is not a second repair cycle —
no ranking was re-run and no other defect was reopened.
