# Project ground truth entering c014

## Corrected c013 state

- overall status: `PARTIAL`
- deployable teacher/Lucario specialist: `SOUP13_SOUP+P1_822`
- broad-field/Iono/Abomasnow specialist: `P0_711`
- previous stable reference: `C012_SOUP_622_633`
- curriculum plumbing: pass
- curriculum decision policy: not ready
- opponent overlap: inconclusive
- Claude serialization: partial
- Claude strategic teacher: not qualified
- c013 submission decision: `DO_NOT_SUBMIT`

## Strategic correction

The competition evaluates a deck-agent pair. The next branch must stop optimizing a frozen Dragapult policy as the primary objective and instead co-design a simple competitive deck with a deterministic deck-specific expert.

The operating order is:

```text
public evidence
→ deck-agent thesis
→ deterministic expert core
→ compact reliability test
→ package
→ submit
→ identify one loss mode
→ improve
→ submit again
```

## Branch allocation entering c014

- Meta-proven branch: primary and implemented now.
- Anti-meta branch: provisional thesis only; implementation begins after meta-proven v0 is submitted.
- Dragapult: preserved control, fallback, and evaluation opponent only.

## Anti-overengineering rule

No active branch may go more than 24 hours without a stable package-feasible version, and no complexity may be added without one documented loss mode it is intended to fix.
