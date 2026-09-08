# Claude Semantic Preflight Protocol

1. Use Claude Code non-interactively.
2. Request Opus explicitly and record the resolved model.
3. Disable tools.
4. Use frozen prompt and schema.
5. Provide only runtime-visible information.
6. Include human-readable card names, card text, decoded board fields, and semantic legal actions.
7. Cover multiple decision categories.
8. Reject illegal, malformed, duplicate, hidden-information-dependent, or semantically ungrounded outputs.
9. Repeat a frozen subset without session persistence.
10. Do not claim teacher superiority and do not train on labels.
