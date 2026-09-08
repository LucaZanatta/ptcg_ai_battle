# Submission A Decision

**Decision: SUBMIT**

- Teacher: `dragapult` (Dragapult ex), archetype spread_setup.
- Frozen deck id: `sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab` (60 cards).
- Reuse: OFFICIAL_REUSABLE (official Kaggle sample; submission-eligible).
- Archive: `submission_A_teacher.tar.gz`, 500422 bytes (< 104857600 limit).

## Packaging + reliability gates (all must pass for SUBMIT)
| check | pass |
|---|---|
| size under limit | True |
| main.py / deck.csv / cg/ present | True / True / True |
| no secrets / no training data | True / True |
| clean extraction | True |
| >=20 extracted smoke games | True |
| zero invalid selections | True |
| all games terminal | True |

Extracted-archive smoke: 20 games vs ['iono', 'mega_abomasnow', 'mega_lucario'],
invalid=0, non-terminal=0,
P99 latency 0.33 ms.

## Upload
Actual upload is gated behind `PTCG_ALLOW_KAGGLE_SUBMIT=1` (see AC-08). The flag is
absent by default -> **not uploaded**; the exact command is in
`KAGGLE_SUBMIT_COMMAND.txt`. Caveat: the full competition rules text was not
machine-retrievable (JS-rendered page); reuse basis is the teacher's official-sample
provenance (`rules_and_reuse_audit.md`).
