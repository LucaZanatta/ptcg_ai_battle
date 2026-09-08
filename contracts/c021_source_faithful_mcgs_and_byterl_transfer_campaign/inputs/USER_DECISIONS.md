# User Decisions — Frozen

1. Implement both MCGS and ByteRL.
2. Analyze both methods deeply, including failures and transferable strengths.
3. MCGS is the primary winning-oriented branch and must be pushed toward a real submission.
4. ByteRL is a faithful compute-limited research branch used to understand what works and what can be reused.
5. Hardware restrictions must not change either algorithm's architecture, equations, control flow, or semantics.
6. ByteRL may use fewer actors, fewer samples, fewer learning periods, and shorter elapsed training; those are scale limitations, not algorithmic substitutions.
7. No yes-man reporting. Weaknesses, defects, insufficient evidence, and compute limitations must be stated directly.
8. No third algorithm and no uncontrolled hybrid.
9. ByteRL components enter MCGS one at a time only after explicit admission tests.
10. Source code and raw evidence must be complete, canonical, and traceable to the final Git commit.
