# NEXT_STEP (AC-16)

**REDESIGN_FIXED_DECK_AGENT**

CURRICULUM_RESULT TIED; SELF_PLAY_LOOP NOT_EXTENDED; CLAUDE_TEACHER_STATUS REJECTED.

**Highest-leverage blocker (one, measured):** PPO continuation has stopped adding value from this initialisation. Neither arm beat the frozen incumbent on teacher score at 500 games (incumbent 0.380; best P0 0.325, best P1 0.345), while a zero-cost weight average of two c011 seeds gained +0.11 teacher over c011's best single policy. The binding constraint is the optimiser's inability to exceed a point that parameter averaging reaches for free -- not opponent curriculum, not compute.

**Hypotheses (labelled, untested here):** that weight-space averaging over more diverse seeds keeps paying; that the escalating elite schedule would behave differently from the fixed 15% actually run.
