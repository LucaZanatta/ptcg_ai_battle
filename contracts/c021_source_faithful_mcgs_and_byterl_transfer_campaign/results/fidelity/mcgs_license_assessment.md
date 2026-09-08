# MCGS licence assessment

## Retrieved

| item | url | sha256 | bytes |
|---|---|---|---|
| source archive | https://hearthstoneai.github.io/files/bots/UserCreatedDeckPlaying2019/2019_UCDP_MCGS.zip | `f00a54f310a8f868deb59964c17e71357d67ecfcedba01c0245053dcc5aa920a` | 64,230 |
| paper | https://ieee-cog.org/2020/papers2019/paper_257.pdf | `c994b91340c71fab289ea158af7ada22f451ed23c1e6b74a6eb69e96261ff73d` | 225,113 |

Retrieved 2026-07-28T20:39:02Z, HTTP 200, server `last-modified: Mon, 08 Feb 2021 09:09:28 GMT`.

## Licence finding

The archive contains **no LICENSE, COPYING, or per-file licence header**. It is a competition
submission published by the Hearthstone AI competition organisers as the 2019 User-Created Deck
Playing track winner. It builds on `SabberStoneCore` (the competition's C# engine), which is
itself AGPL-3.0.

**No explicit grant of redistribution is present.** Under
`references/LICENSE_AND_REUSE_POLICY.md`, unclear-permission code may be studied and used as a
local reference but must not be included in a submission archive.

## Posture adopted

1. The archive and paper are stored under `external_refs/c021_mcgs/`, **outside** the contract
   results tree and outside every competition package.
2. **No C# source is copied, translated line-by-line, or vendored.** The PTCG port is written from
   the algorithm's transcribed formulas and control flow, recorded in
   `mcgs_paper_equation_map.md`, in the same way `FIDELITY_RULES` requires the reference to
   preserve behaviour rather than text.
3. Source-level fidelity here means **behavioural and formula fidelity to the audited original**,
   verified by fixtures that compute the source's formulas independently — not textual derivation.
4. Every c021 package will carry an ATTRIBUTION statement naming this archive as the algorithmic
   reference, its SHA-256, and the fact that no code from it is included.
5. If the competition's rules or a later licence grant permit redistribution, that changes nothing
   here: the port is already clean-room by construction.

## Tension worth stating plainly

`CONTRACT §3` sets the official source archive as authority 1, and `MANDATORY_IMPLEMENTATION A1`
requires a file-by-file and formula-by-formula audit before porting — both of which have been
done. The licence prevents *vendoring*, not *reading*. The resulting port is therefore maximally
faithful in behaviour while containing none of the original text, and the equation map is the
artifact that makes that claim auditable.
