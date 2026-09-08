# c018 Pre-Registered Decision Rules

Committed **before** the final panel is run and before any c018 upload. Nothing below may be
edited after panel results exist; a later change must be recorded as a separate amendment with
its own commit and an explicit reason.

Reason for pre-registration: with four candidates, four opponents and two seats there are many
defensible ways to slice the same games, and picking the slice after seeing the numbers is how
a weak candidate gets promoted. Fixing the rule first makes the ranking a measurement rather
than a choice.

## 1. Candidates

| id | what it is | what it isolates |
|---|---|---|
| `official_mega_lucario` | the official sample agent, byte-identical | the incumbent baseline |
| `m01_heuristic_search` | baseline + real official-API forward search, heuristic leaf | what search alone buys |
| `m04_guided_search` | the same search, with learned ordering and learned leaf values | what guidance adds to search |
| `m03_curriculum_policy` | the trained policy playing directly, no search | what training alone buys |

All four share one deck (`mega_lucario`) and one baseline. The differences are the search layer
and the learned components, so the comparison attributes any gap to those and not to deck choice.

## 2. Panel protocol

- Opponents: `dragapult`, `iono`, `mega_abomasnow`, `mega_lucario`.
- The pairing schedule is constructed once, before any game runs. Every candidate faces the
  same opponent at the same seed and the same seat. A candidate added later cannot draw an
  easier field.
- Seats alternate within each pair so no candidate is measured only on the play or only on the
  draw.
- Floor: ≥ 600 scored games across candidates; target 1,200–2,000.
- Aggregates are recomputed from raw per-game rows using each row's own `candidate_id` and
  `opponent_id`. Worker results are never positionally zipped onto the job list.

## 3. Ranking rule

Lexicographic:

1. `overall_rate` descending;
2. then `worst_matchup_rate` descending.

The tie-break is deliberate: a candidate that is excellent overall but loses badly to one real
public archetype is worse on a live ladder than one that is merely even everywhere, because the
ladder will keep pairing it against that archetype.

Wilson 95% intervals are reported for every rate. They are reported, not used as the rule —
adding a significance filter after the fact is itself a post-hoc choice.

## 4. Promotion gate for a c018 upload

The c018 envelope allows **two** post-baseline uploads.

**Upload 1 — trusted heuristic-search candidate.** Eligible when all of:

- P03 (hidden information) is `PASS` and reports zero runtime violations;
- zero illegal actions across the panel and zero in clean-extraction validation;
- clean extraction plays every validation game to a terminal state with the repo off
  `sys.path`;
- the archive hashes to the value in its own manifest;
- the P90 evidence validator reports zero submission blockers.

Performance is **not** a gate for upload 1. The contract's §8.2 blockers are safety and
integrity conditions, and it states explicitly that weak performance does not stop the pipeline.
Upload 1 exists to put a *trusted* post-baseline candidate on the ladder.

**Upload 2 — strongest trained or guided candidate.** Eligible only when, in addition to every
condition above:

- it ranks strictly above the upload-1 candidate under §3 on the same panel; **and**
- its `overall_rate` point estimate is at least as high as `official_mega_lucario`'s.

If no trained or guided candidate meets both, **upload 2 is not used**. Spending it on a
candidate the panel says is worse would be buying a ladder slot with evidence pointing the other
way. c016 established that from-scratch agents in this project have repeatedly lost to the
official ones; the burden of proof sits with the challenger.

## 5. What the public score does and does not mean

The competition's public score is a **live ladder rating**, not a fixed evaluation of the
submitted agent. It moves by 100+ points within minutes as other entrants play, and 600.0 is the
provisional starting value shown before enough games have accumulated. Therefore:

- an accepted submission is evidence the package is *valid*, not that it is *strong*;
- no c018 conclusion about candidate strength may cite a public score;
- the frozen panel is the only strength claim this contract will make.

## 6. Declared confounds

- **Within-block curriculum win rates are not comparable across blocks.** As the self-play share
  rises, the opponent field changes; a rising win rate there measures a changing field, not a
  improving policy. Only the frozen panel compares like with like.
- **Top-1 agreement is first-pick agreement.** The stored supervised label is `label_action[0]`,
  so on multi-select decisions the metric says nothing about the remainder of the selection.
- **Agreement with the search is not strength.** A model that perfectly imitates the search
  inherits the search's mistakes. P09/P10 measure imitation; only P17 measures play.

## 7. Status rule

- `PASS` requires every §6.1 execution floor met, no unresolved submission blocker, and at least
  one **accepted** post-baseline c018 submission.
- `PARTIAL` where the campaign produced trusted, useful, fully evidenced artifacts but missed a
  floor or a milestone.
- `FAIL` where the central claims cannot be supported by raw evidence.

A missed floor is reported as missed. It is never re-described as a target that was
"substantially met".

---

# Amendment 1 — split guided search into ordering-only and ordering+value

**Committed before the final panel was run.** No panel results existed at the time of this
amendment; the trigger is an *offline* held-out metric, not a gameplay result.

## Trigger

P10's deep held-out metrics (`artifacts/heldout_metrics.json`) measured the value head against
the honest constant baseline — predicting the training-set mean outcome:

| | held-out MSE |
|---|---|
| learned value head | 0.267 |
| constant baseline | 0.216 |

with correlation 0.146 against the actual result. **The value head is worse than a constant.**

## Why this changes the candidate set

`m04_guided_search` uses the learned model twice: to order candidates at the root, and to
evaluate leaves. Those are separate mechanisms, and P10 says one of them carries almost no
signal. A single guided candidate would therefore confound a possibly-useful policy ordering
with a measurably weak value head, and whatever the panel returned, the campaign could not say
which component was responsible.

## Change

Add exactly one candidate, `m04_guided_ordering_only`: identical search, learned ordering at the
root, **hand-written heuristic leaf values**. `m04_guided_search` is unchanged and keeps both
mechanisms.

The panel schedule is rebuilt with five candidates before any game runs, so every candidate
still faces identical opponents, seeds and seats (§2 is unaffected). §3's ranking rule and §4's
promotion gates are unchanged and apply to the new candidate exactly as written.

## Why this is not post-hoc tuning

The evidence used is an imitation metric computed on held-out *training* data, which §5 already
declares is not a strength claim. It cannot tell us which candidate wins the panel. It tells us
only that the two guidance mechanisms deserve separate measurement — a decomposition that should
arguably have been in §1 from the start.

Had this been triggered by panel results, it would be exactly the post-hoc selection §1 exists
to prevent, and it would not have been made.

---

# Amendment 2 — add the distilled policy as its own stage

**Committed before the final panel was run.** Trigger is a contract requirement, not a result.

## Trigger

CONTRACT §29 names six stages that must be preserved, and §31's P17 lists the panel candidates
explicitly, including *distilled policy* as separate from *best curriculum policy*. The
candidate set in §1 (as amended) covered five of the six: `POLICY_DISTILLED_REAL_SEARCH` had no
candidate, because the guided candidates all load the M03 curriculum checkpoint.

## Change

Add exactly one candidate, `m02_distilled_policy`: the M02 search-distilled checkpoint exported
to the runtime NPZ format and played directly through the same `RLAgent` the curriculum used.

The candidate set is now the six §29 stages in order:

| stage | candidate |
|---|---|
| `BASELINE_OFFICIAL_LUCARIO` | `official_mega_lucario` |
| `SEARCH_HEURISTIC_REAL` | `m01_heuristic_search` |
| `POLICY_DISTILLED_REAL_SEARCH` | `m02_distilled_policy` |
| `POLICY_CURRICULUM_BEST` | `m03_curriculum_policy` |
| `SEARCH_POLICY_ORDERED_REAL` | `m04_guided_ordering_only` |
| `SEARCH_POLICY_VALUE_GUIDED_REAL` | `m04_guided_search` |

## Why it matters as a separate stage

Without it, distillation and the PPO curriculum on top of it are measured only as a single
combined artifact. Verified distinct before the panel: the two checkpoints differ on all 32
tensors, maximum absolute weight delta 0.0515, and their file hashes differ — so these are two
agents, not one candidate entered twice.

## Panel size

Six candidates × 4 opponents × 100 games per pair = **2,400 scored games**, which is above the
§32 target band of 1,200–2,000 and well above the 600 floor. Exceeding a target band with more
evidence is recorded as what it is, not presented as sitting inside the band.

§2's protocol, §3's ranking rule and §4's promotion gates are unchanged and apply to the new
candidate exactly as written.

---

# Amendment 3 — correct §4's upload-1 gate to match CONTRACT §16 and §34

**Committed before the final panel was run.** No panel results existed. This corrects a
misreading of the contract in my own §4, not a rule I found inconvenient after seeing numbers.

## The error

§4 stated: *"Performance is not a gate for upload 1."* That was wrong. It generalised from §8.2
(which lists safety and integrity blockers, and does say weak performance does not stop the
*pipeline*) to the *submission* decision, which §16 and §34 govern separately:

- **§16** gives a promotion/submission signal for heuristic search: **+3pp** on the broad field
  with no serious matchup collapse; or **+5pp** on one pre-registered important matchup with
  field non-inferiority; or a major reduction in registered tactical errors with no broad-field
  regression and credible external information value.
- **§34** requires that *"local evidence provides a meaningful improvement or credible
  high-information challenger signal"*, and states plainly: *"Do not upload a candidate known
  to be catastrophically weaker or tainted by a submission blocker."*

So there is a performance condition. It is simply disjunctive — improvement **or** high
information — and I collapsed it to "none".

## Corrected gate for upload 1 (`SEARCH_HEURISTIC_REAL`)

All safety and package gates from the original §4 still apply and are unchanged. In addition,
exactly one of the following must hold on the frozen panel:

- **(a) Improvement.** `overall_rate` ≥ `official_mega_lucario` + 0.03, and no matchup below
  0.15. (§16 clause 1.)
- **(b) Important-matchup improvement.** ≥ +0.05 against `dragapult` — pre-registered here as
  the important matchup, because §39 names Dragapult the externally confirmed champion — with
  `overall_rate` no worse than baseline − 0.02. (§16 clause 2.)
- **(c) High-information near-parity.** `overall_rate` ≥ `official_mega_lucario` − 0.05 **and**
  no matchup below 0.10. (§34's "credible high-information challenger signal".)

Rationale for (c): this is the first agent in this project built on real official-API forward
search, and the project has already established that the public score is a live ladder rating
rather than a fixed evaluation. Whether an offline panel result transfers to that ladder is
genuinely unknown and worth one upload — but only at near-parity. A candidate more than 5
points below the baseline is "known to be catastrophically weaker" in §34's sense, and the
information value of confirming it loses is not worth a ladder slot.

## If no candidate clears any of (a), (b), (c)

**No upload is made, and c018 cannot reach `PASS`** — §6.1 requires at least one accepted
post-baseline submission. The honest status is then `PARTIAL`, which §38 explicitly provides
for: *"training is real but does not improve gameplay."*

That outcome is recorded as the finding, not as a failure to act. Uploading a candidate the
panel says is clearly worse, purely to satisfy a floor and reach `PASS`, would be buying a
status word with evidence pointing the other way — the precise behaviour §40 prohibits when it
says not to submit a known catastrophically weak candidate.

Upload 2's gate (§4, unchanged) still requires outranking upload 1 *and* matching the official
baseline, so it remains strictly harder than upload 1.
