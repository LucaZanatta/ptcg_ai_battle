# B13 — Package recurrent parity

The extracted ByteRL package plays 60/60 games on both seats with the repository off `sys.path`, and its own counters show 2930 of 2930 decisions produced by the learned policy with 0 fallbacks, and 60 recurrent-state resets — one per game.

The package contains no MCTS and no search API (§9.6).

**Status: PASS.**
