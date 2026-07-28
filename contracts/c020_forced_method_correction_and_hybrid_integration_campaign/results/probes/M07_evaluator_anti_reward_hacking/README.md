# M07 — Evaluator anti-reward-hacking

The c019 failure — overriding a productive baseline play with END TURN — is reproduced as a fixture where the end-turn action holds 90% of root visits and a 0.9 Q, and the gate retains the baseline with reason `unproductive_end_turn_veto`. The c019 rule (highest visits wins) would have played it.

Measured on real games, the veto is worth little: 0.3312 with it against 0.3312 without. The damage is done by overriding at all, not by which override is chosen — see M09.
