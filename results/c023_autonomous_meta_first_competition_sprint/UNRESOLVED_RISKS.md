# UNRESOLVED_RISKS

Things this campaign could not settle, stated as risks to the conclusions rather than as caveats
about the effort.

## R1 — the local panel is a proxy for the ladder, and the mapping is unmeasured

Every strength number here is a field score against ten local opponents. The competitive objective
is a Kaggle rating produced by rating-matched play against 6,113 submissions. Nothing in this
campaign measures the function between them, because doing so needs uploads and there is no
authorization to make any.

The one anchor available: our official Dragapult sample scores **0.4653** locally and **719.7** on
the ladder; our official Mega Lucario sample scores **0.3521** locally and **593.3**. Two points,
same direction. That is consistent, not a calibration.

**Consequence.** A local improvement of a few points cannot be converted into a rating claim, and
this contract makes none.

## R2 — the meta snapshot is third-party, two days old, and thin at the top

The archetype shares driving `field_ladder_weighted` come from `myso1987`'s replay classifier,
snapshot 2026-08-02, with **17 classified teams in the 1100+ band**. Band-level shares there carry
wide uncertainty. They are used for ordering — Grimmsnarl dominates, Mega Lucario does not appear
above 1000 — and never as weights with claimed precision. The unweighted field score remains the
primary number everywhere.

## R3 — one Grimmsnarl implementation stands in for 60% of the top ladder

`pub_tetsutani_grimmsnarl` is *an* implementation of Marnie's Grimmsnarl, not the archetype. Every
statement here about "the Grimmsnarl matchup" is really about that agent. A rule tuned against it
could be tuned against its quirks. The dev/validation split holds out two *Mega Lucario search*
implementations and two further Alakazam implementations, so archetype-generalisation is tested —
but there is no second Grimmsnarl agent to hold out, and that is the weakest point in the panel
design.

## R4 — the champion's own strength interval is ±3.6 points, and the run-to-run floor is ~1–3

`official_dragapult`, 720 off-mirror games: 0.4653, Wilson 95% [0.4291, 0.5018].

The run-to-run floor has **three independent measurements**, and the third is the strongest
because the two policies are *provably* identical rather than assumed to be:

| pair | games each | field scores | apart | how identity is known |
|---|---:|---|---:|---|
| `chal_dp_base` vs `chal_dp_base2` | 400 / 600 | 0.4850 / 0.5166 | **3.2 pp** | same wrapper, no rules, same deck |
| `chal_dp_base2` (plan_screen1) vs (rule_screen1) | 1000 / 600 | 0.5060 / 0.5166 | 1.1 pp | the same candidate directory |
| **`chal_dp_bench2` vs `chal_dp_base3`** | **1200 / 1200** | **0.5142 / 0.5042** | **1.0 pp** | the firing probe proved `bench2`'s only rule was **INERT** — 0 fires in 1,329 decisions — so the two were byte-equivalent policies |

And the sharpest estimate of all, because it is the *same candidate directory* measured three
times at the same game count:

| run | candidate | games | dev field |
|---|---|---:|---:|
| `rule_screen2` | `chal_dp_base3` | 1200 | 0.5042 |
| `rule_screen3` | `chal_dp_base3` | 1200 | 0.5125 |
| `rule_screen4` | `chal_dp_base3` | 1200 | **0.5279** |

**Range 2.4 points, SD ≈ 1.2, on one policy at 1,200 games per run.**

That is the number every comparison in this campaign is read against — and it is larger than
the ±1.0 the two-policy comparison suggested, so the earlier estimate was optimistic. At 400–600
games the spread is ~3 points. **No difference under ~2.5 points at 1,200 games is evidence of
anything**, which retires most of the small positive deltas in this campaign's screens.

It is also why `deck_screen1`'s apparent +7.25 point winner evaporated to −0.12 at 1,200 games,
and the standing reason to distrust any single-run screen result here.

## R5 — the engine cannot be seeded, so nothing is paired on the deal

`libcg.so` seeds `std::mt19937` from `std::random_device` and exposes no seeding API (c002
established this against the binary). Two arms therefore never see the same shuffle. "Paired"
here means matched opponents, matched seats and matched counts, and the variance reduction a
common-random-numbers design would give is simply unavailable. All intervals are wider than they
would be with a seedable engine.

## R6 — the engine can kill a process, and the rate is only bounded, not zero

Several public agents call `search_begin` without releasing every handle. The engine's handle
buffer has capacity 7, and the eighth allocation throws an **uncaught C++ exception** that aborts
the process by SIGABRT. This campaign's harness forks one child per game, so an abort becomes a
recorded `engine_process_deaths` count rather than a hung pool — but the same defect is available
to *our* planner if a code path ever leaks a handle.

Mitigation in place: every handle created by `planner.py` is released on every path including
exceptions, and `engine_process_deaths` is reported per arm in every summary. **Observed: zero
across the campaign.** Bounded and monitored, not proven absent.

## R7 — the competition's real limits are unverified

The rules page is a client-rendered single-page application and returns no machine-extractable
text to an unauthenticated fetch (c005 recorded this; unchanged). So the published per-decision
timeout, the submission size limit and the daily submission limit are all **UNVERIFIED**. This
contract enforces a **self-imposed** 1000 ms per-decision bound and labels it as such. If the real
limit is tighter than ~250 ms, the champion package is still fine (its worst observed decision is
~250 ms including one-off warm-up) but a search-heavy candidate might not be.

## R8 — measured latency was not taken in a quiet window

Decision latency in this campaign was measured while 20 evaluation workers shared the machine with
a neighbouring 100%-CPU job from an unrelated project. Count-budgeted evaluations tolerate that —
an arm becomes slower, never weaker — but the **latency numbers themselves are inflated**. They
are therefore conservative for the packaging gate (a real deployment would be faster) and useless
as a precise deployment measurement. The planner's work budget was deliberately converted from a
wall-clock budget to a count for exactly this reason (`PIVOT_LEDGER P4`).

## R9 — the base agent's internals are consulted through a second instance

The veto primitive and the planner both drive a **second, independent instance** of the base
agent, so the real instance's plan state advances exactly once per real decision. That second
instance sees a different observation stream from the real one, so its own carried state
(`pre_turn_log`, the card-count `prize` prediction) drifts. Everything the base recomputes at a
MAIN decision from the observation is unaffected; the drifting parts are the log-derived flags
`pre_ko` and `no_item`. The risk is that a veto's replacement action is chosen under slightly
stale flags. Bounded and small, and unmeasured.

## R10 — no replay of our own submissions was mined

The Kaggle episode-replay API exposes the 60-card deck of any leaderboard team, and public kernels
demonstrate the technique. At ~2 s per request with cooldowns it does not fit inside this window
alongside the experiments that need the same hours. So this campaign's meta evidence is
second-hand aggregation rather than first-hand replay analysis, and **our own submitted agents'
losses were never inspected**. That is the single largest piece of available evidence this
contract did not use.
