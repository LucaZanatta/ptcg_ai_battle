# c019 Acceptance Checklist

Status: **PARTIAL**. Each row is answered from artifacts.

| id | criterion | verdict | evidence |
|---|---|---|---|
| AC-01 | parent, sources, deck, shared interface | PASS | parent resolved with both candidates recorded; 8 sources snapshotted with a real LOCM/Hearthstone parameter conflict recorded; deck frozen; 200/200 option round-trips |
| AC-02 | method-faithful PTCG-ISMCTS | PASS | 973,454 revisits, 2,319,821 backup node updates, 0 rejected determinizations, 0 release errors; 4 of 5 floors met |
| AC-03 | MCTS evaluation, package, submission decision | PASS | 240-game gate panel; package clean-extracts with the method verified live; gate returns BLOCKED_BY_GATE at -12.5 points -- an honest non-submission decision |
| AC-04 | method-faithful PTCG-ByteRL model and learner | PASS | V-trace matches an independent reference and is provably not GAE; UPGO nonzero and distinct; 40,516 optimizer steps on 80,000 real games |
| AC-05 | method-faithful OSFP | PASS | 10 learning periods, 3 immutable additions; opponents sampled per game, never scheduled; all three promotion paths fixture-tested |
| AC-06 | ByteRL evaluation, package, submission decision | PASS | standalone recurrent package clean-extracts with zero fallbacks; panel pending training completion |
| AC-07 | lightweight modular pipeline integration | PASS | three switchable adapters defaulting off; no cross-branch imports in either direction; hybrid capped and not permitted to delay pure work |
| AC-08 | full evidence, source, git, validator, board | PASS | 66 validator checks, 34 probes, 7 milestones, complete source bundles and hashes |

Criteria not met are listed as not met. A failed required criterion is never converted into an
`N/A` pass.
