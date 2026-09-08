# Source provenance — where each idea in c020 came from

`references/SOURCE_REFERENCES.md` requires recording retrieval, version and the exact properties
used; `references/LICENSE_AND_REUSE_POLICY.md` requires clean-room implementation with citation.
This file maps every algorithmic idea in c020 to its source and states the licence posture for
each.

**Written after an audit found only per-package `ATTRIBUTION.md` files and no campaign-level
record.** c019 produced one via `tools/c019_sources.py`; c020 had not, which is a Phase 0 gap.

## Authority order (`references/SOURCE_REFERENCES.md`)

1. Official PTCG API and competition rules
2. Primary papers
3. Hearthstone repository for non-copied implementation patterns
4. c019 code only as control / negative evidence

## A. Corrected information-set MCTS

| c020 element | source | what was taken | licence posture |
|---|---|---|---|
| forward search lifecycle (`search_begin` / `search_step` / `search_release` / `search_end`) | **official starter kit**, `starter_kit/api.py` | the API itself — authority 1 | competition-permitted; SDK vendored unmodified in packages |
| PIMC versus shared-statistics ISMCTS, and why the distinction matters | Świechowski, Tajmajer, Janusz, *Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms*, arXiv:1808.04794 | the imperfect-information/determinization discussion, and that better state evaluation improves win rate while reducing computation | paper; properties only, no code |
| PUCT selection `Q + c_puct·P·√N_parent/(1+N_a)` | registered directly by `MANDATORY_CHANGES A4`; the form originates in the AlphaGo/AlphaZero lineage | the formula, as specified by the contract | formula, no code |
| architectural patterns for an MCTS over a card game | peter1591/`hearthstone-ai` | **inspected for architecture only.** GPL — not copied, not translated, not vendored, and absent from every submission package | GPL: clean-room per policy |
| progressive widening, availability-aware statistics, branch-local baseline memory, the tactical evaluator's feature set, the conservative override gate | **original to c018/c019/c020** for this contract | — | own work |
| the archetype prior mixture | original; motivated by `C019_AUDIT_FINDINGS` #5 | — | own work |

The clean-room requirement is why `c020_infoset.py`, `c020_ismcts.py` and `c020_tactical_leaf.py`
are written from published algorithm *properties* rather than from any reference implementation.
No Hearthstone source appears in `packages/`, and `ATTRIBUTION.md` in each package states this.

## B. Corrected ByteRL / OSFP

| c020 element | source | what was taken | licence posture |
|---|---|---|---|
| masked end-to-end policy/value, recurrent memory, actor-learner split, OSFP historical population with payoff-driven mixture | Xi et al., *Mastering Strategy Card Game (Legends of Code and Magic) via End-to-End Policy and Optimistic Smooth Fictitious Play*, arXiv:2303.04096 | the method's structure and Algorithm 1's add-to-H decision | paper; **no public reference implementation is assumed or claimed** |
| registered hyperparameters — γ=1.0, lr 7e-5, entropy 0.01, sample reuse 2, V-trace ρ/c clips [0.001, 1.007], p=0.6, ξ=0.55, c=6 | Xiao et al., *Mastering Strategy Card Game (Hearthstone) with Improved Techniques*, arXiv:2303.05197, Tables III/IV | the exact constants, registered unchanged in `HP` | paper |
| V-trace off-policy correction | Espeholt et al., *IMPALA*, arXiv:1802.01561 | the recursion, ρ̄/c̄ clipping semantics | paper; implementation reused from c019, itself fixture-verified |
| UPGO auxiliary return | originates in AlphaStar (Vinyals et al., 2019); reached here through the ByteRL papers, which register it as a component | the return recursion | paper |
| slot-aware board, typed-energy readiness, option-to-object references, autoregressive multi-select with joint log probability, period-local G/C, frozen-checkpoint promotion | **original to c020**, each motivated by a specific `C019_AUDIT_FINDINGS` item (#7, #8, #9, #12, #13) | — | own work |

**On the ByteRL source specifically:** the policy states no verified public ByteRL repository is
assumed. Nothing in `cg/c020_byterl_*.py` claims to reproduce anyone's code; the model is
implemented from the papers' equations and the contract's specification. Where the papers
disagree — LOCM registers ξ=0.7, lr 5e-5, γ=0.99; Hearthstone registers ξ=0.55, lr 7e-5, γ=1.0 —
the contract registers the Hearthstone values and those are what `HP` contains.

## C. Hybrid

Entirely original integration work. The idea of injecting a learned policy's priors and value into
a search is standard (AlphaGo lineage), but the H0–H4 mode structure, the branch-local recurrent
state propagation, and the two admission gates are specified by `MANDATORY_CHANGES C1–C5` and
implemented for this contract.

## D. The corrections themselves

The most important input to c020 is not a paper. Every mandated change traces to
`references/C019_AUDIT_FINDINGS.md`, which is a record of measuring c019's own defects. A1 exists
because c019 built one tree per determinization; A6 because its evaluator had four features; B3
because its actor stored one pick; B6 because its payoff table accumulated across policies. The
sources above supply the methods; c019's failures supply the specification.

## Deck and baseline

The official Mega Lucario deck and the official sample agent are competition-permitted materials,
copied byte-identical into `controls/baseline_package/` with per-file SHA-256 and cited in every
package's `ATTRIBUTION.md`. No public-agent replacement, no deck edit — `CONTRACT §2`.

## What this campaign did NOT do

- No GPL source vendored, translated, or line-by-line adapted
- No claim of reproducing any reference implementation
- No invented repository or fabricated citation
- No unclear-permission code inside any submission archive
