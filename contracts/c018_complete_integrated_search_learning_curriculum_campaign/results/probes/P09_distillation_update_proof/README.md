# P09 — Distillation update proof

An optimiser either stepped or it did not, and the only trustworthy witness is the weights.

7,080 optimiser steps on **cuda** over 60 epochs. The
step counter is not taken on faith: summing the per-epoch batch counts recorded during training
gives 7,080, which matches. Every epoch produced a *different* checkpoint
hash (60/60 distinct), hashed over tensor bytes in sorted
key order rather than over the file — c012 cached a per-path file hash and could not tell an
overwrite from a no-op.

Training policy loss moved 1.508158 → 0.310757, and
all losses stayed finite.

Trained on 42,857 trusted rows only, with
0 K_MAX-mislabeled rows excluded. c017's depth-0 labels are
not used (`uses_c017_labels: False`) and c017's checkpoint is not continued
(`continues_c017_checkpoint: False`) — a fresh initialisation is what
makes "the hash changed" mean *this* campaign moved *these* weights.

**Status: PASS.**
