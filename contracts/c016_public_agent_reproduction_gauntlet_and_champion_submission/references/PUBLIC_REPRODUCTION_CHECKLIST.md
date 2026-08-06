# Public-agent reproduction checklist

A candidate is not a faithful reproduction merely because it uses the same deck.

## Source and permission

- Exact author, title, URL, access time, and hashes recorded.
- Competition rules and source licence/permission checked.
- Attribution requirements recorded.
- Submission reuse, local-only, clean-room, or rejected classification frozen before copying or packaging.

## Algorithmic fidelity

Check whether the public agent contains and whether the reproduction preserves:

- setup and bench planning;
- card-search and sequencing logic;
- damage and knockout calculations;
- prize-value calculations;
- resource, discard, and prize tracking;
- evolution and attachment route planning;
- attack and target planning;
- retreat and promotion rules;
- opponent archetype or matchup overrides;
- selective search, expectimax, or rollout logic;
- deterministic fallback behavior.

Replacing any material module with “choose highest damage” or a static priority list is a strategic rewrite, not reproduction.

## Compatibility patches

- Patch is required only for runtime/API compatibility.
- Patch does not change deck, strategy, search depth, thresholds, or matchup logic before baseline measurement.
- Every changed line is documented and hashed.

## Clean-room reproduction

- No copied source text beyond permitted interfaces and factual card data.
- Full public algorithm is specified semantically.
- Every material module is implemented.
- Shared-state behavior parity is measured when possible.
- Disagreements are categorized; fidelity is not overstated.

## Evidence labels

- `OFFICIAL_CURRENT`: official competition source verified now.
- `PUBLIC_REPRODUCIBLE`: claim reproduced from preserved public artifact.
- `PUBLIC_CLAIM`: author/title/notebook claim not independently verified.
- `UNVERIFIED`: could not be confirmed.

Never convert `PUBLIC_CLAIM` to fact in a summary.
