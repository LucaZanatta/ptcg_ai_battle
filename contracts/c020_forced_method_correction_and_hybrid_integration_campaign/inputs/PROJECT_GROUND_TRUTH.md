# c020 Project Ground Truth

- c019 final recorded commit: `55c14c83e8bddc0bd40f510605538735790ae20c`.
- c019 branch: `contract/c019_dual_method_campaign_ptcg_mcts_and_byterl`.
- Frozen deck/base: exact official Mega Lucario.
- c019 MCTS used real PUCT mechanics but separate trees per determinization, a shallow tactical objective, unknown-archetype Dragapult default, and unsafe overrides.
- c019 ByteRL played 80,000 real games and used real V-trace/UPGO code, but its board representation pooled active/bench identities, multi-select probability/action records were incomplete, learner recurrent state was reset at mid-game unrolls, and OSFP period promotion accounting accumulated across changing policies.
- c019 hybrid used weak components and discarded recurrent state at search nodes.
- c020 does not change strategy. It corrects these exact blocks and reintegrates them.
- Full source and raw evidence are mandatory because ChatGPT will audit the implementation line by line.
