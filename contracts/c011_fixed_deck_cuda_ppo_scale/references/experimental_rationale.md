# Experimental Rationale

c010 produced the first multi-seed evidence that PPO can improve and extend a
fixed-deck neural agent. Its strongest confirmed policy reached roughly 28.25%
against the frozen teacher and 33.17% across the three-opponent strategic field.

c011 does not change the deck or invent a new RL algorithm. It addresses the
highest-leverage engineering and evidence gaps:

1. confirm c010 checkpoints that were saved but not fully evaluated;
2. evaluate the frozen teacher on the same strategic panel;
3. port the validated custom PPO mathematics to PyTorch/CUDA;
4. preserve full trainer state for literal future continuation;
5. use the RTX 5070 only when parity and end-to-end throughput justify it;
6. scale the same stabilized recipe across three independent seeds.

The Python source bundle is mandatory so the entire implementation can be
reviewed and debugged outside the execution environment without relying on a
partial source snapshot.
