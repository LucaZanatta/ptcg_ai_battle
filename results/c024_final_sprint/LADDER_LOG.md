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
