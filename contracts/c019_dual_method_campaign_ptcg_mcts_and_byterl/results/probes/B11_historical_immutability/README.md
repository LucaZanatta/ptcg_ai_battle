# B11 — Historical immutability

Promoted checkpoints are copied out, made read-only, and hashed at add time; the hash is re-verified on demand. Attempting to overwrite one raises rather than replacing it — silently overwriting would let a re-run replace history that earlier payoff numbers were measured against.

None/None verified.

**Status: NOT_EXERCISED.**
