# M10 — Lifecycle and memory

0 release errors across the scaled run. Every `searchId` a tree opens is released in a `finally` block, so an exception mid-simulation still frees native state.

**Status: PASS.**
