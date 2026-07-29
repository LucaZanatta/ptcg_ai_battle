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

---

## Completing the file-by-file audit

The table above covered 16 of the archive's 33 `.cs` files. `CONTRACT.md` requires a **file-by-file**
audit, so the remaining 17 are accounted for here. Found during the pass-2 deep audit; the
omission was real, not stylistic — `Information.cs` in particular implements the mechanism most
relevant to the contract's known-defect requirement and had no entry anywhere.

| Source file | Lines | Role | Disposition |
|---|---|---|---|
| `src/Information.cs` | 214 | `GetInformationSet`, `RestoreNodes`, `ExtractPrivateInformation`. Collects the **opponent's private hand** at nodes reached through an end turn and merges nodes sharing a state abstraction into an *information set* — a collection of distinct hidden-information instances behind one key — then re-samples from it. | **NOT PORTED.** Requires reading the opponent's hand and reshuffling an interior deck. `c019_core.visible_view` raises on the first by design, and the API forbids the second (see `A4_chance_node_api_constraint.md`, Probe 3). This is the single largest unported component and is the source's own answer to the hidden-information problem that `FINDING_single_determinization_overconfidence.md` measures the cost of. |
| `src/Enums.cs` | 36 | `RandomActionType`, `InspectType`, `EndNodeOption`, `SearchDurationCondition` | Partially ported: `RandomActionType` survives as `Node.random_action_type`, restricted to `RANDOMEFFECT` for the reason A4 documents. The others gate configurations not used by the shipped setup. |
| `src/SearchStatistics.cs` | 113 | per-search timing and depth accumulators | Superseded by `c021_mcgs.new_stats()`, which records the same quantities plus the PTCG-specific counters the port needs. |
| `src/DefaultPolicy/Policy.cs` | 41 | abstract base for a pluggable rollout policy | Its *pluggability* is the ported property: it is what makes transfer arm T2 (a ByteRL rollout policy) a legitimate component swap rather than an algorithm change. |
| `src/Heuristics/CardCategory.cs` | 765 | Hearthstone card-ID sets (`CardsHarmfulToTarget`, `BeneficialToTarget`, `RestoreOnly`, `GetFromDeck`, …) | **NOT PORTABLE.** These are literal Hearthstone asset IDs. The A10 `C2` filter rebuilds the *structure* from `api.SelectContext` valence and `playerIndex` ownership instead. |
| `src/Utils/IntSet.cs` | 47 | small integer-set helper | Python `set` |
| `src/Utils/CommonUtils.cs` | 180 | `ArgMax`, `GetWeightedRandom`, `Random`, array helpers | Inlined: `max(..., key=...)` and `Node._sample_child`'s weighted draw |
| `src/SabberHelpers/SabberUtils.cs` | — | `Determinize`, engine mutation | No counterpart: determinization happens at `search_begin` |
| `src/SabberHelpers/SendOption.cs` | — | option serialization to the engine | `c019_core.to_select_payload` |
| `src/SabberHelpers/Options/*.cs` (5 files) | — | `Options`, `GetOptions`, `PlayCardOption`, `AttackOption`, `HeroPowerOption` | Replaced wholesale by `c019_core.canonical_options` over the PTCG select |
| `Agent.cs` | 217 | `MCGSAgent` competition entry point, move-clock scheduling | `c021_mcgs_agent.MCGSAgent`, with the budget adapted per `M7`/`M12` |
| `AgentUtils.cs` | 332 | `CardIds`, `CardLib`, deck helpers | `c020_cards` |
| `PremadeDeck.cs` | 45 | fixed decklists for the competition | `c019_determinize.archetype_decks` |

**Coverage: 33 of 33.** Two files are deliberately unported and both are recorded above with the
constraint that forces it, rather than being absent from the audit.
