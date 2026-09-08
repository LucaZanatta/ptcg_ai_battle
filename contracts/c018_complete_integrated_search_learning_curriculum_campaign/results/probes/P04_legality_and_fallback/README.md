# P04 — Legality and fallback

**Legality.** 47,086 search-chosen actions were revalidated against the live option set
before being played; 0 were rejected. All 900/900
games ran to a terminal state, so no search action wedged the engine.

**Fallback.** 4,229 decisions (8.98%) declined to search and
played the baseline heuristic action instead
(forced_or_match_budget=4,229). The baseline is always candidate 0 and
is never pruned, so the search can only *improve on* or *return* the baseline — it retained the
baseline 31,105 times and changed it 11,752 times.

That asymmetry is the package-safety argument: under a timeout, a determinization failure, or an
engine error, the agent degrades to the heuristic it would otherwise have played.

**Status: PASS.**
