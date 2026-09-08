# Method translation: source components -> PTCG components

Line-by-line mapping required by CONTRACT §3. Every row names the PTCG artifact that implements
it, so an auditor can check the claim against code rather than prose.

## A. Hearthstone-style ISMCTS -> PTCG-ISMCTS

| source component | PTCG component | implemented in |
|---|---|---|
| Hearthstone hidden state (opponent hand/deck) | PTCG opponent hand/deck/prize determinization sampled without replacement from a public archetype decklist minus revealed cards | `cg/c019_determinize.py` |
| information set node | node keyed by visible observation hash + determinization id | `cg/c019_mcts.py` |
| MCTS tree over game states | tree over official `search_begin`/`search_step` successors, one live `searchId` per node | `cg/c019_mcts.py` |
| selection policy | PUCT `Q + c_puct * P * sqrt(N_parent) / (1 + N_child)` | `cg/c019_mcts.py:select_child` |
| expansion | progressive widening `1 + floor(k * N^alpha)`, real `search_step` child per action | `cg/c019_mcts.py:expand` |
| rollout / default policy network | branch-local official baseline (`PolicyMemory`) or stochastic legal policy | `cg/c019_baseline.py` |
| value estimate for early cutoff | PTCG heuristic leaf evaluator (prize route, KO/lethal, energy route, board liability) | `cg/c019_leaf.py` |
| backpropagation | visit/value backup with zero-sum perspective sign | `cg/c019_mcts.py:backup` |
| redirect nodes for randomness | successor outcome hashes recorded per (node, action); distinct outcomes stored as chance children rather than overwriting | `cg/c019_mcts.py:ChanceOutcomes` |
| identical-board node sharing | **NOT implemented in v0** and not claimed. §8.5 allows a transposition table only with a proven stable hash; falsely claiming node sharing is called out as invalidating. | — |
| multithreaded virtual loss | **NOT implemented.** Single-threaded tree per decision; CPU budget goes to ByteRL actors. | — |

## B. ByteRL -> PTCG-ByteRL

| source component | PTCG component | implemented in |
|---|---|---|
| end-to-end masked action policy | dynamic legal-option scorer over `CanonicalOption` features; masked entries get exactly zero probability | `cg/c019_byterl_model.py` |
| card + hero embeddings | card id embedding + static card-metadata features, per zone | `cg/c019_byterl_encode.py` |
| LSTM 256 recurrent core | `nn.LSTMCell(d_ctx, 256)` carried across atomic decisions, reset at game boundary | `cg/c019_byterl_model.py` |
| CB (deck-building) + BT (battle) heads | **BT only.** §9.1 freezes PTCG deck construction outside the model, so the CB head has no PTCG analogue and the mixture `delta*pi_CB + (1-delta)*pi_BT` degenerates to `pi_BT`. Recorded, not silently dropped. | — |
| autoregressive action decomposition | the simulator's own sequential selection contexts | `cg/c019_byterl_actor.py` |
| actor-learner (24 GPU / 5856 CPU) | 12 CPU actors + one RTX 5070 learner, FIFO queue | `tools/c019_byterl_train.py` |
| V-trace targets | reference NumPy implementation + torch path, fixture-tested | `cg/c019_vtrace.py` |
| UPGO auxiliary loss | separate recursive return, unit-tested, gradient contribution logged | `cg/c019_vtrace.py:upgo` |
| OSFP historical models H | immutable checkpoint files with recorded hashes | `cg/c019_osfp.py` |
| payoff sampling f | registered hardness/uncertainty sampler over G/C | `cg/c019_osfp.py:sample_opponent` |

## C. What PTCG forced us to change, and why

1. **No deck-building stage.** ByteRL's headline contribution is joint CB+BT training with one
   reward signal. PTCG's deck is frozen by §4/§9.1, so c019 implements the battle policy only.
   This is the single largest fidelity gap and it is a contract requirement, not a shortcut.
2. **Scale.** The source trains on 24 GPUs and 5,856 CPU cores with batch 1e4*8. c019 has one
   RTX 5070 and 12 cores. Batch size and actor count are calibrated once and recorded; every
   other hyperparameter stays at the source value.
3. **Two sources disagree.** LOCM says xi=0.7, lr=5e-5, gamma=0.99, clips=1.0; Hearthstone says
   xi=0.55, lr=7e-5, gamma=1.0, clips=[0.001,1.007]. c019 registers the Hearthstone values
   because METHOD_FIDELITY names them and Hearthstone is the closer analogue to PTCG.
