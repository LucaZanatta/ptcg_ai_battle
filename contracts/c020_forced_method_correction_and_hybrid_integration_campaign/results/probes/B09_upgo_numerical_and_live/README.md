# B09 — upgo numerical and live

Six hand-computed fixtures: single action, multi-select joint action, terminal sequence, truncated recurrent unroll, clipping bounds and the UPGO recursion. The lower-clip fixture originally used exp(-5) = 6.7e-3, which is ABOVE the 1e-3 floor and therefore never exercised the bound it claimed to test; the tests caught it and it now uses exp(-8).
