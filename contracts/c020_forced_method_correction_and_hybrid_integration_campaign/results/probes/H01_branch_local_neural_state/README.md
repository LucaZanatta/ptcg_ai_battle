# H01 — Branch-local neural state

`state_none_at_nonroot` = **0** across all executed modes, with 1697 recurrent advances through simulated transitions. Sibling nodes hold cloned tensors, never shared mutable state.

c019 called the recurrent model with `state=None` at every search node (audit #14) — a recurrent policy evaluated from a blank memory is not the policy that was trained; it is that network's opinion about a game that just started, applied twenty decisions deep.
