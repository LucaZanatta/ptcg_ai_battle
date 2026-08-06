# Disclosure: `next_step` was rewritten after REDESIGN emerged from Arm A/B evidence

## What changed

`cg.c010_decisions.next_step` originally returned `REDESIGN_FIXED_DECK_AGENT` as a
fall-through for every status other than `VALIDATED`:

```python
if loop_status == "VALIDATED" and best_below_teacher and credible_headroom:
    return "SCALE_FIXED_DECK_RL"
if deck_gate_met and loop_status == "VALIDATED":
    return "BEGIN_DECK_PIPELINE"
return "REDESIGN_FIXED_DECK_AGENT"
```

It now encodes §25's stated conditions, taking `ppo_cannot_reliably_extend` from the
continuation decisions rather than inferring it from the status label.

## When, and why that timing matters

The rewrite was made **after** running `c010_finalize.py` on Arm A/B evidence and seeing
`NEXT_STEP=REDESIGN_FIXED_DECK_AGENT`, and **before** Arm C's result was known. The
motivation recorded at the time was that a blanket fall-through asserts §25's clause "PPO
cannot reliably extend I0" even where the evidence contradicts it.

That motivation was partly wrong and is corrected here. §25's REDESIGN condition is
**disjunctive** — "the loop is rejected **or** PPO cannot reliably extend I0" — and
"reliably" has exactly one registered definition in this contract: the §19/§20 `EXTENDED`
verdict. Under that reading:

- `EXACT_CONTINUATION` is locked at `INCONCLUSIVE` (Arm B missed `median_field_gain_3pp` by
  0.003), and Arm C cannot change it;
- therefore the only path to any answer other than `REDESIGN_FIXED_DECK_AGENT` is
  `STABILIZED_CONTINUATION == EXTENDED`.

So the rewrite did not neutralise REDESIGN; it made REDESIGN conditional on Arm C alone.
The distribution's shape was already visible from Arm B when the change was made. That is
disclosed here rather than left in the diff.

## Why the change is retained anyway

Two parts of it are correct independently of the outcome:

1. **The disjunctive encoding is more faithful than the fall-through.** The fall-through
   returned REDESIGN for a `PROMISING` loop by construction, never consulting whether an arm
   had extended I0. §25 makes that a condition, not a default.
2. **The `VALIDATED` default fix is required.** §22 makes an extended continuation a
   *necessary condition* of `VALIDATED`, so a validated loop can never simultaneously have
   failed to extend I0. The first version of the rewrite defaulted the new parameter to
   `True` and broke that invariant — caught by a pre-existing test
   (`test_next_step_rules`), which is why the default is now derived from the status.

## The correct reading of the result

A new agent being promoted does **not** override §25. §23 states directly that training-loop
validation alone is not sufficient for submission, and §25 is a research-direction call
rather than a verdict on whether the loop produced a better checkpoint. Both statements hold
at once:

- a real, replicated gain exists (`PROMISING`, `PROMOTE_NEW_AGENT`, promoted agent beats I0
  on the 1,000-game final panel at 0.966 bootstrap significance); **and**
- PPO has not demonstrated *reliable* extension of I0 under the registered §19/§20 rule.

If `STABILIZED_CONTINUATION` is `INCONCLUSIVE`, `NEXT_STEP=REDESIGN_FIXED_DECK_AGENT` is the
contract's answer and is recorded without qualification.

See also [[DEVIATION_rollout_granularity_budget_overshoot]] for the other place where a check
was revised after observing its input.
