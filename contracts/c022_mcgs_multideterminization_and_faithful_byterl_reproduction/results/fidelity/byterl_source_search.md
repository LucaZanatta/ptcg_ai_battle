# ByteRL source search — re-verified for c022, still NEGATIVE

`references/SOURCE_REFERENCES.md`: "Search author/organization channels for newly released code
before implementation. Record negative results and retrieval dates."

c021 searched on 2026-07-28 and found nothing. That result is not inherited: a release in the
intervening two days would change ByteRL's authority level from "paper fidelity" to "source
fidelity", which is the single largest asymmetry in this contract. The search was repeated.

**Searched 2026-07-30.**

## Result

| target | result | note |
|---|---|---|
| `github.com/bytedance/byterl` | **HTTP 404** | |
| `github.com/bytedance/LOCM` | **HTTP 404** | |
| `github.com/zhangyongxin121/COG2023` | HTTP 200, **repository is empty** | by an author of the Hearthstone paper; GitHub reports "This repository is empty" — no source, and not even the presentation material c021 recorded it as holding |
| `arxiv.org/abs/2303.04096` (LOCM ByteRL) | no code link | |
| `arxiv.org/abs/2303.05197` (Hearthstone improvements) | no code link | |
| web search for a ByteRL implementation | no author repository | the LOCM-related repositories that surface (`CodinGame/LegendsOfCodeAndMagic`, `ronaldosvieira/gym-locm`, `peter1591/hearthstone-ai`, `dillondaudert/Hearthstone-AI`) are the game framework and OTHER agents, not ByteRL |

## One thing c021 did not have: a newer paper about ByteRL

`arXiv:2404.16689`, *Learning to Beat ByteRL: Exploitability of Collectible Card Game Agents*,
post-dates c021's search and is specifically about ByteRL. It was checked in case it disclosed
implementation details that would raise ByteRL's authority level.

**It does not.** It gives no architecture, no LSTM size, no V-trace/UPGO/OSFP details, no
importance-clipping bounds, no PPO clipping parameter, and links to no ByteRL source. Its
substantive claim about the agent is behavioural:

> "Although ByteRL beat a top-10 Hearthstone player from China, we show that its play in Legends
> of Code and Magic is highly exploitable."

So it changes nothing about fidelity. It is worth recording for a different reason: **it is
independent evidence that a strong published ByteRL result coexists with exploitable play.**
That bears directly on how c022 should read its own ByteRL numbers — a rung that improves against
a fixed opponent panel has not thereby become unexploitable, and `DECISION_RULES §3` already
separates `BYTERL_FIXED_DECK=PASS` ("a statistically credible improvement over random
initialization/floor") from competitive strength. This paper is the reason that separation is
not merely bureaucratic.

## Consequence for this contract, unchanged from c021

Authority for ByteRL falls to `FIDELITY_RULES §1` level 2 and below: the LOCM paper, then the
Hearthstone improvements paper, then IMPALA where those two explicitly inherit from it.

Therefore:

- **`BYTERL_REFERENCE_FIDELITY` can only ever be PAPER fidelity, and is reported as such.**
  `references/LICENSE_AND_REUSE_POLICY.md` says it directly: "do not claim source-code identity
  when no complete source exists."
- Every detail the papers do not specify is an entry in `UNRESOLVED_REFERENCE_CHOICES.md` with
  alternatives and a sensitivity note — never a silent inheritance of a c021 value.

**This asymmetry between the two branches is structural and survives into the final report.**
MCGS has an audited official source archive: 33 files, SHA-256 `f00a54f3…`, extracted tree
verified byte-identical, 33 sites anchored to located fragments. ByteRL has two papers. No amount
of care on the ByteRL side closes that gap, and a report that presented the two branches as
equally grounded would be false.
