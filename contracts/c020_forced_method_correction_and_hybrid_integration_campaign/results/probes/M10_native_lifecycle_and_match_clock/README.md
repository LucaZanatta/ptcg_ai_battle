# M10 — Native lifecycle and match clock

Zero release errors, zero begin errors and zero step errors over 11,365,961 `search_step` calls. Maximum cumulative search per match 50843.3 ms against a 600,000 ms clock.

The step-error count was 1,318,265 before the repair pass: every multi-select context failed, so those positions were unexplorable. See `implementation/repair_pass.md` R1.
