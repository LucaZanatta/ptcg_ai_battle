# P07 — Trajectory integrity

The distillation set and the audit log must describe the same decisions. 47,086 JSONL
rows and 47,086 feature rows align one-to-one, and the `trusted_rows` index stored in the NPZ is
*identical* to the set of rows flagged trusted in the JSONL — checked as sets, not as counts, so
an off-by-one reordering cannot pass.

Every trusted row carries at least one real successor. Every label lies inside its own option
range. Every legal mask is exactly as long as its option list.

`uses_c017_labels: False` — c017's depth-0 labels are not importable from the
generator and no row here derives from them.

**Known limit, quantified.** The feature tensor holds K_MAX=32 option slots.
3 rows had more options than that, and exactly
0 rows chose an option at index ≥ K_MAX — those were
stored with label 0, a *wrong* target rather than a truncated one. They are excluded from the
distillation index (M02), not merely disclosed. The JSONL retains the true option count either
way.

848 rows are multi-select. The feature label stores `label_action[0]`
only, so any agreement metric computed against it is FIRST-PICK agreement, not whole-selection
agreement.

**Status: PASS.**
