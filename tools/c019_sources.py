"""c019 §3 — primary source snapshot, method translation, and PTCG adaptation record.

Records what was actually retrieved and when, the exact values each source states, and — where
two sources disagree — which one the contract registers and why. Fabricating agreement between
the LOCM and Hearthstone papers would be the easiest possible way to look faithful while
implementing neither.

Clean-room policy (references/LICENSE_AND_REUSE_POLICY.md): the Hearthstone repository is GPL, so
its structure and published algorithm properties inform an ORIGINAL PTCG implementation and no
source is vendored or line-by-line translated. No ByteRL reference implementation exists
publicly, so that branch is built from the papers' equations and pseudocode.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
MF = os.path.join(C19, "method_fidelity")

RETRIEVED = "2026-07-27"

SOURCES = [
    {
        "id": "hearthstone_ai_repo",
        "role": "MCTS implementation patterns",
        "url": "https://github.com/peter1591/hearthstone-ai",
        "doc_url": "https://peter1591.github.io/hearthstone-ai/agents/include/MCTS/",
        "retrieved": RETRIEVED,
        "retrieval_method": "documentation page fetched and summarized; repository NOT vendored",
        "license": "GPL (declared by the repository)",
        "reuse_decision": "CLEAN_ROOM_ONLY",
        "reuse_rationale": ("GPL source may not be copied or line-by-line translated into a "
                            "competition package without an explicit compatibility decision. "
                            "Published algorithm PROPERTIES inform an original implementation."),
        "properties_extracted": [
            "information-set treatment of hidden information, citing Cowling et al. ISMCTS",
            "identical game states consolidated into one node (transposition sharing)",
            "randomness handled by creating redirect nodes",
            "policy network prioritizes promising actions; rollout network used in simulation",
            "value estimate used for early cutoff",
            "virtual loss for multithreaded exploration",
        ],
        "adopted_in_c019": [
            "information-set determinization (M02)",
            "redirect/chance-outcome recording rather than overwriting a successor (M08)",
            "prior-weighted selection and leaf-value cutoff (M04, §8.4)",
        ],
        "deliberately_not_adopted": [
            {"property": "transposition node sharing",
             "reason": ("§8.5 permits a transposition table only when a stable "
                        "visible+determinization state hash is PROVEN. Claiming node sharing "
                        "falsely is called out explicitly as invalidating; v0 does not share "
                        "nodes and says so.")},
            {"property": "virtual loss / multithreaded tree",
             "reason": "single-threaded tree per decision; CPU is spent on ByteRL actors"},
        ],
    },
    {
        "id": "swiechowski_2018",
        "role": "Hearthstone MCTS + supervised learning paper",
        "url": "https://arxiv.org/abs/1808.04794",
        "retrieved": RETRIEVED,
        "license": "arXiv preprint; cited, not copied",
        "reuse_decision": "CITE_ONLY",
    },
    {
        "id": "cowling_ismcts",
        "role": "ISMCTS foundation",
        "url": "https://ieeexplore.ieee.org/document/6203567",
        "note": ("linked from the Hearthstone MCTS documentation as 'Information Set Monte "
                 "Carlo Tree Search' (Cowling, Powley, Whitehouse). The documentation page "
                 "references the paper; the canonical IEEE TCIAIG 2012 record is used as the "
                 "resolved citation."),
        "retrieved": RETRIEVED,
        "reuse_decision": "CITE_ONLY",
        "properties_extracted": [
            "search a tree of information sets rather than states",
            "each iteration samples a determinization consistent with the information set",
            "statistics aggregate across determinizations at shared information-set nodes",
        ],
    },
    {
        "id": "xi_2023_locm",
        "role": "ByteRL / OSFP original (Legends of Code and Magic)",
        "url": "https://arxiv.org/abs/2303.04096",
        "html_mirror": "https://ar5iv.labs.arxiv.org/html/2303.04096",
        "retrieved": RETRIEVED,
        "retrieval_method": "ar5iv HTML mirror fetched and summarized",
        "license": "arXiv preprint; no public reference implementation identified",
        "reuse_decision": "IMPLEMENT_FROM_PAPER",
        "stated_values": {
            "entropy_weight": 0.01, "learning_rate": 5e-5, "gamma": 0.99,
            "vtrace_c_clip": 1.0, "vtrace_rho_clip": 1.0,
            "osfp_p_current_self_play": 0.6, "osfp_xi_promotion": 0.7,
            "osfp_c_max_lp_without_add": 6,
        },
        "properties_extracted": [
            "OSFP Algorithm 1: immutable historical array H, current-self-play probability p, "
            "payoff-based sampling function f over H",
            "G[i] accumulates +1/-1 game results vs historical model i; C[i] counts games",
            "promotion when all G[i]/C[i] > xi; forced add when count > c",
            "V-trace value targets with an auxiliary UPGO loss",
        ],
    },
    {
        "id": "xiao_2023_hearthstone",
        "role": "ByteRL Hearthstone transfer -- the values c019 REGISTERS",
        "url": "https://arxiv.org/abs/2303.05197",
        "html_mirror": "https://ar5iv.labs.arxiv.org/html/2303.05197",
        "retrieved": RETRIEVED,
        "retrieval_method": "ar5iv HTML mirror fetched; Table III and Table IV read",
        "license": "arXiv preprint; no public reference implementation identified",
        "reuse_decision": "IMPLEMENT_FROM_PAPER",
        "stated_values": {
            "lstm_hidden": 256, "gamma": 1.0, "learning_rate": 7e-5,
            "entropy_weight": 0.01, "ppo_policy_weight": 1.0, "upgo_weight": 1.0,
            "value_weight": 1.0, "sample_reuse": 2, "ppo_clip_epsilon": 0.2,
            "vtrace_c_lower": 0.001, "vtrace_c_upper": 1.007,
            "vtrace_rho_lower": 0.001, "vtrace_rho_upper": 1.007,
            "osfp_p_current_self_play": 0.6, "osfp_xi_promotion": 0.55,
            "osfp_c_max_lp_without_add": 6,
            "reference_scale": "24 V100 GPUs, 5856 CPU cores, batch 1e4 * 8gpu",
        },
    },
    {
        "id": "impala_vtrace", "role": "V-trace origin",
        "url": "https://arxiv.org/abs/1802.01561", "retrieved": RETRIEVED,
        "reuse_decision": "CITE_ONLY",
    },
    {
        "id": "ppo", "role": "PPO clipping origin",
        "url": "https://arxiv.org/abs/1707.06347", "retrieved": RETRIEVED,
        "reuse_decision": "CITE_ONLY",
    },
    {
        "id": "cog22_slides", "role": "competition confirmation",
        "url": "https://legendsofcodeandmagic.com/COG22/COG2022-slides.pdf",
        "retrieved": RETRIEVED, "reuse_decision": "CITE_ONLY",
        "note": ("reports ByteRL as double champion and states the training framework was "
                 "proprietary. No official ByteRL repository is cited or assumed to exist."),
    },
]

# Where the two ByteRL papers disagree, c019 follows the Hearthstone adaptation, because
# METHOD_FIDELITY registers those values and Hearthstone is the closer analogue: a
# turn-based card game with a long battle phase, like PTCG.
CONFLICTS = [
    {"parameter": "osfp_xi_promotion", "locm": 0.7, "hearthstone": 0.55,
     "registered": 0.55, "why": "METHOD_FIDELITY B registers xi = 0.55 explicitly"},
    {"parameter": "learning_rate", "locm": 5e-5, "hearthstone": 7e-5, "registered": 7e-5,
     "why": "METHOD_FIDELITY B registers 7e-5"},
    {"parameter": "gamma", "locm": 0.99, "hearthstone": 1.0, "registered": 1.0,
     "why": ("METHOD_FIDELITY B registers 1.0. Note gamma=1.0 makes the V-trace recursion "
             "non-contracting, so target magnitudes are logged from the first fixture to "
             "distinguish divergence from a bug.")},
    {"parameter": "vtrace_clips", "locm": "c=rho=1.0",
     "hearthstone": "[0.001, 1.007] both", "registered": "[0.001, 1.007]",
     "why": "METHOD_FIDELITY B registers the Hearthstone asymmetric clipping"},
]

TRANSLATION = """# Method translation: source components -> PTCG components

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
"""


def main():
    os.makedirs(MF, exist_ok=True)
    for s in SOURCES:
        s["snapshot_id"] = hashlib.sha256(
            f"{s['url']}|{RETRIEVED}".encode()).hexdigest()[:16]
    manifest = {
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "retrieval_date": RETRIEVED,
        "n_sources": len(SOURCES),
        "sources": SOURCES,
        "source_conflicts": CONFLICTS,
        "clean_room_policy": {
            "hearthstone_repo": "GPL -- inspected via public documentation only, NOT vendored, "
                                "NOT line-by-line translated; original PTCG implementation",
            "byterl": "no public reference implementation identified in the papers or the "
                      "competition materials; implemented from published equations and "
                      "Algorithm 1 pseudocode. No repository is invented or cited.",
            "vendored_source_files": 0,
        },
        "note": ("URLs identify the intended algorithms; retrieval was by fetching public "
                 "abstract/HTML-mirror pages. Full PDFs were not vendored into the repository."),
    }
    json.dump(manifest, open(os.path.join(MF, "source_snapshot_manifest.json"), "w"),
              indent=2, default=str)
    open(os.path.join(MF, "method_translation.md"), "w").write(TRANSLATION)

    adaptations = {
        "ptcg_adaptations": [
            {"id": "no_deck_building_stage", "branch": "byterl", "severity": "MAJOR",
             "source": "ByteRL trains CB+BT jointly with one reward signal",
             "ptcg": "deck frozen by CONTRACT §4/§9.1; battle policy only",
             "consequence": "the CB/BT head mixture degenerates to the BT head",
             "required_by_contract": True},
            {"id": "single_machine_scale", "branch": "byterl", "severity": "MAJOR",
             "source": "24 V100 GPUs, 5856 CPU cores, batch 1e4*8gpu",
             "ptcg": "1 RTX 5070 + 12 CPU cores; batch/actor count calibrated once",
             "consequence": "sample throughput orders of magnitude lower; all other "
                            "hyperparameters held at source values",
             "required_by_contract": True},
            {"id": "atomic_select_contexts_as_autoregression", "branch": "byterl",
             "severity": "MINOR",
             "source": "explicit autoregressive action decomposition",
             "ptcg": "the simulator already emits sequential selection contexts; those ARE the "
                     "decomposition",
             "consequence": "no additional action factorization is invented"},
            {"id": "no_transposition_sharing", "branch": "mcts", "severity": "MINOR",
             "source": "identical boards share one node",
             "ptcg": "not implemented in v0 and not claimed",
             "consequence": "more nodes per tree; §8.5 explicitly permits this and forbids "
                            "falsely claiming node sharing"},
            {"id": "no_virtual_loss_threads", "branch": "mcts", "severity": "MINOR",
             "source": "virtual loss for multithreaded tree exploration",
             "ptcg": "single-threaded tree; CPU reserved for ByteRL actors",
             "consequence": "lower nodes/s per decision, no correctness impact"},
            {"id": "determinization_from_public_archetypes", "branch": "mcts",
             "severity": "MINOR",
             "source": "Hearthstone samples from known card pool",
             "ptcg": "opponent archetype inferred from REVEALED cards only, then hidden zones "
                     "sampled without replacement from that archetype's public decklist",
             "consequence": "wrong-archetype worlds are possible and are counted, not hidden"},
        ],
        "registered_hyperparameters": {
            k: v for k, v in SOURCES[4]["stated_values"].items()
        },
        "source_of_registered_values": "xiao_2023_hearthstone (arXiv 2303.05197) Tables III/IV",
    }
    json.dump(adaptations, open(os.path.join(MF, "ptcg_adaptations.json"), "w"), indent=2,
              default=str)
    print(json.dumps({"sources": len(SOURCES), "conflicts_recorded": len(CONFLICTS),
                      "adaptations": len(adaptations["ptcg_adaptations"]),
                      "vendored_files": 0,
                      "registered_from": adaptations["source_of_registered_values"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
