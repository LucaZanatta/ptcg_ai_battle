# c005 Winning-Oriented Review

## Accepted

- Official Dragapult selected as the first distillation teacher.
- Official Mega Lucario is a near-tied competitive benchmark.
- Submission A Dragapult package is technically valid.
- The c005 teacher dataset is suitable as a starting behavioral-cloning dataset.
- The teacher/deck/source lineage is frozen.

## Required c006 corrections

1. Rebuild ordered game sequences and preserve decision indices.
2. Compare a stateless model with a recurrent model.
3. Use a full legal-card vocabulary.
4. Use semantic decision importance, not SelectContext alone.
5. Train compact models below one million parameters.
6. Implement context-aware multi-select decoding.
7. Use gameplay non-inferiority as the main selection gate.
8. Do not run RL until a student is non-inferior to the frozen teacher.
9. Do not submit a student merely because training completes.

## Important interpretation

Dragapult is the selected official-sample teacher, not conclusively the best public agent in the entire competition.
