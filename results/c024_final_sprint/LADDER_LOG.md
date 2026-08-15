# Ladder log and the champion-protection rule

## The eviction question, resolved

Kaggle keeps roughly the **two most recent** submissions playing and lets the rest go dormant.
Measured on our own five submissions on 2026-08-12:

| submission | agent | episodes | last game | games since Aug 11 |
|---|---|---:|---|---:|
| 55254872 | `official_dragapult` (champion) | 191 | 2026-08-12 17:30 | **35** |
| 55011215 | `official_mega_lucario` | 267 | 2026-08-12 16:42 | **22** |
| 55005237 | c015 anti-meta | 119 | 2026-08-04 | 0 |
| 55004756 | c014 Archaludon | 33 | 2026-07-26 | 0 |
| 54948560 | c005 dragapult | 83 | 2026-07-26 | 0 |

**So exactly one slot was free**, occupied by `official_mega_lucario` at 603.6 — an agent strictly
worse than the champion and of no competitive use. One more submission after this one would
evict the champion itself.

**Rule for the rest of the campaign:** the champion is the last thing submitted before
2026-08-16 23:59, and no submission is made that would leave it dormant at the deadline unless
something has beaten it *on the ladder*.

## The champion's rating was never 788

| reading | date | games | rating |
|---|---|---:|---:|
| first | 2026-08-05 | ~30 | **788.1** |
| converged | 2026-08-12 | 191 | **686.7** |

The 788.1 that closed c023 was an early, high-variance reading of a rating that had not settled.
Over 191 games it came down to 686.7. `live-ladder-rating-not-fixed-score` said not to declare a
champion from one reading; this is the same mistake in a quieter form — the number was quoted as
an achievement when it was a snapshot. The +209.7 gain c023 recorded against the *then-live*
`official_mega_lucario` still holds directionally (686.7 against 603.6 = **+83.1**) but it is a
quarter of the size first reported.

## Submissions

| ref | date | agent | local field | predicted | actual |
|---|---|---|---:|---:|---|
| 55254872 | 2026-08-05 | `official_dragapult` | 0.4967 | 668 | **686.7** |
| 55011215 | 2026-07-26 | `official_mega_lucario` | 0.3952 | 603 | **603.6** |
| **55466460** | **2026-08-12** | **c024 Alakazam (ours)** | **0.3424** | **569** | pending |

The calibration `rating = 347.5 + 646.7 × field` has now predicted the champion to within 19
points and mega_lucario to within 1. It predicts 569 for the Alakazam agent.

## Why the Alakazam agent was submitted at all

It is **not** a challenger. On the eleven-opponent panel it scores 0.3424 against the champion's
0.4967, and excluding the three Alakazam agents — our panel is 27% Alakazam against roughly 9.5%
of the real 1000+ ladder — it is 0.4063 against 0.4691. It is behind on both readings.

It was submitted because the free slot held something useless, and because the panel *provably
cannot* answer the question it raises. `S0_PUBLIC_AGENT_SCREEN.md` measured the panel-to-ladder
per-matchup correlation at **Spearman −0.200**, and this agent's profile is unusually
matchup-shaped:

| it beats | | it loses to | |
|---|---:|---|---:|
| `pub_prvsiyan_lucario_v12` | 0.567 (champion: 0.300) | `official_iono` | 0.217 (champion: 0.750) |
| `pub_makthanithin_lucario_1084` | 0.500 (champion: 0.317) | `pub_prvsiyan_crustle_wall` | 0.183 (champion: 0.567) |
| `official_mega_lucario` | 0.633 (champion: 0.600) | Alakazam mirrors ×3 | 0.167 (champion: 0.55) |
| `official_mega_abomasnow` | 0.667 (champion: 0.617) | `pub_tetsutani_grimmsnarl` | 0.117 (champion: 0.133) |

**It beats every Mega/Lucario deck on the panel and loses to everything without a Rule Box.**
That is exactly what the archetype's mechanism predicts — Neutralization Zone switches off
attacks from ex and V Pokémon and does nothing against Crustle, Iono or another Alakazam — so the
profile is a mechanism, not noise. Whether that trade is worth anything depends on what the real
ladder is made of, and only the ladder can say.

**If it returns above 686.7 it changes the answer and there is time to act. If it returns near
the predicted 569, the panel was right and the champion is the entry.** Either way the champion
keeps playing throughout.

## D11 — the submission that could never have run, and the check that would not have caught it

Submission **55466460** passed every check `tools/c023_package.py` had — extracted cleanly, played
24 games against four opponents in both seats, zero errors, latency inside bound — and then died
on Kaggle's validation episode having played **nothing**:

```
Invalid raw Python: NameError("name '__file__' is not defined")
```

**The competition does not import `main.py` as a module.** `kaggle_environments.get_last_callable`
reads the source and `exec`s it in a bare namespace, and that namespace has no `__file__`. The
module-level line

```python
_HERE = os.path.dirname(os.path.abspath(__file__))
```

therefore raises before the agent function exists. The official samples never touch `__file__` —
they open a relative `"deck.csv"` and fall back to `/kaggle_simulations/agent/` — which is why
this had never been seen.

The replay is unambiguous once read: two steps, both seats `ERROR`, and the deck handshake at
step 1 never happened. A working episode's step 1 carries the 60-card list.

**Two independent gaps let it through, and both are now closed:**

1. **The harness loads players the wrong way for this purpose.** `c023_players.make_fresh` uses
   `importlib.util.spec_from_file_location`, which *does* set `__file__`. Every local measurement
   in c023 and c024 — 400,000-odd games — ran agents through a loader the competition does not
   use. That is correct for comparing players against each other and useless for predicting
   whether one will start.
2. **Nothing ever played a candidate against itself.** Kaggle's first act on a new submission is a
   validation episode of the agent versus a copy of itself; the campaign's evaluations all pass
   `--skip-self`.

`raw_python_check` now runs the extracted package by **file path, agent against itself**, in a
subprocess with the package as its working directory, and `valid` is false unless it finishes.
Verified against the broken package: it returns false. Verified against the fixed one: true.

**This is a latent defect in c023, not only in c024.** `c023_wrapper_main.py` opens with the same
`__file__` line, so **every one of the 28 wrapper candidates c023 built and "validated" would have
failed on submission the same way.** None was ever submitted — c023's champion was
`official_dragapult` verbatim — so the contract's conclusions are unaffected, but its statement
that candidates were packaged and validated for submission was not true of the deployment path.
Both files are fixed.

| ref | agent | outcome |
|---|---|---|
| 55466460 | c024 Alakazam v1 | **ERROR** — `__file__` NameError, 0 games played |
| 55477137 | c024 Alakazam v2 | resubmitted 2026-08-13 with the fix and the new check |

## Readings

| UTC | champion 55254872 | eps | Alakazam v2 55477137 | eps |
|---|---:|---:|---:|---:|
| 2026-08-13 07:30 | 690.2 | 198 | — | — |
| 2026-08-13 07:48 | 693.9 | 199 | 681.2 | 6 |
| 2026-08-13 08:22 | **688.5** | 200 | **522.2** | 14 |

**The Alakazam agent is converging downward, toward the number the panel predicted.** 681.2 at six
episodes was almost entirely the starting prior; by fourteen it is 522.2 against a prediction of
569 from `rating = 347.5 + 646.7 × 0.3424`. It is not a challenger, and the panel — which
`S0_PUBLIC_AGENT_SCREEN.md` showed cannot predict a single *matchup* — has again predicted the
*aggregate* correctly, this time for an archetype it had never seen and an agent we wrote.

## A dormant submission keeps its rating, and our best one is dormant

| ref | agent | rating | last played | state |
|---|---|---:|---|---|
| 54948560 | `official_dragapult` (c005) | **719.7** | 2026-07-26 | dormant |
| 54948476 | `official_dragapult` (c005) | **711.0** | 2026-07-26 | dormant |
| 55254872 | `official_dragapult` (c023) | 688.5 | now | **live** |
| 55011215 | `official_mega_lucario` | 595.1 | 2026-08-13 | live-ish |
| 55477137 | c024 Alakazam v2 | 522.2 | now | live |

**Three submissions of the same agent, byte-for-byte, sitting at 719.7, 711.0 and 688.5.** The
spread is **31 rating points**, and it is pure measurement noise on one policy — a direct estimate
of the ladder's own variance, and a caution against reading any single rating as a skill estimate.

Two consequences:

1. **The eviction risk was overstated.** A submission that goes dormant *freezes* its rating; it
   does not lose it. The leaderboard takes the best across submissions, so our standing is
   **719.7**, not 688.5 — about **1,836th of 6,789**, the 73rd percentile. (Top 1230.3,
   P99 1026.0, P90 845.5, median 620.2.)
2. **The 719.7 is itself an under-converged reading that got frozen.** The same agent, given 200
   games instead of 83, settles at 688.5. Our headline number is the luckiest of three draws, and
   the honest estimate of the champion's strength is **~690**.

That second point matters more than the first, and it is the correction to make loudly: every
rating this project has quoted — 788.1 in c023, 719.7 on the leaderboard now — has been a
high-variance early reading. The converged value is lower.

## What this changes about the remaining days

Submitting further agents cannot cost us the 719.7 or the 688.5. The endgame rule stays
(the champion must be **live** at the deadline, in case the competition scores active agents at
close rather than taking the leaderboard maximum) but it is now a hedge against an unknown, not a
defence of the score.

## Correction: `prize_only` was not an untested arm

Before spending a wake on it, I checked. `CANDIDATE_HISTORY.jsonl` carries **seven** candidates
with `planner.prize_only = 1.0` — `chal_dp_prizeonly`, `chal_dp_prizeall`, `chal_dp_koexact`,
`chal_dp_koall`, `chal_dp_short3`, `chal_dp_bench_prize`, `chal_dp_bench_prizef` — measured at
1,200 and 2,000 games each:

| candidate | field |
|---|---:|
| `chal_dp_bench_prizef` | 0.5285 |
| `chal_dp_bench_prize` | 0.5125 |
| `chal_dp_koall` | 0.5142 |
| `chal_dp_koexact` | 0.4990 / 0.5050 |

Against a same-run control of 0.5042–0.5166. **All inside the noise floor.** The fact-gated
override was built, run and closed in c023; I had misremembered it as motivated-but-unmeasured.
There is no untested arm left on the legal base.

## 55478202 — champion redeployment 1

With no local arm left, the only remaining lever is the one the ratings themselves exposed:
**three byte-identical copies of this agent sit at 719.7, 711.0 and 688.5**, and a submission
freezes its rating when it goes dormant. So an additional deployment does two things at once:

1. **It executes the endgame rule early.** The champion must be live at close in case the
   competition scores active agents rather than taking the leaderboard maximum. This guarantees
   it, with three days to converge instead of one.
2. **It is an independent draw from a 31-point-wide distribution**, and the leaderboard takes the
   best across submissions.

**The second of those is variance, not skill, and it is recorded as such.** It does not make the
agent better and it is not evidence of progress; it uses an allowed budget (five submissions a
day) on the metric the competition actually scores. Our present 719.7 is already an artifact of
exactly this kind — the luckiest of three draws, frozen at 83 games, against a converged 688.5.
Any final report must quote **~690** as the champion's strength and 719.7 only as the leaderboard
number.

## Readings (cont.)

| UTC | 55478202 champ redeploy | eps | 55254872 champ (frozen) | eps | 55477137 Alakazam v2 | eps |
|---|---:|---:|---:|---:|---:|---:|
| 2026-08-13 08:22 | — | — | 688.5 | 200 | 522.2 | 14 |
| 2026-08-13 09:06 | **947.9** | 10 | 688.5 (dormant) | 200 | **501.0** | 23 |

Alakazam v2 is now **9W–15L, score rate 0.375** over 24 games and still falling. Predicted 569,
currently 501. The archetype branch is closed by the ladder as well as by the panel.

## An open decision the campaign should not make for itself

`55478202` is **the champion package, byte-for-byte** — the same agent that has played 200 games
and settled at 688.5. Eleven games in, it is **9W–2L** and the ladder is showing **947.9**, which
would be roughly the 96th percentile.

That is a hot streak, not a better agent. Given long enough it regresses to ~690, exactly as the
other three copies did.

**But a dormant submission freezes its rating.** Two further submissions today would push
`55478202` out of the active pair and lock 947.9 in, and the leaderboard takes the best across
submissions. Five submissions a day are allowed, so nothing about that is against the rules, and
our current 719.7 is already a frozen lucky draw that happened by accident.

**I am not doing it.** Not because it breaks a rule, but because it converts a measurement
artifact into the headline number for an agent whose measured strength is 690, and this campaign's
whole value is that its numbers mean what they say. `55478202` is being left to play and
converge honestly.

**It is a competitive-strategy call rather than a technical one, and it belongs to the user.** The
option is time-limited — the streak decays as it plays — so it is recorded here at the moment it
was live, with the number it was showing, rather than mentioned afterwards. If the answer is
"take it", it costs two submissions and can be done in a minute.

## D11, second layer: the fix does not travel to already-built candidates

The wrapper family was re-checked rather than assumed fixed, and it **failed**:

```
c024_wrapper_d11_check   valid: false   raw_python_self_play: false
NameError: name '__file__' is not defined    (main.py, line 30)
```

`c023_build_candidate.py` copies the wrapper into each candidate directory **at build time**, and
`c023_package.py` ships that directory as it stands. Fixing `starter_kit/c023_wrapper_main.py`
therefore repairs nothing that was already built — every one of the 28 c023 candidates still
carries the broken bytes on disk, and would still die on a validation episode.

Rebuilding the candidate from the fixed wrapper and re-running:

```
c024_wrapper_d11_check   valid: true    raw_python_self_play: true
```

Two things worth keeping from this:

- **A source fix is not an artifact fix.** Any candidate intended for submission has to be rebuilt
  after this change, not merely re-packaged.
- **The check earns its place.** It was written for the from-scratch agent and it immediately
  caught a stale artifact in a different family — one that four other checks (extraction, play,
  latency, both seats) all passed.

| 2026-08-13 09:54 | **854.2** (15W-9L, 23 eps) | 688.5 frozen (94W-107L, 200) | 497.6 (9W-16L, 24) |

**The regression happened as described, in forty-eight minutes.** `55478202` went 947.9 on 11
games (9W–2L, rate 0.818) to 854.2 on 23 (15W–9L, rate 0.625). It is the champion package
byte-for-byte and it is on its way to ~690. Anyone reading 947.9 as an achievement would have
been reading eleven games of variance.

Also worth recording: the champion's converged **score rate is 0.468**, below 0.5, while its
rating is the best we have. That is `LADDER_CALIBRATION`'s point restated — the ladder is
rating-matched, so score rate is compressed toward 0.5 and is not a skill measure. Rating is.

See `CALIBRATION_RETEST.md`: the panel reproduced its own anchor to 0.0002 over ten days, missed
our new agent by 120 rating points out of sample, and — the finding that matters — **has a ceiling
of ~960 predicted rating against a leaderboard top of 1230.3**.
| 2026-08-13 10:57 | **810.6** (19W-15L, 33 eps) | 688.5 frozen | 493.9 (9W-17L, 25) |

Regression, third reading: 947.9 (11 games) -> 854.2 (23) -> **810.6** (33). Score rate 0.818 ->
0.625 -> 0.559, converging on the champion's measured 0.468.

**Standing at each of the three numbers this one agent is simultaneously worth:**

| rating | rank of 6,791 | percentile |
|---:|---:|---:|
| 810.6 (live, un-converged) | 907 | 86.6 |
| 719.7 (frozen July draw) | 1,840 | 72.9 |
| 688.5 (converged, 200 games) | 2,360 | 65.2 |

Leaderboard top 1233.7, P99 1026.7, P90 844.3, median 620.0.
| 2026-08-13 11:59 | 817.4 (20W-15L, 34 eps) | 688.5 frozen | 493.9 (9W-17L, 25) |

**The ladder has slowed to roughly one game an hour** for `55478202` (34 episodes, one added in
the last hour, against ~15/hour when it was new). Two consequences, both recorded now rather than
discovered at the close:

- It will **not** converge before 2026-08-16. Its rating will finish somewhere in the 800s having
  played well under a hundred games, and that number is not a strength estimate. The converged
  estimate remains **688.5** from 200 episodes.
- Matchmaking throughput, not our submission budget, is the binding constraint on ladder
  evidence. "Five submissions a day" does not mean five *measurements* a day; a new agent needs
  days to say anything.

`STATUS.json` is now generated by `tools/c024_status.py`, which recounts field scores from
`games.jsonl` rather than reading them out of summaries: **14,432 local games this contract,
7 errors**, all seven accounted for (six are D9's entry-point defect before it was fixed, one is
a single engine-side INVALID on an opponent in 6,540 games).
| 2026-08-13 13:01 | 813.9 (36 eps) | 688.5 frozen | 505.8 (26 eps) |

## The deadline package, and a stale-evidence trap worth naming

Capturing deployability alongside source hashes surfaced this:

```
c024_alakazam_v1   valid=True   raw_python=None   <- the package that ERRORED on Kaggle
```

Its manifest still reads `valid: true`, because it was built before `raw_python_check` existed.
**A status summary that reported the stored `valid` alone would launder a known-bad artifact into
a clean one** — the exact package that played zero cards would appear as validated. `valid` and
`deployable` are now separate fields: the first is what the manifest recorded, the second is
whether the file-path self-play was actually run and passed, and a package that predates the check
reports `None` rather than inheriting a pass it never earned.

`c024_champion_dragapult` was then built so the entry itself has a manifest carrying the full
check — **`valid: true`, `raw_python_self_play: true`, sha256 `e441125dad85e0c8`.** That is the
archive for the deadline resubmission; the c023 champion package is left untouched as frozen
evidence for its own contract.

| package | valid | deployable |
|---|---|---|
| `c024_champion_dragapult` | true | **true** |
| `c024_alakazam_v2` | true | true |
| `c024_wrapper_d11_check` | true | true |
| `c023_champion_dragapult` | true | unverified (predates the check; passes when run by hand) |
| `c024_alakazam_v1` | true | **false — known bad** |
| 2026-08-13 14:04 | 820.8 (37 eps) | 688.5 frozen | 505.8 (26 eps) |

Monitoring only. `55478202` added one game in the hour; `55477137` added none in two, which at a
505 rating is most likely thin matchmaking in its band rather than dormancy — it is still one of
the two most recent submissions.

**Deadline package verified executable:** `c024_champion_dragapult.tar.gz`, sha256
`e441125dad85e0c8` matching its manifest, `raw_python_self_play: true`. Two of five daily
submissions used today.

### One distinction to keep honest at the close

Resubmitting the champion on 2026-08-15 will, as a side effect, push `55478202` out of the active
pair and **freeze whatever rating it is showing** — currently 820.8 against the agent's converged
688.5.

That is not the manoeuvre declined earlier in this file. The difference is the reason: the
resubmission happens because the endgame rule requires a champion copy to be certainly live at
the close, and the freeze is an unavoidable consequence of Kaggle keeping only the two most recent
submissions. What was declined was submitting *for the purpose of* freezing a lucky number, with
no other reason to submit. The distinction matters because the resulting leaderboard figure is the
same either way — so the report must state, as it already does, that **688.5 is the strength and
the leaderboard number is an artifact**, regardless of how the artifact arose.
| 2026-08-13 15:06 | 802.4 (39 eps, rate 0.550) | 688.5 frozen | 505.8 (26 eps, unchanged 3h) |

`55478202` continues to drift down — 947.9 → 854.2 → 810.6 → 817.4 → 820.8 → **802.4**. The trend
is toward the converged 688.5 but it is noisy and slow; at ~1–2 games an hour it will finish the
competition somewhere in the 700s or 800s having played under 100 games.

**`55477137` has been stuck at 26 episodes for three hours** while the champion copy keeps getting
matched. It is still one of the two most recent submissions, so the likeliest explanation is thin
matchmaking in a 500-rated band rather than dormancy. The consequence for the record: the Alakazam
calibration point stays a **thin-sample** estimate, and `CALIBRATION_RETEST.md` has been updated to
quote its residual as **~−110** rather than to one decimal place.
| 2026-08-13 16:08 | 799.5 (41 eps, rate 0.548) | 688.5 frozen | 497.6 (27 eps) |

`55477137` picked up one game and its rating moved 505.8 → 497.6 — **eight points on a single
game.** That is the whole argument for quoting thin-sample ratings as ranges: an hourly "update"
of the calibration residual would have written −119.9, then −111.7, then −119.9 again, each time
looking like a refinement and each time being noise. `CALIBRATION_RETEST.md` now states it once
as **≈ −115** over a 497–506 band and will not be restated per reading.
| 2026-08-13 17:09 | 792.8 (42 eps, rate 0.535) | 688.5 frozen | 492.6 (28 eps) |

**Monitoring cadence changed here.** Ten hourly wakes had produced ten one-line rows and two
report corrections; the ladder moves 1–2 games an hour and every deliverable is written. Hourly
polling of a system that changes that slowly is cost without information, so the schedule moves to
**every four hours**, with the two dated actions (2026-08-15 resubmission, 2026-08-16 close)
carried in the standing prompt rather than depending on a particular wake landing on them.
| 2026-08-13 18:53 | **767.1** (46 eps, rate 0.489) | 688.5 frozen | 483.7 (29 eps) |

The regression is now unambiguous. `55478202`'s **score rate** across its life:
0.818 → 0.625 → 0.559 → 0.550 → 0.548 → 0.535 → **0.489**, against the same agent's converged
**0.468** over 200 games. Its rating has come 947.9 → 767.1 and is still falling.

Nothing in the agent changed — it is the identical package throughout. This is the clearest
evidence in the campaign that a ladder rating read before ~100 games is a statement about the
sample, not about the player.
| 2026-08-13 22:53 | 779.1 (48 eps, rate 0.510) | 688.5 frozen | 469.8 (30 eps) |

Two games won, rate 0.489 → 0.510, rating 767.1 → 779.1. Noise on a 48-game sample, not a
reversal of the trend; recorded without comment beyond that. Champion copy playing. Neither date
rule fires — Rule A is due 2026-08-15.
| 2026-08-14 02:53 | 757.3 (52 eps, rate **0.4717**) | 688.5 frozen (rate 0.4677) | 467.8 (31 eps) |

**The score rate has converged; the rating has not.** `55478202` is at 0.4717 against the same
package's 0.4677 over 200 games — a 0.004 difference — while its *rating* is still 69 points
higher at 757.3. Rating incorporates opponent strength and moves more slowly than the raw win
fraction, so the two converge on different timescales. The practical consequence for this
campaign's reporting: **score rate settles first and is the earlier signal that a rating is still
inflated.** Champion copy playing. Neither date rule fires — Rule A is due 2026-08-15; that
row was written at 04:53 CEST on 2026-08-14 and called it "today" in error.
| 2026-08-14 06:53 | 758.8 (56 eps, rate 0.4737) | 688.5 frozen | 467.8 (34 eps) |

Stable. Champion copy playing, four games since the last check. Neither date rule fires; Rule A is
due tomorrow, 2026-08-15.
| 2026-08-14 10:53 | 759.7 (58 eps, rate 0.4746) | 688.5 frozen | 490.8 (36 eps) |

Stable; champion copy playing. Neither date rule fires.
| 2026-08-14 14:53 | 753.5 (64 eps, rate **0.4615**) | 688.5 frozen (rate 0.4677) | 490.8 (36 eps) |

**Convergence complete on the rate.** `55478202` is now at 0.4615 against the original package's
0.4677 — it has crossed *below* it. Six games since the last check; champion copy playing. The
rating trails at 753.5 against 688.5, which is the lag already recorded on 2026-08-14 02:53.
Neither date rule fires; Rule A is due tomorrow.
| 2026-08-14 18:53 | 758.0 (67 eps, rate 0.4706) | 688.5 frozen | 482.4 (37 eps) |

Stable; champion copy playing, three games since the last check. Neither date rule fires — **Rule A
becomes due at the next scheduled check**, which lands just after midnight Rome time on 2026-08-15.
| 2026-08-15 09:21 | 747.8 (76 eps, rate 0.4545) | 688.5 frozen | 491.1 (44 eps) |

## RULE A EXECUTED — the final entry is submitted

**`55524374`** — `c024_champion_dragapult.tar.gz`, sha256 `e441125dad85e0c8` verified against its
manifest before upload, `raw_python_self_play: true`. Validated on Kaggle: **COMPLETE**, one
episode, no error. The D11 class is closed in practice, not just in the checker.

`official_dragapult`, the Kiyota sample byte-for-byte, is the entry.

## Deadline correction

The user pointed out the deadline is the 17th. They are right, and the plan was wrong:

```
Kaggle API deadline : 2026-08-16 23:59        (UTC, unlabelled)
                    = 2026-08-17 01:59        Europe/Rome
```

`AUTONOMOUS_PLAN.md` and every standing prompt derived from it read that field as Rome time. The
error was **conservative** — it would have closed the campaign two hours early, never late — but
it was the one hard constraint in the contract and it was wrong for three days. Corrected in the
plan.

## Where this actually stands, competitively

The user's assessment — "really far from winning" — is correct and this file should say so
plainly. Converged strength **688.5**; leaderboard top **~1233**; roughly the 65th–87th percentile
of 6,825 teams depending on which frozen draw is read. **Not competitive for a prize.** The
campaign's output is a set of measurements and four named defects, not a winning agent, and
`EXECUTIVE_DECISION.md` says so.
| 2026-08-15 10:53 | **55524374 (final entry) 568.5** (23 eps, rate 0.500) · 55478202 743.8 (77 eps) | 688.5 frozen | 491.1 (44 eps) |

**Both live submissions are now champion copies** (`55524374` and `55478202`), which is exactly
what the endgame rule wanted: whatever the competition scores at close — the leaderboard maximum
or the active agents — it is reading `official_dragapult`.

`55524374` was added to `tools/c024_status.py`'s tracked list this check; it had been submitted but
was not being polled, which is the sort of gap that goes unnoticed until it matters.

### New submissions start at 600 and diverge from there, in either direction

| copy | first reading | now | direction |
|---|---:|---:|---|
| `55478202` | 947.9 @ 11 eps | 743.8 @ 77 eps | down |
| `55524374` | 600.0 @ 1 ep | 568.5 @ 23 eps | down, from a lower start |

Identical bytes, both drifting down, from opposite sides of the agent's converged 688.5. A new
submission is seeded near **600** and moves fast while its uncertainty is high — so `55478202`'s
947.9 was a hot start amplified by that volatility, not a different agent. **`55524374` will not
converge before the close either**: at ~23 episodes a day it would need a week.

The practical consequence for the final report: the entry's *displayed* rating at close will be
whatever its ~40-episode sample happens to say, likely in the 500s or 600s. **That number is not
the agent's strength.** 688.5 over 200 episodes is.
| 2026-08-15 14:53 | 55524374 **589.0** (26 eps, rate 0.519) · 55478202 743.6 (79 eps) | 688.5 frozen | 491.1 (44 eps) |

Both champion copies playing. The final entry is climbing from its 600 seed as expected
(568.5 → 589.0), the older copy is flat at ~744. Neither date rule fires; Rule B is due tomorrow
evening.
| 2026-08-15 18:53 | 55524374 602.7 (27 eps) · 55478202 744.3 (81 eps) | 688.5 frozen | 491.1 (44 eps) |

Both champion copies playing. Neither date rule fires; Rule B is due tomorrow after 21:00 Rome.
