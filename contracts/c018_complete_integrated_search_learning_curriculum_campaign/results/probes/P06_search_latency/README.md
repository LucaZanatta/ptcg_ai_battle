# P06 — Search latency and resource safety

Per-decision search cost over 42,857 timed decisions: p50 2.4 ms, p90
3.6 ms, p99 5.7 ms, max 341.3 ms, against a
2500 ms budget. 0 decisions exceeded it and
fell back.

**Handle hygiene.** Every `search_begin` opens native state that must be released or the process
leaks across a match. 652,732 releases and 42,857
`search_end` calls with 0 errors — the lifecycle is wrapped in a context
manager, so an exception mid-beam still releases. This is what makes the search safe to run
inside a submitted agent rather than only offline.

**Throughput and memory.** 94.33 search roots/s, 1329.34
`search_step`/s, 2,952 determinizations, process RSS 299.3 MB, and
a mean full-match agent time of 2.3 ms.

609,875 nodes expanded, 14.2 per searched
decision, under a per-decision node cap. That cap is per-decision for two reasons: c017's global
cap starved 249 of 266 searches, and a *cumulative* cap that depended on a caller-maintained
counter later left the packaged agent searching 3 of 84 decisions
(`failures/DEFECT_packaged_agent_searched_3_of_84_decisions.md`).

`search_begin_input` preserved: True. Repeated searches on one
root remained stable with zero begin/release errors: True.

**Status: PASS.**
