# ByteRL — choices the papers do not determine

No author-released implementation of ByteRL was found (see `byterl_source_search.md` for the
search record). The implementation therefore derives from two papers:

* arXiv:2303.04096 — *ByteRL* on LOCM
* arXiv:2303.05197 — the Hearthstone improvements

A paper fixes an algorithm, not a codebase. Everything below is a decision the papers leave open.
Each is recorded with what was chosen, why, and — where it matters — what a different choice would
change. **These are declared, not hidden inside defaults.** A reader auditing BYTERL_METHOD should
treat every row here as a known deviation risk, not as reproduced behaviour.

## Legend

| Confidence | Meaning |
|---|---|
| **Stated** | the paper gives the value or the formula explicitly |
| **Implied** | the paper names the technique and cites a source that fixes the detail |
| **Chosen** | neither paper determines it; the choice is mine and is defensible but unverified |

---

## 1. Algorithmic core

| # | Item | Confidence | Choice | Notes |
|---|---|---|---|---|
| 1.1 | V-trace | Implied | ρ̄ = c̄ = 1.0 | The IMPALA defaults the paper cites. Larger ρ̄ increases variance and off-policy reach; the effect is measured in the `rho_clipped_frac` curve rather than assumed. |
| 1.2 | UPGO | Implied | AlphaStar formulation, bootstrapping from V when the one-step return underperforms | The papers name UPGO without restating the recursion. Transcribed from AlphaStar and pinned by `test_upgo_cuts_to_the_baseline_when_the_trajectory_underperforms`. |
| 1.3 | Discount γ | **Chosen** | 1.0 | PTCG gives a single terminal reward and no per-step shaping, so discounting would only downweight early decisions — which is where this project's measured constraint (early-game credit assignment) already bites. |
| 1.4 | Value loss coefficient | **Chosen** | 0.5 | Common IMPALA setting. Not tuned; a sweep is out of scale here. |
| 1.5 | Entropy coefficient | **Chosen** | 0.01 | Not tuned. |
| 1.6 | UPGO coefficient | **Chosen** | 1.0, equal to the policy-gradient term | The papers do not give the mixing weight. Equal weighting is the neutral choice. |
| 1.7 | Optimiser | **Chosen** | Adam, lr 3e-4 | Neither paper specifies. |
| 1.8 | Gradient clipping | **Chosen** | global norm 10.0 | Reported per iteration as `grad_norm`. |
| 1.9 | Bootstrap value at episode end | Implied | 0.0 | Episodes end at a true terminal, so there is nothing to bootstrap from. |

## 2. OSFP

| # | Item | Confidence | Choice | Notes |
|---|---|---|---|---|
| 2.1 | G and C scope | **Stated** (Hearthstone paper) | period-local, cleared at promotion | The one detail the paper is explicit about, and the one c019 and c020 both got wrong. |
| 2.2 | Opponent distribution | **Chosen** | softmax over negative mean payoff, η = 0.1 | Fictitious play weights the opponents the learner does worst against. The paper does not give the temperature. Uniform before any games in a period. |
| 2.3 | Promotion rule | **Chosen** | win rate ≥ 0.55 over ≥ 48 games | Neither threshold is from the paper. Both are exposed as flags and recorded in the manifest. |
| 2.4 | Checkpoint buffer | **Chosen** | 16, FIFO | Unbounded history would make the meta-distribution stale; the paper does not give a bound. |
| 2.5 | Period-0 opponent | **Chosen** | the initial random weights, seeded as checkpoint 0 | Without this there is no opponent to play in period 0. |

## 3. Network

| # | Item | Confidence | Choice | Notes |
|---|---|---|---|---|
| 3.1 | Torso | **Chosen** | 3–4 residual blocks, width 192–256, LayerNorm | The papers describe a shared torso with separate heads but not the depth or width. **This is the largest unverified structural choice.** |
| 3.2 | Option scoring | **Chosen** | bilinear against the state embedding, plus a per-option bias | PTCG option counts vary from 2 to >100, so a fixed-size action head would truncate or waste. LOCM's action space is fixed and the papers do not face this. |
| 3.3 | Slot tokens | **Chosen** | distinct learned embeddings for role (active/bench), bench index, and side | A PTCG-specific requirement with no LOCM counterpart. Its absence in c020 made the network unable to distinguish attacking with the active from attacking with a benched Pokemon. |
| 3.4 | Stage conditioning | **Chosen** | one shared torso, a stage embedding, and separate value heads | B2 requires the reward to reach both stages; it does not require one shared baseline. Separate value heads stop 60 near-zero-information construction prefixes from swamping the battle gradient. |
| 3.5 | Initialisation | **Chosen** | orthogonal, gain √2; final layers gain 0.01 | So the initial policy is near-uniform and the initial value near 0. |

## 4. PTCG-specific, with no counterpart in either paper

| # | Item | Confidence | Choice | Notes |
|---|---|---|---|---|
| 4.1 | Multi-select actions | **Chosen** | autoregressive; joint log-probability is the sum of per-element conditionals under the running mask | LOCM has no `minCount..maxCount` action. This is forced by V-trace needing a correct behaviour log-probability. |
| 4.2 | Deck construction as a stage | **Implied** | 60 autoregressive picks under a per-prefix legal mask | The papers cover LOCM's draft, which is 30 binary-ish picks from offered triples. PTCG construction is open selection from a 52-card pool, which is a materially larger and less guided space. |
| 4.3 | Construction legality | **Chosen** | enforced structurally in the mask, never repaired after the fact | A silently repaired deck teaches the policy that an illegal construction is free. |
| 4.4 | Option cap | **Chosen** | 128, with truncations counted | Observed maximum in play is ~24, so the cap is not binding; it is counted rather than assumed. |

## 5. Scale — reduced under `FIDELITY_RULES §4`, which permits exactly these four

| Dimension | Papers | This run | Permitted? |
|---|---|---|---|
| Actors | large distributed fleet | 6–10 local processes | yes |
| Samples | millions of games | thousands | yes |
| Duration | days | tens of minutes per rung | yes |
| Learning periods | many | few | yes |
| **Architecture** | — | **unchanged** | would NOT be permitted |
| **Algorithm** | — | **unchanged** | would NOT be permitted |

The reductions are recorded per run in `results/byterl/manifests/*.json` under `reductions`, with
`architecture_simplified: false` and `algorithm_simplified: false` asserted explicitly.

## 6. What this means for the BYTERL_METHOD status

The algorithmic components — V-trace with clipping, UPGO with baseline cutting, OSFP with
period-local bookkeeping, autoregressive masked multi-select, fresh random initialisation — are
implemented and each is pinned by a test that fails when the component is removed
(`tools/c021_validate.py`, 17/17 detect).

What cannot be claimed is *numerical* correspondence to the published agent. The torso geometry
(3.1), every coefficient in §1 marked **Chosen**, and the OSFP temperature and promotion rule
(2.2, 2.3) are unverified against the authors' settings. Any BYTERL_METHOD claim must therefore
read as "faithful to the published algorithm as specified, with the listed choices declared",
never as "reproduces ByteRL".
