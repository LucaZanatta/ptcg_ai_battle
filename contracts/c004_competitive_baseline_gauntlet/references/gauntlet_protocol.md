# Competitive Gauntlet Protocol

## Core principles

1. Compare complete deck–agent pairs.
2. Freeze candidates before official evaluation.
3. Balance both seat orientations.
4. Treat attributable invalid actions, exceptions, and timeouts as losses and reliability defects.
5. Do not treat exposed engine seeds as trajectory control.
6. Use uncertainty intervals and sequential stopping.
7. Preserve raw game-level results.
8. Select a primary and backup using a predefined rule.
9. Do not strategically modify candidates during baseline selection.
10. Finish with an actionable next hypothesis.

## Recommended calculations

- Draw = 0.5 result.
- Seat-balanced win rate = equal-weight mean of the candidate’s win rate as seat 0 and seat 1.
- Pairwise interval = Wilson interval or stratified bootstrap; document exact method.
- Global model = Bradley–Terry or justified equivalent.
- Bootstrap ranking = at least 2,000 resamples.
- Worst matchup = minimum conservative lower bound among opponents.
