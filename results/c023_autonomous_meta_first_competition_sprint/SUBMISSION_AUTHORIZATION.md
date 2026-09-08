# Submission authorization

The contract permits an upload only if "explicit autonomous-submission authorization already
exists in the repository". When c023 began it did not, and `LEADERBOARD_SUBMISSION_PLAN.md`
recorded the search that established that: every `.py`, `.md`, `.json` and `.txt` in the
repository, for `PTCG_ALLOW_KAGGLE_SUBMIT`, `AUTONOMOUS_SUBMIT`, `ALLOW_KAGGLE` and
`autonomous_submission`. The only hits were c005-era references to a runtime environment-variable
gate, which is not a standing authorization.

**The user granted it directly, in session, on 2026-08-05:**

> "remember you can submit whenever you want. what is the status? any submition soon?"

It is recorded here so that the authorization exists in the repository, as the contract requires,
and so that the audit trail shows when it arrived and what it covers.

## What was submitted under it, and why

**Not a challenger.** No candidate in this campaign beat the champion; `EXECUTIVE_DECISION.md`
records that, and the contract forbids packaging a misleading challenger to complete a contract.

**The champion, because the wrong agent is currently on the ladder.** Checked 2026-08-05 03:37:

| ref | agent | submitted | public score | still moving |
|---|---|---|---:|---|
| 55011215 | `official_mega_lucario` | 2026-07-26 21:17 | **581.1** | **yes** — was 593.3 |
| 54948560 | `official_dragapult` | 2026-07-24 10:04 | 719.7 | no — frozen since July |

The most recent submission is the one the ladder plays, and ours is the **weaker** of the two by
about 139 rating points. c017 submitted `official_mega_lucario` as a baseline and it has been our
active agent for ten days.

This campaign's central measurement says that is backwards:

| | local field (13-player panel, 2,400 games) | predicted rating | actual |
|---|---:|---:|---:|
| `official_dragapult` | **0.5708** | 716.6 | 719.7 |
| `official_mega_lucario` | 0.3952 | 603.0 | 593.3 |

So the upload is not a bet on a new idea. It is putting the agent this campaign measured as the
champion back in the seat the campaign measured as being occupied by a weaker one.

**Legality:** `official_dragapult` is `SUBMISSION_REUSE_ALLOWED` — an official Kaggle sample
agent, byte-for-byte, attributed to Kiyota, with acceptance precedent (this exact agent was
accepted and scored as ref 54948560). No community code is in the package.
