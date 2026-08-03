# The first local↔ladder calibration this project has had

Every strength claim this repository has made for eleven contracts has been a *local* field score
against a panel we assembled, while the competitive objective is a Kaggle rating. Nothing has ever
measured the function between them, and `UNRESOLVED_RISKS.md` R1 says so.

The Kaggle episode API closes part of that gap. Every public game a submission plays is
retrievable as a replay, so a submitted agent's **real ladder score rate** is a measurable
quantity — not a rating, which moves and is rating-matched, but the plain fraction of public games
it actually won.

## All four submissions this project has made, as the ladder recorded them

| submission | agent | archetype played | ladder score rate | public games | rating |
|---|---|---|---:|---:|---:|
| 54948560 | `official_dragapult` (c005) | Dragapult, 83/83 | **0.5783** | 83 | 719.7 |
| 55011215 | `official_mega_lucario` (c017) | Mega Lucario, 157/157 | **0.4904** | 157 | 593.3 |
| 55005237 | c015 anti-meta expert | Iono's Bellibolt, 107/107 | **0.4206** | 107 | 390.7 |
| 55004756 | c014 Archaludon expert | Archaludon, 33/33 | **0.3333** | 33 | 471.4 |

380 public games, all parsed, zero errors. Every agent played the archetype it was built for in
every game — which is also a check on the classifier: it recovered our own deck correctly 380
times out of 380.

**Note the inversion.** c014 has the *higher rating* (471.4 vs 390.7) and the *lower* score rate
(0.3333 vs 0.4206). Ratings are timestamped snapshots of a moving quantity, they are earned
against rating-matched opponents, and c014's is over 33 games. This is the clearest illustration
in this campaign of why a single rating reading establishes nothing — the rule c015 §16 and c016
§21 both wrote down, now visible in our own four data points.

## Two anchors

| agent | local field (off-mirror) | **ladder score rate** | games | rating at the time |
|---|---:|---:|---:|---:|
| `official_dragapult` (ref 54948560) | 0.4653 | **0.5783** | 83 | 719.7 |
| `official_mega_lucario` (ref 55011215) | 0.3521 | **0.4904** | 157 | 593.3 |
| difference | **0.1132** | **0.0879** | | **126.4** |

Both parsed with zero errors; both agents' own archetype was confirmed from the replays (Dragapult
83/83, Mega Lucario in every game it played).

## What the two points imply

Taken literally, and they should not be taken more than literally:

- **1 point of local field score ≈ 0.78 points of ladder score rate.** The local panel is the
  harder measurement — it contains public community agents that score 0.60–0.64 against each
  other, a stronger field than a 600–720-rated agent actually meets.
- **1 point of local field score ≈ 11 rating points.** So this contract's registered promotion
  target of ~+4 local points is worth roughly **+45 rating**, and the ~535 points between our
  champion and the top of the leaderboard would need something like **+48 local points** — five
  times the entire spread between the best and worst official sample.

That last number is the most useful thing in this file. It says plainly that no amount of local
rule surgery on a sample agent reaches the top of this leaderboard, and it says it with a
measurement rather than with a shrug.

## What this is not

- **Two points is a slope through two points.** It has no error bar, the two readings were taken
  at different times against different ladder populations, and the relationship is certainly not
  linear over a 500-point range.
- **A ladder score rate is not a rating.** Matchmaking pairs by rating, so a strong agent keeps
  winning about 60% and climbs slowly; keidroid measured a ~1155-rated agent at 61.2%. The gap
  between 57.8% (us, 719.7) and 61.2% (them, ~1155) is 3.4 percentage points for 435 rating.
- **These are the two *official samples* we submitted.** c014's and c015's records are recorded
  alongside for completeness, but they are custom agents at 471.4 and 390.7 and say more about
  those contracts than about this mapping.
