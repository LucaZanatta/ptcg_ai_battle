# Frozen prompt (§26/§28)

```
You are choosing one action in a Pokemon Trading Card Game position.

Everything below is information the acting player can legally see. You do NOT see the
opponent's hand, the deck order, future randomness, any other agent's choice, or the eventual
result. Do not reason about hidden cards as though you knew them.

Each legal action is described with its type, the card involved, that card's text, and what it
targets. Choose the single best legal action and then rank the legal actions best to worst.
Your rationale must refer to the cards and effects actually shown.

POSITION
{state}

Reply with ONE JSON object and nothing else:
{{"state_id": "<the state_id above>",
  "selected_action_id": "<an action_id from legal_actions>",
  "ranked_action_ids": ["<action_id>", ...],
  "confidence": <number between 0 and 1>,
  "strategic_tags": ["<short tag>", ...],
  "short_rationale": "<one to three sentences naming the cards or effects that drove the choice>"}}

Rules: selected_action_id must appear in legal_actions; ranked_action_ids may contain only
legal action_ids with no duplicates; confidence in [0,1].
```
