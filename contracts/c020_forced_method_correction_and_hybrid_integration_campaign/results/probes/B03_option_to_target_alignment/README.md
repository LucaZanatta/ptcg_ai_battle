# B03 — Option-to-target alignment, measured on a trained checkpoint

Redirecting one option's source changes ITS logit by 1.21893 on average (max 4.46744) over 288 reassignments, and pointing it at the learned null token changes it by 1.98533.

**Cross-option leakage: 0.0.** Changing one option's source leaves every other option's logit bit-identical, which is what makes this a per-object gather rather than a pooled summary wearing one.

This was written after the resolver was found INERT (0 of 556 options resolving any reference) — a source-level check said B2 was implemented while nothing about the runtime was true.
