# CLAUDE_TEACHER_STATUS (AC-13)

**REJECTED**

- model requested `opus`, resolved `claude-opus-5`, verified per call from `modelUsage` output tokens
- schema-valid rate **0.92**, legal-action rate **1.0**, hidden-information violations **0**
- repeated top-1 consistency **1.0** (13 states relabelled independently)
- branching **INCONCLUSIVE** — The simulator exposes a forward-search API, but no observation captured through the standard agent interface carried the `search_begin_input` payload that `search_begin` requires, so a saved position could not be restored and branched under matched stochastic conditions.

§42 — QUALIFIED_* requires valid branching AND objective superiority. With branching INVALID the ceiling is PROMISING_UNVALIDATED regardless of how good the labels look; agreement and rationale quality are explicitly not evidence of teacher quality (§5).

Claude labels were not used to update any policy weights (§2).
