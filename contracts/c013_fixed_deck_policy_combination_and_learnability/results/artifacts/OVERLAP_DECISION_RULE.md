# Registered decision rule for AC-12 / §24 — written before any overlap number was computed

This file is committed **before** `tools/c013_overlap_analysis.py` is run. c013's own history
contains `DEFECT_float_tie_flipped_a_registered_threshold.md`, where a threshold check was
revised after the result was visible. Registering the rule first is the control for that.

## 1. What is being tested

§6 question 6: *do the frozen teacher and official opponents show measurable behavioural /
policy overlap on identical visible states?*

§24: `OPPONENT_OVERLAP = SUPPORTED` **only** when teacher–Lucario similarity is higher than
teacher–Iono **and** teacher–Abomasnow **under multiple registered measures**, with uncertainty
reported.

## 2. How "identical visible state" is produced

A **shadow-query loop**. One acting policy drives a real game; at every decision point every
other policy is queried on the *same* `obs` and its answer is recorded and discarded.

Each shadow policy holds a **persistent per-game instance**. `cg/teachers.py` states these rule
agents keep module-level state (turn counters, attack plan, ability flags) and do not reset;
a fresh instance queried at a mid-game state would evaluate every turn-conditioned branch on
counters still at zero. That would corrupt the four rule agents *asymmetrically* — whichever
skeleton branches hardest on turn number would be damaged most — and that asymmetry would land
directly on the teacher–Lucario vs teacher–Iono contrast this rule turns on. Persistent
instances see the whole obs prefix, so their counters advance naturally.

**Disclosed limitation, not worked around:** the trajectory is the *acting* policy's. Shadow
agents answer "what would you do in this position", not "what position would you have reached".
This is inherent to any identical-state comparison and is reported with the result.

## 3. Applicability classification (per policy, per state)

Every agent hard-codes its own deck's card IDs (dragapult 48 distinct integer literals,
mega_lucario 28, iono 32, mega_abomasnow 15), so on a state from another deck the deck-specific
branches cannot fire and the agent falls through to its generic skeleton. Counting a fall-through
as agreement would manufacture overlap. Each (policy, state) is therefore classified:

| class | test | used in agreement measures |
|---|---|---|
| `ERROR` | the agent raised | no |
| `INVALID` | returned index out of range, or count outside `[minCount, maxCount]` | no |
| `POSITIONAL` | under `K = 4` registered permutations of the option list, the selected **content** changes — the agent tracked the index, not the option | no |
| `CONTENT_DRIVEN` | the selected content is invariant under all `K` permutations | yes |

The permutation test is implementation-agnostic: it never reads the agents' source, so it cannot
be tuned to a branch. Permutations are drawn from a `default_rng(20260726)` fixed at registration.
Forced decisions (`n_options < 2`) carry no information and are excluded from every measure.

## 4. Primary comparison population — fixed now

The **intersection** subset: states where the frozen teacher **and all three** official opponents
are `CONTENT_DRIVEN`. If teacher–Lucario were computed on Lucario's applicable states and
teacher–Iono on Iono's, the two numbers would come from different state populations and §24's
ordering would be confounded by subset composition rather than policy similarity.

Per-pair-maximal subsets are reported as **secondary**, always with their `n`. Applicability
rates are themselves reported as a finding.

## 5. Registered measures (§22)

Similarity between policies A and B on the primary subset:

1. `top1_agreement` — same chosen option content
2. `action_type_agreement` — `c013_semantic_serializer.classify_action` category
3. `set_jaccard` — Jaccard of returned option sets (multi-select)
4. `target_agreement` — same target card among target-bearing decisions
5. `energy_commitment_agreement` — same attach/decline on energy decisions
6. `attack_pass_timing_agreement` — same attack-vs-develop choice when both are legal
7. `promotion_agreement` — same promoted Pokémon after a knockout
8. `phase_conditioned_top1` — measure 1 within each of early / mid / late

## 6. Decision rule — fixed now

Let `d_L = sim(teacher, Lucario)`, `d_I = sim(teacher, Iono)`, `d_A = sim(teacher, Abomasnow)`,
each with a 95% bootstrap CI (10,000 resamples over states, seed fixed at registration; the
validator recomputes with a **different** seed).

A measure **discriminates for Lucario** when `d_L > d_I` and `d_L > d_A` **and** the 95% CI of
the paired difference excludes 0 in both comparisons. Paired bootstrap over shared states, since
all three are measured on the same states.

| verdict | condition |
|---|---|
| `SUPPORTED` | ≥ 5 of the 8 measures discriminate for Lucario, and **no** measure discriminates in the opposite direction (`d_I` or `d_A` > `d_L` with CI excluding 0) |
| `PARTIALLY_SUPPORTED` | ≥ 2 measures discriminate for Lucario, and Lucario's point estimate is highest on a majority of the 8 |
| `NOT_SUPPORTED` | ≥ 2 measures discriminate in the **opposite** direction, or Lucario is not highest on a majority |
| `INCONCLUSIVE` | the primary subset has `n < 100` shared states, or fewer than 5 measures are computable, or every CI spans 0 |

`INCONCLUSIVE` is checked **first**: an underpowered panel is reported as underpowered, never as
`NOT_SUPPORTED`.

## 7. Explicitly out of scope as evidence

- **Deck composition overlap.** Measured and reported as context (dragapult∩iono = 5 cards,
  dragapult∩lucario = 3, dragapult∩abomasnow = 2 distinct IDs). It is deck similarity, not policy
  similarity, and §24 asks about policy. It cannot contribute to the verdict.
- **Source-code similarity** between the four agents. Not among §22/§23's registered measures.
  Supplementary only.
- **Win rates.** §15 forbids concluding overlap from them.

## 8. Operationalisation stated openly

§22's final bullet asks for "agreement on states where teacher/Lucario transfer gains were
observed." **No such state set is registered in c010–c012** — those contracts recorded per-opponent
score aggregates, not per-state gain attributions. It is therefore operationalised here as: states
arising in games whose *opponent seat* is Mega Lucario. This is a defensible reading, it is not
pre-registered by an earlier contract, and it is labelled as an operationalisation in the report
rather than presented as a pre-existing set.
