# Defect: a candidate-type allow-list shrank the Q3 comparison set and flipped a registered gate

Caught during development, before any result was published. Recorded because it flipped a
**registered threshold**, which is the same defect class as
`c010 DEFECT_float_tie_flipped_a_registered_threshold.md`.

## What §16 requires

Q3 (ensemble→student distillation) runs only when an online ensemble beats **every trainable
single/soup candidate** on the confirmation panel by ≥3pp teacher gain or ≥3pp field gain.

## The defect

`q3_gate` selected the comparison set with an allow-list of type names:

```python
trainable = {c: v for c, v in cands.items()
             if fam.get(c) in ("weight_soup", "single_policy", None) and c != "T_teacher"}
```

The registries spell the single-policy type `single`, not `single_policy`. Once
`families()` was corrected to honour each registry's declared `candidate_type` — a separate
fix, made because the c012 incumbent is itself a weight soup and was being reported as a single
policy — the single policies stopped matching the allow-list and silently dropped out of
`trainable`.

`best_trainable_teacher` was then computed over a **smaller** set, so the bar an ensemble had to
clear fell. The observable effect:

```text
allow-list (wrong):   n_trainable_compared = 2   GATE = PASS   Q3 = RUN
by exclusion (right): n_trainable_compared = 6   GATE = FAIL   Q3 = SKIPPED_BY_GATE
```

An unnecessary Q3 distillation run would have been launched against a bar that only looked
beaten because four of the six candidates it was supposed to beat had been dropped.

## Why the direction matters

The failure was **not** symmetric. Dropping candidates can only lower `max(...)`, so this class
of bug can only ever make the gate *easier* to pass — it silently manufactures positive results
and never suppresses them. A membership test that fails open on an unrecognised type name is
therefore not a cosmetic issue.

## Fix

Define the set by exclusion, so an unrecognised type name cannot remove a candidate from the
comparison:

```python
trainable = {c: v for c, v in cands.items()
             if fam.get(c) != "online_ensemble" and c != "T_teacher"}
```

Only membership in the ensemble family is now name-dependent, and an ensemble mislabelled as
something else would be *added* to the comparison set — failing closed, making the gate harder,
which is the safe direction.

## How it was caught

The gate flipped from `SKIPPED_BY_GATE` to `RUN` after a change that should have affected only
a display label. A registered decision moving in response to a cosmetic edit is the signal;
`n_trainable_compared` was added to `Q3_gate.json` so the size of the comparison set is visible
in the evidence rather than implicit.
