# PIVOT_LEDGER

Major redirections of this campaign, with the evidence that forced each one.

---

## P1 — the champion is `official_dragapult`, not `official_mega_lucario`

**Previous hypothesis.** c016 named `official_mega_lucario` its best candidate, and c022 used it
as the frozen bar. The starting interpretation this contract inherited would have built every
challenger on it.

**Evidence against.** c016's panel never ran `official_dragapult` as a *candidate* — only as an
opponent — so the two were never compared. The Kaggle ladder disagreed with the label the whole
time: dragapult 719.7 against mega_lucario 593.3. c023's own 8,000-game round-robin, with every
player measured on one panel by one harness, settles it:

| submission-eligible base | off-mirror field score |
|---|---:|
| **`official_dragapult`** | **0.4653** |
| `official_mega_abomasnow` | 0.3625 |
| `official_mega_lucario` | 0.3521 |
| `official_iono` | 0.3431 |

**Replacement hypothesis.** Build on `official_dragapult`.

**Expected value.** Decisive. Every downstream hour is spent on the right base; forty hours on the
wrong one would have been unrecoverable.

**Cost.** 8,000 games, ~25 minutes of wall clock.

**Validation.** `champion.json` and `MATCHUP_MATRIX.csv`, both recomputed from `games.jsonl` by
validator check V07.

---

## P2 — the panel is the ladder's meta, not the four official samples

**Previous hypothesis.** Prior contracts evaluated against the four official sample agents.

**Evidence against.** Those four score 390–720 on a ladder whose median is 637.8 and whose top is
1262.2 (`META_REPORT §1`). Tuning against them optimises a function whose ceiling is roughly the
ladder's median. Worse, the archetype census shows what the panel was *missing*: **Marnie's
Grimmsnarl ex is 58.8% of the 1100+ band and 61.1% of 1000–1099**, and no official sample plays
it or resembles it.

**Replacement hypothesis.** Add public community agents as opponents — one Grimmsnarl, three
Alakazam, two Mega Lucario derivatives — and report a ladder-usage-weighted field score alongside
the unweighted one.

**Expected value.** High and already realised: the champion's worst matchup on the enlarged panel
is `pub_tetsutani_grimmsnarl` at **0.250**, which is invisible on a four-sample panel and is the
single most valuable thing to fix.

**Cost.** Kernel retrieval and extraction, ~40 minutes.

**Validation.** `SOURCES.md` (reuse classes), `MATCHUP_MATRIX.csv`, `PANEL_SPLIT.json`.

**Constraint carried.** Community agents enter as **opponents only**. `SOURCES.md` classifies
every one of them `LOCAL_BENCHMARK_ONLY`: no licence is exposed by the Kaggle API, and c016 §12
forbids inferring permission from visibility. Their **deck lists** are `CONFIGURATION_NOT_CODE`
and are usable.

---

## P3 — deck co-optimization killed; the headroom is in the agent

**Previous hypothesis.** Branch B2: constrained count mutations around the official list would
buy a few points cheaply.

**Evidence against.** Seventeen mutations, screened at 400 games and confirmed at 1,200. The best
screen arm went **+7.25 → −0.12** between the two. Nothing separated from a control measured in
the same run. Full table in `DECK_CHANGE_LEDGER.md`.

**Replacement hypothesis.** Spend the remaining hours on agent behaviour, and specifically on the
Grimmsnarl matchup, which `PANEL_SPLIT.json` pre-registered as a promotable target on its own.

**Expected value.** The external evidence points the same way: `makthanithin`'s Mega Lucario
agent claims 1084.5 on a deck five counts from its official sample, while that sample scores
593.3. Same 60 cards, different agent, ~490 rating points.

**Cost.** 14,000 games, ~17 minutes of wall clock. Cheap, and it bought a real answer.

**Validation.** `deck_screen1` and `deck_confirm1` raw games; validator V01 recomputes both.

---

## P4 — the planner's work budget is a count, not a clock

**Previous hypothesis.** The turn planner would spend a 120 ms wall-clock budget per decision.

**Evidence against.** No new experiment — a standing lesson from this repository. A search with a
per-decision *time* budget does not merely run slower under CPU contention, it silently explores
fewer lines and scores worse, and the output says nothing about it. That artefact has corrupted
results in three prior contracts, once inverting a ranking by 49 points.

**Replacement hypothesis.** Effort is set by `max_root_options × max_turn_steps`; the wall clock
becomes a 700 ms safety valve that should almost never bind. An arm then gets *slower* on a busy
machine and never weaker, and deployment latency is measured separately in a quiet window.

**Expected value.** Protects every planner comparison in the campaign from a known,
previously-paid-for measurement error.

**Cost.** One constant, and re-running the arms measured under the old budget.

**Validation.** `plan_screen1` was run under the old time budget and is reported as a *screen*;
the decisive planner arms are re-run count-budgeted.
