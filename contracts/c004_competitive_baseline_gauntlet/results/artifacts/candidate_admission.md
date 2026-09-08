# Candidate Admission — c004

Four complete deck–agent pairs were discovered, frozen, smoke-gated, and all four
admitted to the official gauntlet. They form a **policy × deck factorial** over
the only complete baselines available locally — the repo/starter kit ship **no
strategic agents**, and no public candidate was retrieved (network was available
but the contract prefers local and forbids reconstructing incomplete public
policies; local candidates suffice for a baseline).

## Admitted candidates

| candidate_id | policy | deterministic | deck | deck_id (prefix) | source attribution |
|---|---|---|---|---|---|
| `det_starter` | first-`maxCount` options | yes | starter | `sha256:7e7bca6783…` | current safe baseline (c001) policy on starter deck |
| `det_cabt` | first-`maxCount` options | yes | cabt built-in | `sha256:53ada9d42d…` | official cabt `first` policy on cabt built-in deck |
| `random_starter` | uniform random legal | no | starter | `sha256:7e7bca6783…` | c002/c003 random baseline policy on starter deck |
| `random_cabt` | uniform random legal | no | cabt built-in | `sha256:53ada9d42d…` | official cabt `random` policy on cabt built-in deck |

**Transparency (not hidden dupes):** all four adapters live in one file
(`starter_kit/candidates.py`), so they share the same agent-source hash. The
**material axes of difference** are recorded in the freeze:
- **policy_type** — `deterministic_first` vs `uniform_random_legal` (a real
  behavioral axis), and
- **deck_id** — starter (`7e7bca…`) vs cabt (`53ada9…`) (deck identity is part of
  candidate identity per the completeness definition).

`det_starter`/`det_cabt` share an identical policy and differ **only** by deck;
`det_*`/`random_*` differ by policy. No two admitted candidates are identical.

## Completeness & compatibility (§5)
Each candidate has: an exact 60-card cabt-accepted deck; an executable policy;
a stable id+version (`c004.1`); source provenance; agent + deck source hashes;
a canonical deck id + full multiset; a deterministic/stochastic classification;
and a working adapter (`CandidateAgent`) to the common agent interface.

Compatibility adaptations applied (documented, source-snapshotted, **no strategic
change**): the adapter returns the candidate's own deck at deck-selection, and
plumbs a per-game seed into the stochastic policy. No action priorities,
heuristics, decks, or fallback behaviors were changed.

## Freeze
Freeze hashes (agent/adapter source sha, deck_id, deck-source sha, policy_type)
were recorded **before** the gauntlet and re-verified **after** — identical
(`candidate_freeze_hashes_before.json` == `candidate_freeze_hashes_after.json`).

## Smoke gate (Phase 2) — all admitted
Each candidate played 10 games (5 seat 0, 5 seat 1) against ≥2 opponents:

| candidate | completed | invalid | agent errors | timeouts | admitted |
|---|---|---|---|---|---|
| det_starter | 10/10 | 0 | 0 | 0 | ✅ |
| det_cabt | 10/10 | 0 | 0 | 0 | ✅ |
| random_starter | 10/10 | 0 | 0 | 0 | ✅ |
| random_cabt | 10/10 | 0 | 0 | 0 | ✅ |

No candidate was rejected or non-admitted. See `candidate_smoke_report.json`.
