# The local panel predicts Kaggle rating with R² = 0.987

Eleven contracts of this project have measured strength as a *local* field score against a panel
we assembled, while the competitive objective is a Kaggle rating. Nothing had ever measured the
function between them. `UNRESOLVED_RISKS.md` R1 says so.

This closes it.

## The measurement

Four agents this project has actually submitted, each measured **on the same 13-player panel, at
2,400 games**, against the rating the Kaggle ladder gave it:

| agent | local field (off-mirror) | ladder score rate | public games | **Kaggle rating** |
|---|---:|---:|---:|---:|
| `official_dragapult` | **0.5708** | 0.5783 | 83 | **719.7** |
| `official_mega_lucario` | **0.3952** | 0.4904 | 157 | **593.3** |
| c014 Archaludon expert | **0.1583** | 0.3333 | 33 | **471.4** |
| c015 anti-meta expert | **0.0900** | 0.4206 | 107 | **390.7** |

Ladder score rates come from 380 of our own public replays, parsed with zero errors; each agent
played the archetype it was built for in every one of its games.

```
Kaggle rating  =  347.5  +  646.7 × local_field_score            R² = 0.9872
```

| agent | predicted rating | actual | residual |
|---|---:|---:|---:|
| `official_dragapult` | 716.6 | 719.7 | **+3.1** |
| `official_mega_lucario` | 603.0 | 593.3 | −9.7 |
| c014 Archaludon | 449.8 | 471.4 | +21.6 |
| c015 anti-meta | 405.7 | 390.7 | −15.0 |

**Four agents, 330 rating points of spread, and the local panel orders all four correctly with a
worst-case residual of 22 rating points.**

## The inversion, and why it resolves in the panel's favour

I expected this to get *messier*, because c015 scores the **lowest** local field of the four
(0.0900) and a **higher ladder score rate** than c014 (0.4206 against 0.3333). Written down as a
prediction before the run: "the four-point calibration collapses back to two clean points plus two
that disagree."

It did not, and the reason is worth more than the calibration itself:

| ordering by | agrees with local? |
|---|---|
| **Kaggle rating** | **yes — all four, exactly** |
| ladder score rate | **no** — c015 and c014 swap |

**A ladder score rate is rating-matched and therefore compressed toward 0.5.** A weak agent is
paired with weak opponents and wins a respectable fraction of its games; a strong agent is paired
with strong opponents and does the same. c015 has a 0.42 score rate because it plays 390-rated
opponents, not because it is any good — its local field score against a fixed panel is 0.0900, the
worst of the four, and its rating is likewise the worst of the four.

So the local panel was right and the ladder score rate was the misleading number. **Rating is the
dependent variable; score rate is not.** That is a correction to §"Two anchors" as it was first
written here, and it is the reason the earlier two-point estimate (≈11 rating per local point,
from score rates) is superseded by the four-point one below.

## What it costs to move

**6.47 rating points per local point** (one local point = 0.01 of field score).

| target | rating gap | local points required |
|---|---:|---:|
| this contract's registered promotion target | ~+26 | +4 |
| P90 of the ladder (836.1) | +116 | +18 |
| P99 (1035.6) | +316 | +49 |
| **top of the leaderboard (1254.3)** | **+534.6** | **+82.7** |

For scale, **+82.7 local points is more than the champion's entire field score.** The whole spread
between the best and the worst official sample is about 22 points; between the champion and the
strongest agent on this panel, about 7.

That is the sentence this campaign exists to be able to say: *the gap to the top of this
leaderboard is roughly eighty local points, the local panel measures the right quantity to within
about twenty rating points, and no local modification of a hand-written expert moves it.*

## What this is not

- **Four points and a straight line.** R² = 0.987 on four observations is not a validated model;
  it is four points that happen to lie near a line. It should not be extrapolated past the range
  measured (390–720 rating), and the top-of-leaderboard figure above is an extrapolation of
  exactly that kind — quoted as an order of magnitude, not a target.
- **Ratings are timestamped snapshots** of a live quantity that moved 150+ points inside an hour
  for c014 in c015's own records. These four were read on 2026-08-03.
- **The panel is ours.** It predicts rating well *because* it was built to be meta-representative —
  one Grimmsnarl, three Alakazam, two Mega Lucario derivatives, a Crustle wall and the four
  samples. A panel of only official samples would not have done this.
