# B09 — Payoff table identity

26 payoff tables written, one per learning period. Every G/C cell names the historical checkpoint's index, path and SHA-256, so a payoff number can be traced to the exact weights it was measured against.

G and C update only for `HISTORICAL_PAYOFF_SAMPLE` games — self-play games carry no payoff information about a historical opponent.

**Status: PASS.**
