# P01 — Native search lifecycle

Establishes that the official API supports real multi-step forward search:
`to_observation_class` → `search_begin` → `search_step`(xN) → `search_release` → `search_end`.

## Result

Real search works. Six `search_step` calls succeeded across depth 3, producing distinct child
search IDs and distinct successor observations, and the parent episode still finished
`DONE/DONE` — no corruption and no crash.

## This corrects a c017 error

c017's probe P10 concluded "forward simulation is impossible in this simulator" and the whole
campaign was rebuilt around that: `OFFLINE_TEACHER_MODE`, a depth-0 heuristic ranker, and every
downstream artifact tainted as unable to support any lookahead claim.

That conclusion was **wrong**. It was drawn from `env.clone()` — the `kaggle_environments`
wrapper — segfaulting when a cloned episode was advanced. The official SDK provides a dedicated
search interface that does exactly this safely, in the same `cg/api.py` that c017 already read
for other purposes, and whose input field `search_begin_input` appeared in a c017 probe's own
observation dump without being followed up.

The error was not that the simulator lacked the capability. It was testing one interface,
finding it broken, and generalising to the simulator.

## Determinization requirement

`search_begin` requires predicted hidden cards — opponent deck, prizes, hand, and face-down
active. Search therefore cannot begin without an explicit determinization of hidden information,
which is why §-level hidden-information auditing (P03) applies to the determinizer and not only
to the state reader.
