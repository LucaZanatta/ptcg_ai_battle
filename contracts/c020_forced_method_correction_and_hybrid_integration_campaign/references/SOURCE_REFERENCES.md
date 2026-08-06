# Primary Source References

Record retrieval time, URL, version/commit where available, snapshot/hash, and exact properties used.

## Official PTCG API

- Local repository: `starter_kit/api.py`
- Required forward API: `search_begin`, `search_step`, `search_release`, `search_end`.
- Official competition/starter-kit rules remain highest authority for legal information and packaging.

## Hearthstone MCTS implementation patterns

- Peter1591, `hearthstone-ai`
- https://github.com/peter1591/hearthstone-ai
- MCTS documentation: https://peter1591.github.io/hearthstone-ai/agents/include/MCTS/
- Training/search notes: https://peter1591.github.io/hearthstone-ai/agents/train/gcc7/reinforcement_learning/

Use for algorithmic patterns only under the clean-room policy. Do not copy GPL source into the competition package.

## Hearthstone MCTS paper

- Świechowski, Tajmajer, Janusz, “Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms.”
- https://arxiv.org/abs/1808.04794

Relevant properties:

- imperfect-information/random-effect search;
- PIMC/ISMCTS discussion;
- search plus state evaluation;
- better evaluation improving win rate and reducing computation.

## ByteRL LOCM paper

- Xi et al., “Mastering Strategy Card Game (Legends of Code and Magic) via End-to-End Policy and Optimistic Smooth Fictitious Play.”
- https://arxiv.org/abs/2303.04096

## ByteRL Hearthstone transfer

- Xiao et al., “Mastering Strategy Card Game (Hearthstone) with Improved Techniques.”
- https://arxiv.org/abs/2303.05197
- Readable HTML: https://ar5iv.labs.arxiv.org/html/2303.05197

Preserve:

- masked end-to-end policy/value;
- recurrent memory;
- actor-learner execution;
- V-trace;
- UPGO;
- gamma 1.0;
- OSFP historical population and payoff-driven mixture.

## V-trace / IMPALA

- Espeholt et al., “IMPALA: Scalable Distributed Deep-RL with Importance Weighted Actor-Learner Architectures.”
- https://arxiv.org/abs/1802.01561

## Competition context

- LOCM competition summary: https://arxiv.org/abs/2305.11814
- COG 2022 competition material: https://legendsofcodeandmagic.com/COG22/COG2022-slides.pdf

## Authority order

1. Official PTCG API and competition rules.
2. Primary papers.
3. Hearthstone repository for non-copied implementation patterns.
4. c019 code only as control/negative evidence.
