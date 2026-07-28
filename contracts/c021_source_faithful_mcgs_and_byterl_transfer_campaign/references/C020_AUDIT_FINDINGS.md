# c020 Findings That c021 Must Not Repeat

## Reporting/source integrity

- `SUMMARY.md` and `STATUS.json` were stale relative to a completed final panel.
- Source bundles represented different commits/repair states.
- A complete source archive was corrupt.
- Package/source identity was inconsistent.

c021 must generate all final reports after raw final artifacts and derive all source snapshots from one exact final commit.

## Search

- c020 search mechanics improved, but executed overrides harmed the strong baseline.
- c020 used a handcrafted tactical leaf evaluator and PUCT-style system, not official-source MCGS.
- initial action-type detection defects made veto/evaluator features inert.
- zero terminal leaves in scaled search meant the handcrafted evaluator determined returns.

c021 must not repair c020 search and call it MCGS. It must port official MCGS source behavior.

## ByteRL

- c020 corrected slot identity, typed features, multi-select, recurrence and OSFP mechanics substantially.
- the first corrected run still had inert option-to-object references and required fresh retraining.
- training against only current/historical ByteRL policies produced poor external generalization.
- recurrent verification did not independently recompute all claimed quantities.
- the value head failed admission.

c021 must use c020 only as infrastructure/negative evidence. ByteRL begins fresh and must evaluate externally throughout.

## Hybrid

- ByteRL policy priors showed a potentially useful signal.
- neural value was not actually called because admission failed.
- H2–H4 labels overstated what executed.

c021 transfer tests must verify runtime call counts and change one component at a time.
