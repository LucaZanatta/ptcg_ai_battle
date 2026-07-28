# MCGS — source file to PTCG implementation map

Official archive: `2019_UCDP_MCGS.zip`, SHA-256
`f00a54f310a8f868deb59964c17e71357d67ecfcedba01c0245053dcc5aa920a`, 33 C# files.
No C# text is copied; behaviour is transcribed. See `mcgs_license_assessment.md`.

| Source file | Role | Ported to | Notes |
|---|---|---|---|
| `src/MCGS.cs` | search loop, `TreePolicy`, `TranspositionCheck`, `Backup`, `Select` | `c021_mcgs.py` | control flow reproduced including `Expand`'s continue-boolean |
| `src/Node.cs` | node, `Value`, `Update`, `BestChild`, `SampleChild`, `IsFullyExpanded`, `Finalise` | `c021_mcgs_graph.py::Node` | sign flip at opponent nodes preserved; values stored in the mover's frame |
| `src/Edge.cs` | `Value`, `SampleCount`, `IsDummy`, `RecursiveUpdate` | `c021_mcgs_graph.py::Edge` | UCB1 with the UCD `TotalVisit` divisor; `IsDummy` parks VisitCount at int.MaxValue |
| `src/Node.Expand.cs` | `Expand`, `TreePolicy`, `CheckRandom`, `CreateChanceNode`, `PrepareChanceNode` | `c021_mcgs.py::expand`, `_make_node` | chance types reduced to RANDOMEFFECT — see `A4_chance_node_api_constraint.md` |
| `src/Algorithms/UCD.cs` | `UCDParams`, recursive update | `c021_mcgs_graph.py::UCDParams`, `backup_ucd` | inert at the (1, 0) default; reproduced, not fixed |
| `src/Algorithms/DampedSamping.cs` | `ReduceFunction` | `Node.reduce_function` | keyed on `numSampleTraversed`, NOT depth |
| `src/Abstraction/StateAbstraction.cs` | transposition key | `c021_mcgs_abstraction.py::StateAbstraction` | `hash*17 + next` combiner and field order preserved; contents are a SEMANTIC_ADAPTER |
| `src/Abstraction/ActionAbstraction.cs` | action identity | `c021_mcgs_abstraction.py::ActionAbstraction` | identified by type/source/target, not list position |
| `src/DefaultPolicy/UniformRandomRollout.cs` | rollout | `c021_mcgs.py::_play_until_terminal` | uniform random; 1000-step cap; NO move-clock check inside the rollout |
| `src/Heuristics/Filter.cs` | `CategoryBasedFilter` | `c021_mcgs_legal.py::category_filter` | A10 branch only; Hearthstone card-ID sets replaced by `SelectContext` valence + `playerIndex` |
| `src/Heuristics/TreePhasePruning.cs` | obliged actions | `c021_mcgs_legal.py::is_obliged` | A10 branch only |
| `src/Utils/IntArrayComparer.cs` | array hash | `c021_mcgs_abstraction.py::_arr_hash` | order-sensitive |
| `src/SearchConfig.cs`, `NodeConfig.cs` | constants | `c021_mcgs_graph.py` module constants | asserted by `test_source_constants_match_the_shipped_config` |
| `src/Algorithms/PIMC.cs`, `DoubleProgressiveWidening.cs` | alternative configurations | not active | `PIMC = False`, `DoubleProgressiveWidening` off, matching the shipped config |
| `src/SabberHelpers/*` | Hearthstone engine glue | no counterpart | replaced wholesale by the PTCG `api` search interface |
