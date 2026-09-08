# Files changed (c012)

New c012 source only; no file under c005-c011 modified.

```
 .../results/failures/.gitkeep                      |   0
 .../failures/DEFECT_inrun_evaluation_stale_hash.md |  92 ++++
 tests/test_c012_continuation.py                    | 143 ++++++
 tests/test_c012_rng_restore.py                     |  96 ++++
 tools/c012_build_source_bundle.py                  | 335 ++++++++++++++
 tools/c012_claude_label.py                         | 213 +++++++++
 tools/c012_claude_qualify.py                       | 201 ++++++++
 tools/c012_consolidate.py                          | 110 +++++
 tools/c012_decide.py                               | 290 ++++++++++++
 tools/c012_elite.py                                | 261 +++++++++++
 tools/c012_eval.py                                 | 356 ++++++++++++++
 tools/c012_hard_states.py                          | 191 ++++++++
 tools/c012_overlap.py                              | 315 +++++++++++++
 tools/c012_phase0.py                               | 276 +++++++++++
 tools/c012_ppo.py                                  |  54 +++
 tools/c012_reports.py                              | 124 +++++
 tools/c012_summary.py                              | 147 ++++++
 tools/c012_train_population.py                     | 509 +++++++++++++++++++++
 tools/c012_trainer_state.py                        | 128 ++++++
 tools/c012_validate_evidence.py                    | 202 ++++++++
 20 files changed, 4043 insertions(+)
```
