# LEADERBOARD_SUBMISSION_PLAN

## Authorization: none exists, so nothing is uploaded

The contract permits an upload only if "explicit autonomous-submission authorization already
exists in the repository". It does not.

Searched this run: every `.py`, `.md`, `.json` and `.txt` in the repository for
`PTCG_ALLOW_KAGGLE_SUBMIT`, `AUTONOMOUS_SUBMIT`, `ALLOW_KAGGLE` and `autonomous_submission`. The
only hits are c005-era references to an **environment-variable gate** — `PTCG_ALLOW_KAGGLE_SUBMIT`,
which is a runtime switch a human sets, not a standing authorization recorded in the repository.
No authorization file, no contract clause granting one, nothing in c023's own inputs.

```text
DECISION: prepare packages; do not upload
```

**Not uploading on 2026-08-05 forfeits nothing.** The competition's own deadline is
**2026-08-16 23:59 UTC** (`kaggle competitions list`, retrieved 2026-08-03), eleven days after
this contract closes. Every package below is complete, hashed and clean-validated, and the exact
upload command is recorded so a human can execute it in one line whenever they choose.

Credentials are present and working, which is *why* this has to be stated explicitly rather than
left implicit: `~/.kaggle/access_token` authenticates the CLI right now, and `kaggle competitions
list -s pokemon-tcg` returns the competition with `userHasEntered: True`. The gate here is
authorization, not capability.

## Where we stand on the ladder

| submission | ref | public score | reading date |
|---|---|---:|---|
| c005 official Dragapult sample | 54948560 | **719.7** | 2026-08-03 |
| c017 official Mega Lucario sample | 55011215 | 593.3 | 2026-08-03 |
| c014 Archaludon expert | 55004756 | 471.4 | 2026-08-03 |
| c015 anti-meta expert | 55005237 | 390.7 | 2026-08-03 |

Ladder context (keidroid snapshot, 6,113 teams): median 637.8, P75 755.2, P90 836.1, P95 903.8,
P99 1035.6, max 1262.2. Our best sits near the 65th percentile.

**The public score is a live ladder rating, not a result.** c014 moved 600.0 → 754.5 → 641.1 →
589.6 inside one hour on 2026-07-26. Every number above is a timestamped snapshot. No promotion,
regression or champion claim in this contract rests on a single reading.

## Upload commands, in the recommended order

Run from the repository root. Each is one line and requires no edits.

```bash
# 1. the frozen champion -- the fallback, unchanged from the official sample's behaviour
.venv/bin/kaggle competitions submit pokemon-tcg-ai-battle \
  -f results/c023_autonomous_meta_first_competition_sprint/final_packages/c023_champion_dragapult.tar.gz \
  -m "c023 frozen champion: official_dragapult, wrapper action-identical, <COMMIT>"
```

Any challenger package is listed in `final_packages/` with its own manifest, hash and clean
validation; `EXECUTIVE_DECISION.md` names which — if any — is recommended and on what evidence.
**A challenger is only listed here if it cleared the promotion rule registered in
`PANEL_SPLIT.json` before it was measured.** A package that exists is not a package that is
recommended, and this file distinguishes the two.

## Per-package record

Each `final_packages/<name>_manifest.json` carries: source commit and dirty flag, deck list and
`deck_sha256`, `base_agent_sha256`, `wrapper_sha256`, the enabled rules, the archive sha256 and
size, the attribution text, and an **executed** clean validation — the archive extracted to a
scratch directory and played out of it, with completed games, errors, both seats and worst-case
decision latency. A manifest without an executed clean validation fails validator check V09.

## Submission constraints that remain unverified

The competition rules page is a client-rendered single-page application and returns no
machine-extractable text to an unauthenticated fetch; c005 recorded this and it has not changed.
So **the published per-decision timeout and the daily submission limit are UNVERIFIED**. This
contract enforces its own bound and labels it as such:

- self-imposed maximum decision latency: **1000 ms**, checked on every package
- observed worst case across all c023 candidates: ~250 ms (base) and ~800 ms (the public
  Alakazam agents, which are opponents here, not candidates)
