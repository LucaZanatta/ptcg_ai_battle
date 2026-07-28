# B05 — Autoregressive multi-select with joint probability

None multi-select decisions over None multi-select contexts. Every record stores the full ordered selection, the exact environment payload, per-pick probabilities and the joint log probability, and the joint equals the sum of the per-step log probabilities in every logged record.

c019 stored the first pick only (audit #9). The V-trace fixture shows the resulting targets are numerically different, so the c019 ratio was wrong wherever k > 1.
