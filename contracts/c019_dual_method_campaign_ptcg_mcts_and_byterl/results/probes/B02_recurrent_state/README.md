# B02 — Recurrent state

LSTM hidden size 256 (the registered source value), state carried across atomic decisions within a game and reset at the game boundary.

A real defect was found here: the checkpoint-driven opponent kept its state in a module-level dict keyed by model id, so a game began with the previous game's hidden state. Now reset explicitly at every game boundary.

**Status: PASS.**
