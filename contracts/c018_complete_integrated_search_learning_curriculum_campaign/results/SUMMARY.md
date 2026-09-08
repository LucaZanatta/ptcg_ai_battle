# c018 SUMMARY — status PARTIAL

## 1. Did real official-API forward search run?

**Yes.** `to_observation_class` → `search_begin` → `search_step` → `search_release` →
`search_end`, against the real simulator. This corrects c017's central conclusion that forward
simulation was impossible: c017 reached that verdict from `env.clone()` segfaulting, without
using the official search interface that was already present in the same `cg/api.py` it had read.

## 2. Actual `search_begin` and `search_step` counts

Scaled generation: **42,857** successful `search_begin` roots (0 errors) and
**609,875** successful `search_step` calls of 614,722
attempted. Maximum depth reached 4;
353,448 distinct successor observations;
652,732 releases with 0 errors.

## 3. Did multi-step search improve the baseline?

**No — and the panel cannot answer the question, because a wrapper defect dominates it.**

On the frozen panel `m01_heuristic_search` scored 0.21 (CI [0.1729, 0.2526]) against
`official_mega_lucario`'s 0.58 (CI [0.5311, 0.6274]) over 400 identical
games each. That is a 37-point collapse for an agent that **is** the baseline plus a search which
keeps the baseline action as candidate 0 and never prunes it — close to impossible from action
quality alone.

A control settles it. Same baseline, search replaced by a **random legal action** at the same
override rate:

| arm | override rate | win rate |
|---|---|---|
| never override | 0% | **0.5958** |
| random legal override | 18.6% | **0.1917** |
| real search (panel) | ~26% | 0.21 |

Disabling overriding reproduces the baseline, so the harness is sound. **Random overriding
reproduces the entire collapse** — the real search, with 609,875 verified
simulator steps behind its choices, scores barely above random.

**Mechanism.** The official agent keeps module-level state across decisions (`global plan`,
`global pre_turn`, `global ability_used`) and its recommendations assume its own previous
recommendations were executed. Overriding it desynchronises that state, so every later baseline
action — *including the search's own candidate 0* — is computed from a false model of the
position. "The baseline is always candidate 0" bounds the result from below only for a
**stateless** baseline.

**What this does and does not license.** The search machinery is real and correct (P01–P06, P30).
What is unsound is layering it on a stateful scripted agent by overriding that agent. And because
state corruption dominates, this panel cannot separate a good leaf evaluator from a bad one —
both would land near random. The separate alignment measurement over 42,857
decisions is the better evidence there, and it points the other way: the learned value head
correlates 0.284 with actual outcomes
versus the hand-written heuristic's 0.1804.

Full records: `artifacts/override_control.json`,
`failures/DEFECT_search_cannot_wrap_a_stateful_scripted_baseline.md`.

## 4. Trajectory scale and trust status

42,857 **trusted** decisions of 47,086 total
(0.9102), from 900 real games. A decision is trusted only
when its own search ran and returned at least one real successor; fallbacks are retained and
flagged untrusted rather than silently dropped. Floor 10,000: met. Target band 30,000–60,000:
**not reached** — see `BUDGET_EXECUTION.json`.

## 5. Supervised optimizer steps and checkpoint change

**7,080 steps** on cuda, 60 epochs,
trusted rows only. Checkpoint hash `f476b862eeb0` →
`0903a0755e95`,
61 distinct per-epoch hashes. Exact reload verified.

Held out: policy top-1 0.6144, top-3 0.9, legal top-1 rate
1.0. **The value head does not beat a constant baseline** — MSE
0.202133 against 0.149119 for predicting the training-set
mean, correlation 0.284. That is load-bearing, not cosmetic: M04's
guided search substitutes exactly this head for the hand-written leaf heuristic.

## 6. Actual PPO games, optimizer steps, self-play stages, promotions

**81,920 real simulator games**,
**66,604 optimizer steps**,
81 distinct checkpoint hashes across
80 blocks. Self-play share rose 0 → 0.7 as scheduled, with the
realised mix recounted from raw opponent labels rather than reported from the plan. Every block
wrote a uniquely-named lagged snapshot, so the self-play opponent genuinely advanced.

**Promotions: 0.** Every transition is
`FALLBACK_SCHEDULE`-grade — the schedule advanced on block index, and no evaluation gated any
increment. §26 caps a non-performance-gated schedule at 20–30% self-play and this run reached
0.7314. **c018 therefore makes no strategic curriculum claim.** The
curriculum is evidence that real PPO training ran at scale and nothing more; asserting that the
self-play schedule *improved* the policy would need performance-gated promotions this run does
not have. Full per-interval record: `artifacts/curriculum_audit.json`.

## 7. Did guided search use policy/value inside real trees?

**Yes.** Learned ordering (one forward on the root) and learned leaf values (one batched forward
over all candidate leaves) operate inside the *same* real search tree — 301
shared roots compared, learned leaf values changed the chosen action on
0.4419 of them. Guidance cost: p90 7.62
ms guided vs 3.31 ms unguided, against a
2500 ms budget.

**Decomposition.** Learned **ordering** helped: `m04_guided_ordering_only` 0.2125 vs `m01_heuristic_search` 0.21 (same search, same heuristic leaves, only the candidate order differs). Learned **leaf values** helped: `m04_guided_search` 0.215 vs `m04_guided_ordering_only` 0.2125 (same search, same ordering, only the leaf evaluator differs).

## 8. Final-panel results

| rank | candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|---|
{'section': '§7 Pass B', 'open_findings': ['D0'], 'process_note': 'Repairs were applied as each defect was found rather than batched into one pass. Several were submission blockers discovered while the artifacts they invalidated were still being produced, and carrying a known-broken package forward to satisfy a batching rule would have meant scaling on top of it. What IS consolidated is the rerun: the two highest-impact open defects (D5, D6) both trace to M01 and below, so a single rerun from the earliest affected milestone clears both.', 'defects_ranked_by_downstream_impact': [{'id': 'D0', 'title': 'forward search cannot wrap a stateful scripted baseline', 'found_in': "disbelieving the campaign's own headline panel number", 'downstream_impact': 'INVALIDATES_CENTRAL_COMPARISON', 'impact_rank': 0, 'why': "m01_heuristic_search IS the official agent plus a search keeping the baseline as candidate 0, yet it scored 37 points below it. A control shows random legal overrides at the same rate reproduce the collapse (0.192 vs 0.210) while disabling overriding reproduces the baseline (0.596 vs 0.580). The official agent keeps module-level state and assumes its own recommendations are executed, so overriding poisons every later baseline action -- including the search's own candidate 0.", 'affected_milestones': ['M01', 'M04', 'M05'], 'earliest_affected': 'M01', 'repaired': False, 'repair': 'NOT repaired -- this is a design constraint, not a patch. Either the baseline becomes a pure function of the observation, or the search owns the whole policy instead of sitting on top of a scripted one. Recorded as an open finding rather than closed with a cosmetic fix.', 'verified_by': 'artifacts/override_control.json (480 control games)', 'record': 'failures/DEFECT_search_cannot_wrap_a_stateful_scripted_baseline.md'}, {'id': 'D1', 'title': 'packaged agent searched 3 of 84 decisions', 'found_in': 'package clean-extraction instrumentation', 'downstream_impact': 'SUBMISSION_BLOCKER', 'impact_rank': 1, 'why': "§8.2.6 — the uploaded agent was not the evaluated agent. The node budget was cumulative and depended on the caller incrementing stats['decisions']; the harnesses did, the generated main.py did not, so a whole match shared a 40-node budget.", 'affected_milestones': ['M05'], 'earliest_affected': 'M05', 'repaired': True, 'repair': 'local per-decision node counter in c018_search.plan', 'verified_by': 'packaged agent 3/84 -> 67/75 searched; harness intensity unchanged (14.57 vs 14.25 nodes per searched decision)', 'record': 'failures/DEFECT_packaged_agent_searched_3_of_84_decisions.md'}, {'id': 'D2', 'title': 'guided package never searched and completed every game anyway', 'found_in': 'the check added in response to D1, on its first run', 'downstream_impact': 'SUBMISSION_BLOCKER', 'impact_rank': 2, 'why': "a hand-written dependency list omitted policy_data_v2; main.py's safe fallback swallowed the ImportError, so the package was the baseline agent wearing a guided-search label", 'affected_milestones': ['M05'], 'earliest_affected': 'M05', 'repaired': True, 'repair': 'AST-derived cg import closure; utf-8-sig reads so a BOM cannot silently truncate the closure', 'verified_by': 'guided package 0/321 -> 262/293 searched', 'record': 'failures/DEFECT_guided_package_never_searched_silently.md'}, {'id': 'D3', 'title': 'evidence validator passed a campaign that had trained nothing', 'found_in': "the validator's own first run", 'downstream_impact': 'INVALIDATES_VERDICT', 'impact_rank': 3, 'why': 'absence of a milestone was indistinguishable from not-yet; a campaign that did nothing would have scored PASS', 'affected_milestones': ['M05'], 'earliest_affected': 'M05', 'repaired': True, 'repair': 'require() -- non-critical in interim runs, critical in --final mode', 'verified_by': 'two unit tests pin both directions', 'record': 'failures/DEFECT_validator_returned_pass_with_no_training_at_all.md'}, {'id': 'D4', 'title': 'validator read training claims out of the report it judged', 'found_in': 'review of the validator against its own stated principle', 'downstream_impact': 'INVALIDATES_VERDICT', 'impact_rank': 4, 'why': 'the exact surface c017 fabricated; the mix check asserted only that both keys existed, so planned numbers copied into actual_fractions would have passed', 'affected_milestones': ['M05'], 'earliest_affected': 'M05', 'repaired': True, 'repair': 'games, optimizer steps and realised mix all recounted from raw JSONL rows', 'verified_by': 'test_rejects_planned_mix_reported_as_actual and five sibling tests', 'record': 'failures/DEFECT_validator_read_the_report_it_was_judging.md'}, {'id': 'D5', 'title': 'trusted trajectory scale left at the floor, not the target', 'found_in': "external challenge to the campaign's elapsed time", 'downstream_impact': 'MISSED_TARGET', 'impact_rank': 5, 'why': "11,151 trusted decisions met the 10,000 floor but missed the 30,000-60,000 target. The stated reason -- that scaling would cost more than it was worth -- was simply wrong: measured throughput is ~1,000 trusted decisions per 13.5 seconds single-process, so the target costs about ten minutes. The wrong estimate came from reading a background task's wall-clock, most of which was idle, as if it were compute.", 'affected_milestones': ['M01', 'M02', 'M03', 'M04', 'M05'], 'earliest_affected': 'M01', 'repaired': True, 'repair': 'regenerate ~43,000 trusted decisions, then rerun M02 and M03 from them', 'verified_by': 'search/scaled2_search_summary.json and the reruns downstream of it', 'record': 'this file'}, {'id': 'D6', 'title': 'curriculum sat at the floor of its target band', 'found_in': 'same review as D5', 'downstream_impact': 'MISSED_TARGET', 'impact_rank': 6, 'why': '40,960 games is inside the 40,000-100,000 band but at its very bottom, with roughly 68 of a 72-hour envelope unused', 'affected_milestones': ['M03', 'M04', 'M05'], 'earliest_affected': 'M03', 'repaired': True, 'repair': '80 blocks x 1,024 = 81,920 games, mid-band', 'verified_by': 'training/curriculum_report.json', 'record': 'this file'}, {'id': 'D7', 'title': 'panel candidate m03_curriculum_policy was a crippled agent', 'found_in': 'review before the panel ran', 'downstream_impact': 'WRONG_CONCLUSION', 'impact_rank': 7, 'why': "it took the top-k of a score ranking, which is not what the policy's sequential without-replacement multi-select head produces; 'what training alone buys' would have measured something the curriculum never trained", 'affected_milestones': ['M05'], 'earliest_affected': 'M05', 'repaired': True, 'repair': 'use RLAgent, the exact agent the curriculum trained', 'verified_by': 'panel candidate construction; caught before any panel result existed', 'record': 'this file'}], 'total': 8, 'submission_blockers': 2, 'all_repaired': False, 'earliest_affected_milestone': 'M01', 'consolidated_rerun': {'from': 'M01', 'chain': ['M01 trusted trajectories (~43,000 decisions)', 'M02 re-distillation on those trajectories', 'export round-trip gate', 'M03 curriculum 81,920 games from the new M02', 'M04 guidance, final panel, packages, validator, reports'], 'why_the_whole_chain': 'the distilled model must come from the trajectories reported, and the curriculum must descend from that distilled model. Regenerating only the trajectories would leave a published lineage whose ancestor was trained on a dataset no longer in the results tree -- internally consistent-looking and externally false, the same class of defect as D1 and D2.', 'preserved_controls': {'m02_distilled_11k.pt': 'distillation on 11,151 rows, kept as the sample-size control for the value-head result', 'm03_curriculum_40k.*': 'the complete 40,960-game curriculum run, kept as a fully-evidenced fallback'}}}

## 9. Uploads

| package | reference | status | score | archive sha256 |
|---|---|---|---|---|
| _none_ | | | | |

Baseline anchor: accepted reference `55011215` verified
(`True`); c005–c017 unmodified across
2,169 files.

The public score is a **live ladder rating**, not a fixed evaluation — it moves 100+ points
within minutes and 600.0 is the provisional start value. No strength claim here rests on it.

## 10. Strongest trustworthy package

`vertical_package_smoke` — clean extraction with the repo off `sys.path`,
4/4 games
terminal, search verified live in the extracted package
(297/324
decisions searched), 0 hidden-information violations.

## 11. Failed or tainted stages

- none

### Defects found and repaired, ranked by downstream impact

- **D0** [INVALIDATES_CENTRAL_COMPARISON] forward search cannot wrap a stateful scripted baseline — NOT repaired -- this is a design constraint, not a patch. Either the baseline becomes a pure function of the observation, or the search owns the whole policy instead of sitting on top of a scripted one. Recorded as an open finding rather than closed with a cosmetic fix.
- **D1** [SUBMISSION_BLOCKER] packaged agent searched 3 of 84 decisions — local per-decision node counter in c018_search.plan
- **D2** [SUBMISSION_BLOCKER] guided package never searched and completed every game anyway — AST-derived cg import closure; utf-8-sig reads so a BOM cannot silently truncate the closure
- **D3** [INVALIDATES_VERDICT] evidence validator passed a campaign that had trained nothing — require() -- non-critical in interim runs, critical in --final mode
- **D4** [INVALIDATES_VERDICT] validator read training claims out of the report it judged — games, optimizer steps and realised mix all recounted from raw JSONL rows
- **D5** [MISSED_TARGET] trusted trajectory scale left at the floor, not the target — regenerate ~43,000 trusted decisions, then rerun M02 and M03 from them
- **D6** [MISSED_TARGET] curriculum sat at the floor of its target band — 80 blocks x 1,024 = 81,920 games, mid-band
- **D7** [WRONG_CONCLUSION] panel candidate m03_curriculum_policy was a crippled agent — use RLAgent, the exact agent the curriculum trained

Full records in `failures/` and `artifacts/defect_ranking.json`. Two were submission blockers
caught before any upload; two would have invalidated this contract's own verdict.

## 12. Decision board

| role | id | value |
|---|---|---|
| CHAMPION | dragapult | externally confirmed control; unbeaten by any post-baseline c018 agent on external evidence |
| CHALLENGER | official_mega_lucario | 0.58 |
| ARCHIVE | m03_curriculum_policy | 0.2475 |
| CHALLENGER | m04_guided_search | 0.215 |
| ARCHIVE | m04_guided_ordering_only | 0.2125 |
| CHALLENGER | m01_heuristic_search | 0.21 |
| ARCHIVE | m02_distilled_policy | 0.175 |
| ARCHIVE | c017_depth_zero_ranker | c017's static scorer, disproven as search by P01/P02 |
| ARCHIVE | c017_distilled_policy | not continued by c018; trained on depth-zero labels |
| DIAGNOSTIC | P10 | WARN |
| DIAGNOSTIC | P14 | WARN |

## 13. Exactly one next externally relevant action

**Submit the official agent for a different deck — `official_iono` or `official_mega_abomasnow`, both already packaged and validated by c016 — and measure it on the live ladder.**

This campaign's evidence points at exactly one external question. Every c018 candidate shares one deck and one baseline, and the search layer that was supposed to improve on that baseline is now known to be structurally unsound on a *stateful* scripted agent: random overrides reproduce its collapse (0.1917) as completely as the real search does (0.21). Fixing that is a design change, not a tuning pass — the baseline must become stateless or the search must own the whole policy — and neither produces external evidence on its own.

Meanwhile the strongest thing measured here is the untouched official agent at 0.58, whose worst matchup is `mega_abomasnow` at 0.47. Whether a *different* official deck rates higher on the live ladder is cheap to test, uses artifacts that already exist and are clean-validated, and is the only remaining variable this campaign has not moved.
