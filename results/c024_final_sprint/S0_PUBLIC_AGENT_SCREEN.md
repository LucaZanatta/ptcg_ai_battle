# S0 — what the public state of the art actually measures at

Twelve public kernels were selected on one criterion the c023 panel never used: **the author
advertises a ladder rating in the notebook title.** Nine extracted to a runnable
`(main.py, deck.csv)` without executing any kernel code; three did not (one is a markdown-only
write-up, two hide their payload in a shape no extractor here reads).

All nine were run against the full c023 panel — 4 official samples and 7 community agents — at
60 games per ordered pair, 6,540 games, **1 error**, in one harness under one protocol. Our
champion `official_dragapult` was entered as a candidate in the same run so it is measured on
exactly the same games.

## The two rankings disagree, and the disagreement is the finding

| agent | claimed | off-mirror field | **ladder-weighted** | vs Grimmsnarl | vs our champion |
|---|---|---:|---:|---:|---:|
| `pub_romanrozen_v10_950` | LB 950+ | **0.6197** | 0.3908 | 0.200 | **0.450** |
| `pub_prvsiyan_tusk_1208_v24` | 1208 | 0.5182 | 0.3760 | 0.233 | 0.333 |
| **`official_dragapult` (ours)** | 788.1 | 0.4967 | **0.2606** | **0.133** | — |
| `pub_soutasakurai_libraryout_1208` | 1208 | 0.4933 | 0.2880 | 0.100 | 0.333 |
| `pub_masamikobayashi_archaludon` | 1300 Starmie author | 0.4515 | 0.3938 | 0.350 | 0.717 |
| `pub_aristophanivan_multiply_940` | 940 | 0.4439 | **0.4530** | **0.500** | 0.667 |
| `pub_penguin069_915` | 915 | 0.4280 | 0.3880 | 0.383 | 0.633 |
| `pub_borealis27_1050` | 1050 | 0.4205 | 0.3978 | 0.417 | 0.683 |
| `pub_ryotasueyoshi_alakazam_5th` | best 5th place | 0.3455 | 0.2907 | 0.250 | 0.317 |
| `pub_prvsiyan_lopunny_1208` | 1208 | 0.2386 | 0.3077 | 0.383 | 0.517 |
| `pub_tetsutani_grimmsnarl` *(c023 run)* | — | 0.6347 | **0.6631** | — | 0.675 |

`field_ladder_weighted` weights each opponent by how often its archetype actually appears in the
1000+ ladder bands (`META_REPORT` §2). Marnie's Grimmsnarl carries 0.60 because it is 58.8% of
the 1100+ band.

**Read down the ladder-weighted column and it is almost entirely one matchup.** Our champion is
last at 0.2606, and it is last because it scores **0.133 against Grimmsnarl** — the worst cell
on the board. `pub_aristophanivan_multiply_940`, which advertises the *lowest* rating of the
nine and sits 5th on raw field score, is **first** on the ladder-weighted metric, purely because
it splits the Grimmsnarl matchup 0.500.

## Three things this kills

- **The claimed ratings do not transfer to this panel.** Two agents titled "1208" score 0.4933
  and 0.2386; the "best 5th place" Alakazam scores 0.3455, below our champion. Either the panel
  is unrepresentative of what those agents were tuned against, or the titles are stale — but a
  title is not a measurement and none of these should be treated as one.
- **The raw field score is the wrong instrument.** It is a round-robin average and compresses
  toward 0.5 for exactly the reason `LADDER_CALIBRATION.md` gives for ladder score rate. It
  ranks `romanrozen` first and our champion third; weighted by what you actually meet above
  1000 rating, that ordering inverts.
- **`EXCHANGE_RATE.md` misvalues at least two archetypes.** It ranks Alakazam 16/22 (its headline
  attack has 0 printed damage and scales with hand size, which the metric cannot score) and it
  cannot score a wall deck at all. Use it to *order* candidates, never to justify a bet.

## The one thing it suggests — and the check that stops it becoming a bet

**Our champion's worst cell is the most common deck on the ladder.** 0.133 against the panel's
Grimmsnarl, against a 60% ladder weight. `pub_tetsutani_grimmsnarl` scores **0.6631**
ladder-weighted against our **0.2606**; at 6.47 rating points per local point that reads as a
~260-rating difference, which is the whole gap from our 788 to the top 1%.

**That reading does not survive its own counter-evidence.** On 83 *real* Kaggle ladder games the
champion went **4W–6L against Marnie Grimmsnarl — 0.400, not 0.133**. The panel's tetsutani is a
much stronger implementation than the Grimmsnarl you actually meet, so 0.133 is a property of one
sparring partner, not of the matchup.

So the question is whether a panel *cell* predicts a ladder *cell* at all. `LADDER_CALIBRATION.md`
validated the panel only in aggregate — four agents, field score against rating, R² = 0.987. It
never validated a single matchup. Tested here for the first time, on the four archetypes where
both numbers exist:

| archetype | real ladder | real 95% CI | panel | CIs overlap? |
|---|---:|---:|---:|:--:|
| Marnie Grimmsnarl | 0.400 (n=10) | [0.168, 0.687] | 0.133 | yes |
| Crustle Wall | 0.222 (n=9) | [0.063, 0.547] | **0.567** | yes |
| Alakazam | 0.737 (n=19) | [0.512, 0.882] | 0.561 | yes |
| Mega Lucario | 0.467 (n=15) | [0.248, 0.699] | 0.406 | yes |

**Spearman −0.200. Pearson 0.163. Mean absolute error 0.212.** Grimmsnarl and Crustle disagree in
*opposite* directions — the panel says Crustle is our second-best matchup at 0.567 while the real
ladder says it is our worst at 0.222.

Every CI overlaps, so the panel is not refuted per cell either; the ladder side is 9–19 games
wide. The honest status is **UNMEASURED, not validated**: with four points, a near-zero rank
correlation and ±0.25-wide intervals, `field_ladder_weighted` — which is ~60% one 60-game cell —
**is not a decision instrument for a multi-day archetype bet.**

The consequence is operational, not philosophical. The instrument that can settle this is the
ladder, at 5 submissions a day, and it costs a day of latency per reading. So the campaign spends
its first candidate on something buildable on the *legal* base and submittable inside two days,
and lets the ladder — not the panel — decide whether an archetype rewrite is worth the remaining
week.

## Provenance and reuse

Every kernel here stays `LOCAL_BENCHMARK_ONLY`. Verified again on a fresh pull: `kernels_list`
exposes no licence field, `kernels_pull` writes a `kernel-metadata.json` with no `licenseName`,
and the notebook page is JavaScript-rendered so it cannot be read from here. These are opponents
and sources of *technique described in prose*, never a submission base. Nothing in this campaign
copies kernel code.

## Defects found while building this

- **D8 — the flattener lost cell boundaries.** `_writefile_cell` splits on a `#%%CELL%%` marker
  and returns everything after the magic line *in the cell it matched*. Joining cells with a bare
  blank line made the whole notebook one cell, so `%%writefile deck.csv` handed back the entire
  remaining notebook, which parses as a deck only when the deck happens to be the last cell.
  Cost four extractions and looked like "these kernels use an unknown format".
- **D9 — a kernel whose entry point is not called `agent`.** `pub_prvsiyan_lopunny_1208` declares
  `EXPECTED_FINAL_CALLABLE = 'mega_lopunny_cleanroom_entrypoint'` and leaves the binding to its
  own builder. The module imported cleanly and every decision then raised `AttributeError`: six
  errored games, no score. Fixed by binding the kernel's own declared name, and by making the
  loader *raise* rather than guess when no `agent` exists.
- **The trivial-fallback probe was run on all nine before any of these numbers were read.**
  Agreement with the first-k fallback ran 0.35–0.60, in band with agents known to be working; no
  agent was silently playing its fallback.
