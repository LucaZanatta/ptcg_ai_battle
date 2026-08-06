# Failure record — the c008 evaluation defect and what the amendment changed

**No blocking failures in c009.** All 16 acceptance criteria executed and the content-aware
validator passed 39/39. This file records the failure that made c009 necessary, and states
plainly which c008 conclusions survived and which did not.

## What failed in c008 (my own work)

`tools/c008_final_eval.py::strategic()` re-attached the policy-arm label by positional `zip`
over results returned by `imap_unordered`. The c008 source comment on that line — *"attach arm
label (imap loses it otherwise)"* — shows the label was known to be lost and was then restored
by the one mechanism that is invalid under unordered completion. The bug shipped inside a
contract that claimed PASS 16/16, because the c008 acceptance check tested that evidence files
*existed*, not that their contents were correct. Two failures compounded: a data-integrity bug,
and an acceptance process that could not detect it.

A second, quieter inconsistency: `checkpoint_selection.json` designated the **median** seed as
each arm's representative while the c008 final evaluation actually used the **best-by-validation**
checkpoint, which the c008 summary then described as "best checkpoint per arm". And c008 never
evaluated the untouched c007 V2-A initialization, so its central claim — that RL was not worth
pursuing — was never tested against the policy RL actually started from.

## What c009 changed about the conclusions

| c008 said | c009 finds |
|---|---|
| strategic field: teacher 0.528, R1 0.289, R2 0.189, R0 0.11 | **corrupt**; corrected: teacher **0.570**, R1_101 **0.255**, R2_303 **0.228**, R0_202 **0.100** |
| held-out Abomasnow: teacher 0.50, R1 0.263 | **corrupt**; corrected: teacher **0.560**, R1_101 **0.270** |
| "no RL checkpoint is submittable" | **upheld** — best one-sided LB 0.1875 vs the unchanged 0.47 bound |
| RL feasibility INCONCLUSIVE | **upheld**, but for a better-supported reason |
| improvement over initialization: never tested | **YES** — R1_101 beats untouched V2-A on the teacher (0.160→0.220, P=0.98) and on the field (0.152→0.255, P=1.00) |
| R2 (teacher-anchored) was the primary hypothesis | R2 improves on the field but its teacher score is **indistinguishable from its initialization**; its anchors never left the high-anchor regime |

The headline c008 decision (do not submit) was correct. The evidence c008 used to reach the
*surrounding* conclusions was not, and one materially positive finding — that supervised-init RL
does improve on its initialization — was missed entirely.

## Why the c009 evidence should be trusted where c008's was not

- Identity is carried inside every result; nine assertions run before aggregation; 17 tests cover
  reordering, including a test that the c008 pattern is rejected.
- Every worker re-hashes the checkpoint it loaded and fingerprints the deck it played, so each of
  the 4,100 games proves which weights and which deck produced it.
- Every aggregate is recomputed from raw games by a separate validator using a different bootstrap
  seed; 14 tests show a pristine copy passes while 13 distinct corruptions are each detected.
- All 4,100 games are terminal with zero invalid actions, exceptions or timeouts, and every
  candidate/opponent cell is exactly seat-balanced.

## Residual limitations (not failures)

- Games are engine `random_device`-seeded; conclusions carry bootstrap intervals and the raw
  records ship so any number can be recomputed.
- 100 games per strategic cell — differences under ~10 percentage points are inside noise.
- R2's interpretation is bounded by the anchor-schedule finding (§2.5), not by a defect.
