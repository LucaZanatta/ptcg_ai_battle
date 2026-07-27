# DEFECT — the validator read training claims out of the report it was judging

**Severity: the validator would have certified a c017-style fabrication.**

## What happened

The validator's own docstring states that "a summary asserting a number is never accepted as
evidence for that number". Its search and trajectory checks honoured that. Its **training**
checks did not: `actual_simulator_games`, `optimizer_steps` and `planned_vs_actual` were read
straight out of `curriculum_report.json`.

That is the exact surface c017 fabricated. c017's curriculum sampled a mixture, incremented a
counter, and re-evaluated an unchanged checkpoint; a validator reading those fields would have
agreed with it.

The mix check was worse than useless: it asserted only that `planned_fractions` and
`actual_fractions` both *existed*. A report with the planned numbers copied into the actual field
passed.

## Fix

Every training number is now recounted from raw rows:

- games counted by reading `raw_rollout_file`, compared against the reported figure;
- optimiser steps summed from one row per update in `raw_updates_file`;
- the realised opponent mix recomputed from raw per-game opponent labels and compared against
  the reported actual, per block, with a 0.02 tolerance;
- every update row carries the weight hash before and after, so a block that moved nothing is
  visible even if its loss printed fine.

`test_rejects_planned_mix_reported_as_actual` constructs a report whose ten games were all
against `iono` while claiming a 50/50 iono/self-play split, and asserts the validator rejects it.

## Generalisable lesson

Writing the principle in the docstring is not the same as implementing it. The checks that most
needed raw derivation were the ones where a report was most convenient to read.
