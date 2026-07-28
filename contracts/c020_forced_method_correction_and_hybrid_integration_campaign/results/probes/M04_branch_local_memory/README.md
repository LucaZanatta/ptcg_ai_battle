# M04 — Branch-local memory parity and independence

`recommend` /`advance_after_executed` / `clone_memory`, with the official agent loaded unmodified. Installing a foreign memory demonstrably changes the module globals and restoring returns them exactly, so a simulated branch cannot leak into the real game.

The split between `recommend` and `advance_after_executed` is what A8 needs: when the search overrides, the baseline's memory advances along the action ACTUALLY EXECUTED and its plan is invalidated rather than left pointing at a line that never happened.
