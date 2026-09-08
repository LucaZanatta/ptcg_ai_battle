# Defect: a floating-point tie read as a miss, flipping STABILIZED_CONTINUATION

## Symptom

The first complete run of the decision stage reported:

```text
stabilized_continuation = INCONCLUSIVE
    NOT  median_field_gain_3pp
    median field 0.3133333333333333 gain 0.029999999999999916
```

§20 (via §19) requires a strategic-field gain of **at least** 3 percentage points. The
reported gain was `0.029999999999999916` — short of `0.03` by 8.4e-17.

## Root cause

The gain is a difference of two seat-balanced means, each an exact rational:

| quantity | exact value | float |
|---|---|---|
| I0 strategic-field score | `17/60` | `0.2833333333333333…` |
| Arm C median seed-best field score | `47/150` | `0.3133333333333333…` |
| gain | `47/150 − 17/60 = 9/300 = **3/100**` | `0.029999999999999916` |

The mathematically exact gain is **exactly 0.03**. Binary floating point cannot represent
`17/60` or `47/150` exactly, and the subtraction landed a few ulps low. A bare `df >= 0.03`
therefore read an exact tie as a miss.

This was verified with `fractions.Fraction`, not by inspection:

```text
EXACT gain = 3/100 = 0.03
gain == 3/100 exactly? True
```

Note the error is not even stable under reassociation: recomputing the two field scores in a
different summation order gives a difference of `0.030000000000000027`, which *passes*. The
condition's outcome was decided by float association order, which is not a property the
contract intends to depend on.

## Fix

`cg/c010_decisions.py` gains a single tolerance helper applied **uniformly** to every
registered gain threshold (§17 nomination 3pp/4pp, §18 c3 3pp/5pp, §19/§20 3pp/3pp):

```python
GAIN_EPS = 1e-9

def _ge(value, threshold, eps=GAIN_EPS):
    return value is not None and value >= threshold - eps
```

The tolerance is not a relaxation of any threshold:

- the metrics are seat-balanced means over 100–200 game panels, so their true resolution is
  `1/600 ≈ 0.00167` — more than six orders of magnitude coarser than `1e-9`;
- no value that is genuinely below a threshold can be admitted;
- "at least N percentage points" is inclusive, so an exact tie **must** count as met.

Pinned by tests in `tests/test_c010_promotion_rules.py::ExactTieThresholds`, including the
observed Arm C values, both genuine shortfalls (Arm A's 0.04-vs-0.05 and Arm B's
0.0267-vs-0.03, which still fail), and an assertion that `GAIN_EPS` is at least 1000× smaller
than the metric's resolution.

**Guarded by content validation, not only by unit tests.** The pre-existing
`*_conditions_consistent_with_decision` check would *not* have caught this: it compares the
stored condition flags against the stored decision label, and reverting `_ge` to a bare `>=`
flips both consistently. A dedicated check was therefore added —
`{decision}_threshold_ties_counted_as_met` — which recomputes the comparison from the stored
gain rather than trusting the stored flag, and fails when a gain within 1e-6 of its threshold
is recorded as NOT MET. It was verified by corrupting a copy of the artifact tree to simulate
the reverted tolerance; the validator returned `ALL_OK = False` with exactly that check
failing:

```text
FAIL stabilized_continuation_threshold_ties_counted_as_met
  -> ['median_field_gain_3pp: gain=0.029999999999999916 vs 0.03 recorded NOT MET
      while within 1e-6 of the threshold']
```

## Effect on the recorded result — stated plainly

This fix **changed a contract decision after the numbers were seen**, which is disclosed here
rather than left in the diff:

- `STABILIZED_CONTINUATION`: `INCONCLUSIVE` → `EXTENDED`
- consequently `NEXT_STEP`: `REDESIGN_FIXED_DECK_AGENT` → `SCALE_FIXED_DECK_RL`, because
  §25's REDESIGN clause ("PPO cannot reliably extend I0") is no longer supportable once an
  arm has reached `EXTENDED`.

What did **not** change, and could not have:

- `EXACT_REPRODUCIBILITY` stays `INCONCLUSIVE` (Arm A's field gain 0.040 vs a 0.05 bar is a
  real shortfall of 1 percentage point, ~6× the metric resolution);
- `EXACT_CONTINUATION` stays `INCONCLUSIVE` (Arm B's 0.0267 vs 0.03 is a real shortfall);
- `TRAINING_LOOP_STATUS` stays `PROMISING` — §22 requires `EXACT_REPRODUCIBILITY=PROVEN`,
  which no tolerance affects;
- `SUBMISSION_E` stays `DO_NOT_SUBMIT` — the teacher non-inferiority bound (0.245 vs the
  required 0.47) is nowhere near a tie.

The honest framing is that Arm C's continuation result sat exactly on the registered
threshold, and the original report of a miss was an artifact rather than a measurement. Had
the true gain been below 3pp by any amount the metric can express, the decision would have
remained `INCONCLUSIVE`.

See also [[DISCLOSURE_next_step_rule_rewritten]], which describes the §25 encoding this
interacts with, and [[DEVIATION_rollout_granularity_budget_overshoot]].
