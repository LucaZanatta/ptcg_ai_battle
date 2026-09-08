# F01 — Common-panel identity safety

Every raw row carries its own `candidate_id`, `opponent_id`, `seat` and `seed`, and aggregates are recomputed from those fields — worker results are never positionally zipped back onto the job list.

**Recorded limitation:** `make('cabt')` exposes no seed, so deck shuffles and coin flips are NOT paired between candidates. The protocol states exactly what is and is not controlled; see `failures/LIMITATION_panel_cannot_pair_environment_randomness.md`.

**Status: PASS.**
