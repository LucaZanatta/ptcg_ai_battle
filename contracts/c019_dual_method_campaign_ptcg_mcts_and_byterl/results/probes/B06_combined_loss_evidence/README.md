# B06 — Combined loss evidence

31728 optimizer updates, each logging policy-V-trace, UPGO, value and entropy losses SEPARATELY plus the gradient norm. 31728 updates carry a nonzero UPGO term.

Separate logging is what makes 'UPGO is implemented' checkable rather than assertable.

**Status: PASS.**
