# c019 SUMMARY — status PARTIAL

Method fidelity and competitive strength are reported separately, as CONTRACT §15 requires.
A method-faithful agent that loses is a competitive failure, and saying so is the point.

| | MCTS | ByteRL |
|---|---|---|
| **method fidelity** | PASS | PASS |
| **competitive** | NOT CREDIBLE -- -12.5 field points vs the frozen baseline | IN PROGRESS |

## 1. Did a faithful information-set MCTS beat the frozen baseline?

**No.** Two panels, at two configurations, both decisive:

| configuration | MCTS field | baseline field | delta |
|---|---|---|---|
| package (12 sims x 1 determinization) | 0.3917 | 0.5167 | **-12.5 pts** |
| registered (48 x 3) | 0.3833 | 0.5833 | **-20.0 pts** |

More search made it **worse**. Both gaps are several times the baseline's own run-to-run spread
and consistent in direction, so this is a result rather than noise.

The DECISION_RULES gate (field +3 points, or a matchup +5 without field regression) is enforced
in `tools/c019_submit.py` and returns `BLOCKED_BY_GATE`. No matchup improved.

## 2. Is the MCTS actually MCTS?

Yes, and every c018 failure mode is inverted:

| property | evidence |
|---|---|
| non-root expansion (M03) | **546,162** non-root expansions; 232 trees with a branching non-root node |
| revisits (M06) | **973,454** |
| backup (M05) | 694,834 backups over **2,319,821** node updates |
| rollout policy (M07) | **10,086,419** branch-local baseline calls, zero option-0 continuation |
| determinization (M02) | 17,592 legal, **0** rejected, no duplicate filler |
| lifecycle (M10) | **0** release errors |
| hidden information (P02) | **0** violations |
| `c_puct` is real (M04) | a fixture shows it changing which child is selected |

### MCTS execution floors

| floor | actual | required | |
|---|---|---|---|
| searched live decisions | 7,549 | 5,000 | met |
| simulations or native expansions | 1,346,381 | 500,000 | met |
| decisions using multiple determinizations | 7,549 | 1,000 | met |
| complete sampled tree traces | 116 | 100 | met |
| common-panel games baseline vs MCTS | 840 | 800 | met |

## 3. ByteRL

**Training was still in progress at report time.**
42,880 actual simulator games (42,880
completed), 22,553 optimizer steps,
2 complete learning periods,
1 immutable historical additions.

| floor | actual | required | |
|---|---|---|---|
| actual simulator games | 42,880 | 60,000 | **MISSED** |
| optimizer steps | 22,553 | 20,000 | met |
| complete OSFP learning periods | 2 | 5 | **MISSED** |
| immutable historical additions | 1 | 2 | **MISSED** |
| games involving historical checkpoints | 9,112 | 1,000 | met |
| common-panel/milestone evaluation games | 0 | 800 | **MISSED** |

## 4. Common panel

| panel | candidate | field | 95% CI | worst matchup |
|---|---|---|---|---|
| mcts_gate2 | baseline_official_mega_lucario | 0.5778 | [0.5047, 0.6476] | mega_lucario @ 0.4222 |
| mcts_gate2 | ptcg_ismcts_v0 | 0.4611 | [0.3899, 0.534] | mega_lucario @ 0.3778 |
| mcts_gate | baseline_official_mega_lucario | 0.5167 | [0.4281, 0.6042] | dragapult @ 0.3667 |
| mcts_gate | ptcg_ismcts_v0 | 0.3917 | [0.309, 0.4811] | mega_abomasnow @ 0.3 |
| mcts_full | baseline_official_mega_lucario | 0.5833 | [0.4939, 0.6676] | mega_abomasnow @ 0.4 |
| mcts_full | ptcg_ismcts_v0 | 0.3833 | [0.3012, 0.4727] | mega_lucario @ 0.3333 |

**Recorded limitation.** `make("cabt")` exposes no seed, so deck shuffles and coin flips are not
paired between candidates — only opponents, seats and agent-side RNG are. Differences inside the
Wilson intervals must not be read as method differences. See
`failures/LIMITATION_panel_cannot_pair_environment_randomness.md`.

## 5. Match-clock safety

At the registered configuration search costs 31.2s
mean and 45.7s maximum per match, against a
baseline whose entire game takes about 1.2s. The package configuration costs 4.6s mean / 7.7s
max. The gate panel evaluated the configuration that would actually ship.

## 6. Hybrid

Adapters implemented and switchable, defaulting off; `c019_mcts.py` imports nothing from any
ByteRL module, so H03 is structural. The leaf-value adapter refuses to act until calibration
shows it beats both a constant and the heuristic. **Not competitively evaluated:** §10 caps
hybrid work and forbids delaying pure submissions, and the pure MCTS branch did not clear its
gate, so a hybrid built on it had no path to promotion.

## 7. Probes

| probe | status |
|---|---|
| B01 | PASS |
| B02 | PASS |
| B03 | PASS |
| B04 | PASS |
| B05 | PASS |
| B06 | PASS |
| B07 | PASS |
| B08 | PASS |
| B09 | PASS |
| B10 | PASS |
| B11 | NOT_EXERCISED |
| B12 | NOT_EXERCISED |
| B13 | PASS |
| F01 | PASS |
| F02 | PASS |
| F03 | PASS |
| F04 | NOT_EXERCISED |
| H01 | WARN |
| H02 | WARN |
| H03 | PASS |
| M01 | PASS |
| M02 | PASS |
| M03 | PASS |
| M04 | PASS |
| M05 | PASS |
| M06 | PASS |
| M07 | PASS |
| M08 | PASS |
| M09 | PASS |
| M10 | PASS |
| M11 | WARN |
| M12 | PASS |
| P00 | PASS |
| P01 | PASS |
| P02 | PASS |
| P03 | PASS |

## 8. Validator

51/57 checks, 0 critical
failures, 0 submission blockers. Written before the runs it
judges; every check recounts from raw rows.

It earned that design: it caught a defect where the ByteRL summary reported 20,000 games and
2,500 optimizer steps while the raw rows held 12,000 games, **zero completed**, averaging 0.8
decisions. `kaggle_environments` passes `(observation, configuration)` to any agent accepting two
parameters, so default-argument closure capture had replaced the model with a config object and
every self-play opponent seat errored. See `failures/`.

## 9. Decision board

| role | id | basis |
|---|---|---|
| CHAMPION | dragapult | externally confirmed control (~719.7 in captured evidence); no c019 candidate has beaten it on external eviden |
| CHALLENGER | baseline_official_mega_lucario | accepted submission 55011215; strongest measured candidate on the c019 common panel |
| DIAGNOSTIC | ptcg_ismcts_v0 | method-faithful and package-safe, but -12.5 field points below the frozen baseline; DECISION_RULES gate not me |
| IN_PROGRESS | ptcg_byterl_v0 | training run incomplete at report time |
| ARCHIVE | c018_search_and_curriculum | root-only search and schedule-driven self-play; disproven as MCTS and as OSFP, not continued by c019 |

## 10. Submissions

None. No candidate cleared its pre-registered credibility gate, and §34-equivalent rules forbid uploading a candidate known to be materially weaker.

## 11. Exactly one next externally relevant action

**Submit the official agent for a different deck — `official_iono` or `official_mega_abomasnow`,
both already packaged and validated by c016 — and measure it on the live ladder.**

c019 answered its first question decisively and negatively: a faithful information-set MCTS,
with real PUCT, non-root expansion, legal determinization and branch-local rollouts, is
**20 points worse** than the scripted baseline it wraps, and more search widens the gap. That
points at the leaf evaluator and at the scripted baseline's own strength, not at more search
depth or a third algorithm. Meanwhile the strongest thing measured on the common panel remains
the untouched official agent.

Deck choice is the one externally testable variable this project has never moved, it needs no
new implementation, and unlike further search or training work it produces external evidence
immediately.
