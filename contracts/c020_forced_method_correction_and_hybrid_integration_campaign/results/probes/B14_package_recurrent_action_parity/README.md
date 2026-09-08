# B14 — Package recurrent/action parity

The SAME checkpoint is loaded in the repository and in the extracted package (repository source roots removed from `sys.path`), and both are driven through an identical fixed sequence. Compared at every step: legal logits, the autoregressive selected payload, the recurrent transition and the value output.

Result: **0** mismatches over 6 steps.

Playing legal games is not parity — a package can differ from the evaluated code and still complete every game, which is why `CONTRACT §8` lists submitted-differs-from-evaluated as its own blocker.
