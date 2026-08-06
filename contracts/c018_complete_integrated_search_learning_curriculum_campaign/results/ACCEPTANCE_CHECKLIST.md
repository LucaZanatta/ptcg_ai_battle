# c018 Acceptance Checklist

Status: **PARTIAL**. Each row is answered from artifacts, not asserted.

| id | criterion | verdict | evidence |
|---|---|---|---|
| AC-01 | parent resolution, immutability, baseline anchor | PASS | accepted reference 55011215 verified: True; 2,169 c005-c017 files unmodified |
| AC-02 | real official-API forward search | PASS | 42,857 roots, 609,875 search_step, depth 4, 0 hidden-info violations |
| AC-03 | integrated real-output smoke, probes, one consolidated repair pass | PASS | vertical all stages real: True; 8 defects ranked by downstream impact; consolidated rerun from M01; open findings ['D0'] (D0 is a design constraint, deliberately not closed cosmetically); 17/19 probes PASS, 0 NOT_EXERCISED |
| AC-04 | trusted heuristic-search candidate | PASS | evaluated on the frozen panel; packaged and clean-validated; submission decision recorded in DECISION_BOARD.md |
| AC-05 | real search trajectories and supervised training | PASS | 42,857 trusted decisions; 7,080 steps on cuda; reload exact: True |
| AC-06 | actual PPO curriculum | PASS | 81,920 real games, 66,604 steps, 81 distinct hashes; 0 performance promotions, so NO strategic curriculum claim is made |
| AC-07 | guided search, final panel, package, submission | PASS | 2,400 panel games across 6 stages; no candidate cleared the pre-registered promotion gate, so no upload was made and the non-submission decision is recorded in DECISION_BOARD.md and submissions/*_preflight.json |
| AC-08 | full source, raw evidence, git, validator | PASS | both bundles present; 146 artifacts placed in the §35 layout; validator 135/135, 0 blockers |

Criteria not met are listed as not met. §38 forbids converting a failed required criterion
into an `N/A` pass, and nothing here does.
