# B04 — Canonical action round trip

757 of 757 real select contexts reconstruct the exact environment payload, including 32 of 32 MULTI-select contexts.

The multi-select column is the one that matters: an option identified by index rather than by key, or a payload built with the wrong cardinality, produces a legal-looking action that is not the action selected. The c020 search failed exactly this way before the repair pass — it stepped every multi-select context with a single option and the engine rejected it.
