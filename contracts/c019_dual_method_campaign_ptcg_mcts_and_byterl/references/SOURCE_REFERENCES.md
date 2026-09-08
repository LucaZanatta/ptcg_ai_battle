# Primary source references and authority order

Record retrieval date and snapshots/hashes in c019 results. These URLs identify the intended algorithms; they do not grant automatic code-reuse permission.

## A. Hearthstone-style MCTS

### Source repository

- Peter1591, `hearthstone-ai`
- https://github.com/peter1591/hearthstone-ai
- Documentation: https://peter1591.github.io/hearthstone-ai/agents/include/MCTS/
- Reinforcement-learning notes: https://peter1591.github.io/hearthstone-ai/agents/train/gcc7/reinforcement_learning/

Relevant published properties:

- Multiple-Observer / information-set treatment of hidden information.
- Tree nodes shared for identical boards.
- Policy network used to prioritize promising actions.
- Default/rollout network used during simulation.
- Value estimate used for early cutoff.
- Selection, expansion, simulation, and backup over real game successors.

### Supporting paper

- Świechowski, Tajmajer, Janusz, “Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms.”
- https://arxiv.org/abs/1808.04794

### ISMCTS foundation

- Cowling, Powley, Whitehouse, “Information Set Monte Carlo Tree Search.”
- Use the paper linked from the Hearthstone MCTS documentation. Save the exact resolved URL in c019 source snapshots.

## B. ByteRL / OSFP

### LOCM ByteRL paper

- Xi et al., “Mastering Strategy Card Game (Legends of Code and Magic) via End-to-End Policy and Optimistic Smooth Fictitious Play.”
- https://arxiv.org/abs/2303.04096

### Hearthstone transfer and implementation details

- Xiao et al., “Mastering Strategy Card Game (Hearthstone) with Improved Techniques.”
- https://arxiv.org/abs/2303.05197
- Readable HTML mirror: https://ar5iv.labs.arxiv.org/html/2303.05197

Important details to preserve:

- end-to-end masked policy and value network;
- LSTM state size 256 in the published Hearthstone system;
- actor-learner architecture;
- V-trace value targets;
- UPGO auxiliary policy loss;
- V-trace/PPO-clipped policy gradient improvement;
- discount `gamma = 1.0`;
- learning rate `7e-5` as source default;
- entropy weight `0.01`;
- sample reuse `2`;
- V-trace c/rho clipping `[0.001, 1.007]` in the Hearthstone adaptation;
- OSFP current-self-play probability `p = 0.6`;
- historical promotion threshold `xi = 0.55`;
- force-add after more than `c = 6` learning periods;
- actual payoff-driven historical-opponent sampling.

### Competition confirmation

- COG 2022 Strategy Card Game AI competition slides/results:
- https://legendsofcodeandmagic.com/COG22/COG2022-slides.pdf

The slides report ByteRL as double champion and state the training framework was proprietary/planned for release. Do not invent or cite an unverified “official ByteRL repository.”

## C. Shared algorithm references

- IMPALA / V-trace: https://arxiv.org/abs/1802.01561
- PPO: https://arxiv.org/abs/1707.06347
- AlphaStar/UPGO source reference used by ByteRL paper: preserve the exact citation from the paper.

## Authority order

1. Official PTCG starter-kit API and competition rules.
2. Peer-reviewed/arXiv source papers above.
3. The Hearthstone source repository for implementation patterns.
4. c018 source only as a negative example and shared harness.

When sources conflict with c018 conventions, the method source and official PTCG API win.
