# Results Protocol

- c005 through c011 are immutable.
- The c005 Dragapult deck is exact and frozen.
- Raw games are the source of truth.
- Every evaluation result preserves immutable job and checkpoint identity.
- The curriculum registry is hash-locked before new training.
- P0 and P1 share the same start, PPO setup, budgets, and evaluation panels.
- The opponent curriculum is the only training variable.
- Claude inputs contain runtime-visible information only.
- Claude labels never update policy weights in c012.
- File existence is never sufficient for acceptance.
- All thresholds are frozen before final results.
- All Python source, prompts, schemas, and sanitized Claude inputs/outputs are archived.
- No credentials may be stored.
