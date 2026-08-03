# SOURCES — external evidence used by c023

Every external artifact this campaign touched, what was taken from it, and what may legally be
done with it. The reuse vocabulary is c005's and c016's, deliberately: inventing a new one would
let this contract quietly grant itself permissions two earlier audits refused.

## Retrieval environment

| fact | value |
|---|---|
| Kaggle CLI | `.venv/bin/kaggle`, authenticated via `~/.kaggle/access_token` |
| competition | `pokemon-tcg-ai-battle` — The Pokémon Company, PTCG AI Battle Challenge Simulation |
| competition deadline | 2026-08-16 23:59 UTC (well after this contract's 2026-08-05 20:00 deadline) |
| retrieval date | 2026-08-03, 18:2x–18:3x Europe/Rome |
| internet access | available; Kaggle API reachable and authenticated |

## Leaderboard and ladder mechanics

| source | retrieved | evidence extracted |
|---|---|---|
| `kaggle competitions leaderboard pokemon-tcg-ai-battle` | 2026-08-03 18:24 | top team 1254.3; ranks 2–20 span 1189.1 → 1095.9 |
| `kaggle competitions submissions pokemon-tcg-ai-battle` | 2026-08-03 18:24 | our four scored submissions: dragapult sample **719.7**, mega_lucario sample **593.3**, c014 archaludon 471.4, c015 anti-meta 390.7 |
| `keidroid/ptcg-ai-battle-rating-and-matchmaking-analysis` | 2026-08-03 18:26 | 6,113 teams; mean 622.8, median 637.8, max 1262.2; P75 755.2, P90 836.1, P95 903.8, P99 1035.6. A ~1155 rating corresponds to a measured 61.2% win rate over 260 public games, so the ladder is rating-matched: a strong agent's win rate against *its own band* stays near 60%, and rating — not win rate — is the quantity that separates. |

**Consequence for this campaign.** Our best submission (719.7) sits near the 65th percentile;
the frozen champion sits near the 40th. The four official sample agents are *not* the field. Any
local panel built only from them measures a different function from the ladder, so this contract
adds public community agents to the panel as opponents — see the reuse rules below for why they
enter as opponents and not as bases.

## Public kernels retrieved

Pulled with `kaggle kernels pull <ref> -p <dir> -m` (anonymous-capable, public kernels).
Runnable `main.py`/`deck.csv` pairs were recovered **without executing kernel code** —
`tools/c023_extract_kernels.py` reads each agent out as data (string literal, `%%writefile`
cell, base64 payload, or embedded tar member).

| kernel | votes | archetype | deck sha256 (12) | extraction |
|---|---:|---|---|---|
| `tetsutani/grimmsnarl-ex-damage-transfer-control` | 46 | Grimmsnarl ex damage-transfer control | `92b92bac9f91` | embedded tar asset (a ~150-module "council" package with a gzipped policy ensemble) |
| `jazivxt/codex-sol-eclipse-alakazam` | 38 | Alakazam ex | `8eccc69c3bf7` | `MAIN_SOURCE` / `DECK_SOURCE` literals |
| `jazivxt/a-better-hand-alakazam-rising-tide-v21` | 38 | Alakazam ex | `8eccc69c3bf7` | `%%writefile main.py` cell |
| `prvsiyan/ptcg-ai-battle-search-audited-alakazam-v12` | 11 | **Mega Lucario ex** (despite the title) | `2a541d7bf3d9` | base64 `PAYLOADS` dict |
| `raunakdey07/pok-mon-tcg-advanced-heuristic-agent` | 14 | Alakazam ex | `8eccc69c3bf7` | `%%writefile main.py` cell |
| `keidroid/ptcg-ai-battle-rating-and-matchmaking-analysis` | 9 | — (analysis) | — | read only; no agent |
| `kirvk013/ptcg-22-decks-one-meta` | 3 | — (deck census) | — | read only |
| `busyaprime/test-your-agent-a-local-matchup-harness` | 3 | — (harness) | — | read only; not used |

## Reuse classification

**The Kaggle API exposes no licence field for kernels.** Re-verified this run: `kernels_pull`
with `metadata=True` returns `licenseName: null` for all five agent kernels. c016 recorded the
same finding and its §12 forbids inferring permission from visibility. Nothing here overrides
that.

| source | class | may execute locally | may package | may submit |
|---|---|---|---|---|
| `official_dragapult` / `official_mega_lucario` / `official_mega_abomasnow` / `official_iono` | **SUBMISSION_REUSE_ALLOWED** | yes | yes | yes |
| all five public community kernels | **LOCAL_BENCHMARK_ONLY** | yes | **no** | **no** |
| public **deck lists** (card-ID lists) | **CONFIGURATION_NOT_CODE** | yes | yes | yes |

*Basis for `SUBMISSION_REUSE_ALLOWED`*: these are the competition's own sample agents, and c005
packaged one and Kaggle accepted and scored it (ref `54948560`, 719.7, COMPLETE). That is an
observed outcome of this competition, not a reading of a licence.

*Basis for `LOCAL_BENCHMARK_ONLY`*: no licence is exposed, no acceptance precedent exists for
community code, and absence of a licence is not permission.

*Basis for `CONFIGURATION_NOT_CODE`*: a list of 60 card IDs is a game configuration, not authored
software; c014 already used a community deck list on this basis and c016 §12 restated it.

**Operative consequence, stated before any candidate was built:** every c023 submission candidate
is built on an official sample agent plus this contract's own code. No community source is
copied, adapted, translated, or packaged. Community agents appear in this campaign **only** as
locally-executed opponents, which is what makes the panel meta-representative.

## Attribution carried by any package

- official sample agents: Kiyota, Kaggle kernels `kiyotah/a-sample-rule-based-agent-*`
- deck lists sourced from the community meta: recorded per-deck in `DECK_CHANGE_LEDGER.md`

## Retrieval limitations (recorded, not worked around)

- The competition **rules page is a client-rendered SPA**; an unauthenticated fetch returns a
  shell with no machine-extractable text. c005 recorded this and it has not changed. The
  per-decision timeout and submission-size limits therefore remain **UNVERIFIED**, and this
  contract enforces its own conservative latency bound and states it as self-imposed.
- Kernel licences are not exposed by the API (above).
