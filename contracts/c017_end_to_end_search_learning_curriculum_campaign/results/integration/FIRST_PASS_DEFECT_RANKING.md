# First-pass defect ranking and consolidated repair (§31/§32)

The thin end-to-end smoke exists to expose interface and systems defects. It found **6**, ranked below by impact on the campaign's ability to run the vertical at all.

| rank | defect | severity | block | impact | fixed |
|---|---|---|---|---|---|
| 1 | `D1_nested_clone_segfault` | CRITICAL | A | removes forward search from the campaign entirely | yes |
| 2 | `D4_none_board_slots` | HIGH | A | agent errored on the first decision of every game; 0 games completed | yes |
| 3 | `D5_global_node_budget` | HIGH | A | 249 of 266 searches aborted before scoring any candidate | yes |
| 4 | `D3_none_reward_comparison` | HIGH | B | every game marked ERROR and its true outcome destroyed | yes |
| 5 | `D2_sorted_over_none_ids` | HIGH | A | TypeError on every game during redaction | yes |
| 6 | `D6_wrong_featuriser` | MEDIUM | C | distillation could not start | yes |

## The defect that mattered most

`D1_nested_clone_segfault` is **permanently unfixable**: `env.clone()` shares native `libcg.so` state with its parent, so advancing a clone core-dumps the process. Forward search is therefore impossible in this simulator, which is why the campaign runs in `OFFLINE_TEACHER_MODE` with a depth-0 ranker and why every downstream artifact is tainted by probe P10.

## The defect worth learning from

`D3_none_reward_comparison` was the most damaging to diagnose, because the bug was in the **error handling**: an except-block overwrote the observed episode statuses with `ERROR`, destroying the evidence needed to identify the other defects. Three of the six were invisible as errors until tracebacks were captured inside the agent callback.

## Rerun scope (§32)

Reran from the earliest affected milestone — trajectory generation — because Block A feeds every later block. Distillation, curriculum and the final panel all ran on post-repair data.
