# M01 — Branch-local baseline memory parity

521 decisions, **0 mismatches**, parity 1.0.

c019 exists because c018 proved that overriding a stateful scripted agent destroys it. Inside a tree the problem is worse: sibling branches would share one global `plan`, so exploring child B would corrupt the memory child A's subtree was built from. `PolicyMemory` snapshots exactly the globals the agent declares, and `verify_state_coverage()` fails if it ever grows another.

**Status: PASS.**
