# Frozen Claude prompt (§38)

```
You are choosing one action in a Pokemon Trading Card Game position.

You see ONLY what a player legally sees at this moment. You do NOT see the opponent's hand,
the deck order, future randomness, any other agent's choice, or how the game turns out. Do
not speculate about hidden cards as if you knew them.

Choose the single best legal action, then rank the legal actions from best to worst.

Position:
{state}

Reply with ONE JSON object and nothing else, matching exactly this schema:
{{"state_id": "<the state_id above>",
  "selected_action_id": "<one action_id from legal_actions>",
  "ranked_action_ids": ["<action_id>", ...],
  "confidence": <number 0..1>,
  "strategic_tags": ["<short tag>", ...],
  "short_rationale": "<one or two sentences, no hidden information>"}}

Rules: selected_action_id must appear in legal_actions; ranked_action_ids must contain only
legal action_ids with no duplicates; confidence in [0,1]; rationale concise.
```
