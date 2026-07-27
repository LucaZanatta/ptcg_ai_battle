# M04 — PUCT numerical fixture

Selection scores match hand-calculated `Q + c_puct * P * sqrt(N_parent)/(1+N_child)` to 12 decimal places, and a registered sensitivity fixture shows `c_puct` **changing which child is selected**: at 0.01 the strong-Q child wins, at 10.0 the strong-prior child does.

That second test exists because c018 configured a `beam_width` that had no runtime effect. A constant that cannot change behaviour is not a parameter.

**Status: PASS.**
