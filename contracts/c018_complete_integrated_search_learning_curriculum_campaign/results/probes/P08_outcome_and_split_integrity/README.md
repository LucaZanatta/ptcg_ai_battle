# P08 — Outcome and split integrity

Every one of 47,086 decision rows carries the terminal result of *its own* game: 0
disagreements against the per-game record, 0 null outcomes. The value head therefore regresses
on real game results, not on placeholders.

**Splits are by game, not by decision.** 0 games straddle a split boundary.
Decision-level splitting would put earlier and later turns of the same game on both sides of the
train/test line and inflate held-out agreement, because consecutive decisions in one game share
almost all of their state. Split sizes: {'train': 32930, 'validation': 6721, 'test': 7435}.

Seats are balanced ({0: 24362, 1: 22724}) and the opponent mix is
dragapult=12,235, mega_abomasnow=12,127, mega_lucario=11,745, iono=10,979; the generator won
23.4% against that mixed field.

**Status: PASS.**
