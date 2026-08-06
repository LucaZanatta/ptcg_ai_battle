# Measurement errors made during c016, found and fixed before they reached a verdict

Both were caught during execution, neither changed a published result, and both are recorded
because each could have produced a wrong verdict if it had survived.

## 1. Fidelity probe demanded a deck-specific feature shape

**Severity: HIGH — it wrongly failed two of the three candidates.**

The reproduction-fidelity gate included `material_functions_preserved`, computed as "every
feature probe matched". One probe, `planning`, searched for `AttackPlan`, `plan_a`, `plan_b` —
**identifiers that exist only in the Dragapult source**. Iono and Abomasnow are linear decks that
legitimately have no named attack-plan object, so both were classified `FAILED`:

```text
official_iono            FAILED   (missing feature: planning)
official_mega_lucario    EXACT
official_mega_abomasnow  FAILED   (missing feature: planning)
```

That result would have left only **one** exact candidate, breaching §13's "at least two exact
public implementations" and collapsing the gauntlet to a single agent.

**Why it was wrong:** these candidates are *byte-for-byte copies*. Nothing can have been replaced
by a static priority table if not one byte differs from the official source. The hash **is** the
anti-simplification proof; requiring a fixed feature shape punishes a deck for not needing a
feature its archetype omits.

**Fix:** the gate now tests `source_byte_identical_to_official` plus a shape-agnostic richness
check (≥200 lines and ≥6 material feature categories present). The semantic inventory remains as
descriptive evidence, not as a pass/fail requirement. Probe names were also corrected to
`planning_or_sequencing` so they cannot encode one deck's structure.

## 2. Denominator check compared display rounding, not denominators

**Severity: MEDIUM — it produced a false validator failure.**

`published_rates_and_denominators_match_raw_games` compared the CSV's stored rate against the
recomputed rate at a `1e-6` tolerance, and flagged:

```text
screening_results.csv  official_mega_lucario vs dragapult
  reported 0.4062   raw 0.40625
```

The denominators matched exactly (80 games); only the 4-decimal-place storage differed. A
validator whose failures are dominated by formatting artefacts gets ignored, which is worse than
no validator.

**Fix:** the comparison is made at the precision the CSV actually stores, `round(raw, 4)`. Any
real rate or denominator discrepancy is ≥ 1e-4 and is still caught, and the separate exact
integer check on game counts is untouched.

## Why these are disclosed rather than silently corrected

c016's own prior-results audit found three report-integrity defects in c015 — including a success
rate published over a zero denominator — by re-deriving numbers from raw records. A contract that
audits its predecessor for measurement defects and then hides its own would be applying the
standard in one direction only.

Neither error reached a published verdict: the fidelity error was caught when two candidates
failed a gate they could not logically fail, and the rounding error was caught by the validator
run that preceded the final reports.
