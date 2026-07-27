# M08 — Chance outcome handling

A precondition probe run BEFORE the tree was written established that `search_step` returns deterministic successors for the actions tested, that one live root branches into distinct children, and that a child can be stepped further. That is what allows a node to own a live `searchId` instead of replaying from the root.

Every (node, action) still records its successor observation hashes — 651,547 recorded, 0 actions seen producing more than one outcome. A stochastic action therefore cannot silently overwrite an earlier outcome, which is the property M08 asks for, whether or not stochasticity appears.

**Status: PASS.**
