# B01 — Dynamic option-mask correctness

495 live decisions checked: unavailable options carry exactly zero probability (mask multiplied after softmax, not a small epsilon), legal options sum to one, and every sampled index maps back to the correct canonical option. Zero violations.

**Status: PASS.**
