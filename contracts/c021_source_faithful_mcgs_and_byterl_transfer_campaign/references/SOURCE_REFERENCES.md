# Primary Source References

Record retrieval time, exact URL, version/commit where available, SHA-256 and exact properties used.

## Official PTCG environment

- Local repository starter kit and competition API.
- Highest authority for legal observations, legal actions, deck rules, packaging and search lifecycle.
- Required native search API previously identified: `search_begin`, `search_step`, `search_release`, `search_end`.

## Official 2019 MCGS competition source

- Official competition bot-download page:
  - https://hearthstoneai.github.io/botdownloads.html
- Direct 2019 user-created-deck MCGS winner archive:
  - https://hearthstoneai.github.io/files/bots/UserCreatedDeckPlaying2019/2019_UCDP_MCGS.zip
- The official page identifies Jean Seong Bjorn Choe's MCGS as rank 1 in the 2019 user-created-deck track.

## MCGS paper

- Jean Seong Bjorn Choe and Jong-Kook Kim, “Enhancing Monte Carlo Tree Search for Playing Hearthstone.”
- https://ieee-cog.org/2020/papers2019/paper_257.pdf
- DOI landing page: https://ieeexplore.ieee.org/document/8848034/

Primary properties:

- state abstraction;
- transposition-table DAG;
- modified UCD;
- recursive graph updates;
- active-player information sets;
- chance nodes;
- sparse and damped sampling;
- category filters and obliged actions;
- graph reuse/time allocation;
- random simulation/no state evaluator;
- known theoretical information limitation.

## ByteRL LOCM

- Wei Xi et al., “Mastering Strategy Card Game (Legends of Code and Magic) via End-to-End Policy and Optimistic Smooth Fictitious Play.”
- https://arxiv.org/abs/2303.04096
- PDF: https://arxiv.org/pdf/2303.04096

## ByteRL Hearthstone improvements

- Changnan Xiao et al., “Mastering Strategy Card Game (Hearthstone) with Improved Techniques.”
- https://arxiv.org/abs/2303.05197
- PDF: https://arxiv.org/pdf/2303.05197

Primary properties:

- end-to-end deck building and battle;
- recurrent masked categorical policy/value;
- autoregressive action decomposition;
- gamma=1 improvement;
- random deck-construction initialization;
- blocking FIFO actor–learner balance;
- modified V-trace and PPO-style policy objective;
- OSFP;
- B0→B4 cumulative analysis.

Use B0→B3 as the closest clean PTCG-compatible reference ladder. B4 hero isolation has no literal PTCG equivalent and is not mandatory in c021.

## Competition evidence on ByteRL source availability

- COG 2022 competition slides:
  - https://legendsofcodeandmagic.com/COG22/COG2022-slides.pdf
- The material reports training with the authors' proprietary RL framework. Re-check for later release before concluding no source is available.

## V-trace

- Espeholt et al., “IMPALA: Scalable Distributed Deep-RL with Importance Weighted Actor-Learner Architectures.”
- https://arxiv.org/abs/1802.01561

Use only when the ByteRL papers defer to the primary V-trace definition. ByteRL-specific modifications override generic IMPALA behavior.

## Deferred, not part of c021 mandatory implementation

- Peter1591 neural-MOMCTS repository:
  - https://github.com/peter1591/hearthstone-ai

This is a separate GPL neural-MCTS architecture, not the 2019 MCGS winner. Do not add it as a third method in c021.
