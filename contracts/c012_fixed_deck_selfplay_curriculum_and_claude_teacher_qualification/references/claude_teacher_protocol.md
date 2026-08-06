# Claude Offline-Teacher Protocol

1. Use Claude Code non-interactively.
2. Request Opus explicitly and record the resolved model.
3. Disable tools during labeling.
4. Use a frozen prompt and JSON schema.
5. Label sequentially under a fixed state cap.
6. Never show hidden information, teacher/incumbent choices, or eventual outcomes.
7. Reject illegal, malformed, duplicate, or hidden-information-dependent labels.
8. Repeat a frozen subset without session persistence.
9. Claim objective superiority only after valid simulator branching and paired rollout adjudication.
10. Do not train on Claude labels in c012.
