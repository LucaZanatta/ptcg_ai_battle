# P03 — Hidden-information audit

Search cannot begin without *predicting* the opponent's deck, prizes, hand and face-down Active.
That is the whole risk: a determinizer that peeks would produce a search that looks brilliant
offline and is illegal in the competition. So the audit covers the determinizer, not only the
state reader.

**Static.** `tools/c018_search.py` routes every state read through `VisibleView`, which exposes
only own hand, both boards, both discards and public counts. `opponent_hand_ids`, `deck_list`
and `prize_ids` exist solely to raise `HiddenInformationAccess` — 3
raise sites. The determinizer receives a `VisibleView`, never the raw observation, so a peek is a
crash rather than a silent advantage.

**Runtime.** 0 violations across 42,857 search
roots in 900 games. Predicted opponent contents were drawn from public archetype
decklists (dragapult=10,707, mega_lucario=10,540, mega_abomasnow=10,513, iono=9,926, unknown=1,171), i.e. *guessed* from the
public metagame, not read from the live game.

**Status: PASS.**
