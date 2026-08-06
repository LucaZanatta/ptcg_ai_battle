# Why confirmation was extended, and why this is not protocol drift

## What happened

§17 sets confirmation **floors**: "at least 200 independent-seed confirmation games against
Dragapult" and "at least 300 independent-seed strategic-field confirmation games".

§18's strength paths set **higher minimums**:

- path A: "at least 400 confirmation games" vs Dragapult;
- path B: "at least 400" vs Dragapult **and** "at least 600 total confirmation games" across the
  official field.

Running only §17's floors therefore makes both strength paths **unevaluable** — every candidate
would fail on game count regardless of how it played. The first confirmation pass ran the floors
(200 / 300); this note records the top-up to 400 / 600.

## Why this is executing the protocol, not changing it

The 400 and 600 minimums were written into `evaluation_protocol.json` under `strength_paths`
**before any candidate was scored**, and that file was committed at `cc64cb5` before the gauntlet
ran. Nothing about the gate, the thresholds, the panel, or the ranking rule changed. Only the
number of games actually collected moved — from a floor that cannot evaluate the gate to the
minimum the gate itself requires.

## The safeguard against optional stopping

Extending a run after seeing partial results is exactly how optional stopping produces a false
positive. Two constraints prevent that here:

1. **Fixed target, single pass.** The top-up size was decided before it ran — exactly enough to
   reach 400 vs Dragapult and 600 field for **both** finalists and for the Dragapult control —
   and the run was not stopped early or extended again. There is no "keep going until it passes".
2. **Both finalists and the control are topped up identically**, on the same continued
   independent seed block, so no candidate gains games the other did not.

The partial results at the floor were:

| candidate | vs Dragapult (n=200) | field mean (n=300) |
|---|---|---|
| official_mega_lucario | 0.535 | 0.613 |
| official_mega_abomasnow | 0.530 | 0.450 |

Both already exceeded path B's **rate** threshold vs Dragapult (0.48) at the floor, and Lucario
already exceeded the field threshold (0.55). The top-up was therefore not run in search of a
passing number — it was run because the registered gate cannot be evaluated at 200/300 at all,
whichever way the rates fell.

## What the top-up cannot fix

Game count is only one clause. Base conditions are evaluated separately and are unaffected by
this: Lucario's Stage A/B safe-control rate (0.82) and its rate against the c014 custom package
(0.625) sit below the registered 0.90 and 0.65 thresholds, and no additional confirmation games
change those. If a candidate fails a base condition it cannot be selected regardless of its
strength-path numbers.
