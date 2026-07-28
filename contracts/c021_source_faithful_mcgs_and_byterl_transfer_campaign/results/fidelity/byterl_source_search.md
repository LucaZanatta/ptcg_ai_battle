# ByteRL source search — conclusion: NO author-released implementation found

`MANDATORY_IMPLEMENTATION B1` requires searching for a complete ByteRL implementation and
recording the search **even when negative**, and forbids claiming source fidelity when only paper
fidelity is available.

Searched 2026-07-28, ~20:45–20:55 UTC.

| target | result |
|---|---|
| `arxiv.org/abs/2303.04096` (LOCM ByteRL) | HTTP 200; abstract page contains no GitHub link and no "code available" statement |
| `arxiv.org/abs/2303.05197` (Hearthstone improvements) | HTTP 200; same — no code link |
| `github.com/bytedance/LOCM` | HTTP 404 |
| `github.com/bytedance/byterl` | HTTP 404 |
| `github.com/bytedance/Hearthstone-AI` | HTTP 404 |
| GitHub search `byterl` | 1 result, `Rpgbyter/Byterleek`, unrelated |
| GitHub search `LOCM optimistic smooth fictitious play` | 0 results |
| GitHub search `mastering strategy card game hearthstone` | 1 result, `zhangyongxin121/COG2023` |

`zhangyongxin121/COG2023` is by an author of the Hearthstone paper and is the closest hit. It is
**0 KB with no language and no file contents** — its own description states it holds "the
presentation video for our paper". It contains no implementation.

## Consequence for this campaign

Authority for ByteRL falls to level 2 of `CONTRACT §3`: the LOCM paper, then the Hearthstone
improvements paper, then COG material, then IMPALA where the ByteRL papers defer to it.

Therefore:

- **`SOURCE_FIDELITY` for ByteRL can only ever be paper-fidelity, and will be reported as such.**
  Claiming source fidelity would be false.
- Every detail the papers do not specify becomes an entry in
  `results/fidelity/UNRESOLVED_REFERENCE_CHOICES.md` with evidence, alternatives, the choice made,
  and a sensitivity test — never a silent inheritance of c020 behaviour, which
  `FIDELITY_RULES §6` and `references/C020_AUDIT_FINDINGS` both forbid.

This asymmetry between the two branches is structural and must survive into the final report: MCGS
has an audited official source archive; ByteRL does not, and no amount of care changes that.
