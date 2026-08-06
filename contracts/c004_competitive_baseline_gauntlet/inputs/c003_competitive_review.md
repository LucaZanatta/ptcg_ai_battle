# c003 Competitive Review

## Accepted

c003 is accepted as a technical PASS.

It provides:

- schema-v2 self-describing captures
- canonical deck identity
- source/Git/engine/environment lineage
- honest engine RNG semantics
- semantic replay for the deterministic safe agent
- gzip capture and validation

## Required narrow amendments in c004

1. Terminal error extraction must inspect the final environment/player state, not the first step.
2. `legal_option_metadata` must equal `observation.select.option`, or the duplicated field should be removed.
3. Semantic replay must verify recorded agent identity, version, and source hashes before invoking current code.
4. Add only the minimal agent registry required for c004 candidates.

## Winning constraint

Do not create schema v3 or expand the general data platform.

The purpose of c004 is to select a competitive baseline deck–agent pair.
