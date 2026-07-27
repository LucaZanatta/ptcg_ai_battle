# P02 — Shared observation legality

`VisibleObservation` exposes own hand, both boards, both discards and public counts. `opponent_hand_contents`, `deck_contents` and `prize_contents` exist solely to RAISE — a leak becomes a crash in a probe instead of a silent advantage. All three raised; zero leaked.

The ByteRL encoder reads state only through this guard (§7: the ByteRL branch must never receive hidden sampled state). The MCTS determinizer may *predict* hidden zones but never read them.

**Status: PASS.**
