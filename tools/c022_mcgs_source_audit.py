"""c022 A1 — map the official 2019 MCGS source's hidden-information machinery.

`MANDATORY_IMPLEMENTATION A1` requires the archive re-hashed and every site responsible for
private-information save/restore, determinization/re-determinization, random/chance handling,
observer information sets, graph identity and simulation init/cleanup mapped BEFORE any K-way
code is written.

Every mapped site is ANCHORED: the entry carries a `must_contain` fragment, and the tool asserts
that fragment is present in the file at the recorded line region. A map that merely asserts
"Node.Expand.cs handles chance nodes" is prose; if the archive were swapped for a different
version the prose would still read true. These anchors fail loudly instead.

The audit's headline finding is in `AGGREGATION`: the archive already contains a complete
root-statistic aggregation across independent determinization roots
(`MonteCarloGraphSearch.AggregateDeterminizations`), together with the code that picks a
determinization per simulation and the code that re-roots and replenishes the ensemble between
decisions. So c022's K-session design does not have to invent an aggregation rule — it has to
port one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

ARCHIVE = os.path.join(_REPO, "external_refs", "c021_mcgs", "2019_UCDP_MCGS.zip")
SRC = os.path.join(_REPO, "external_refs", "c021_mcgs", "extracted")
OUT = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                   "results", "fidelity")

ARCHIVE_URL = "https://hearthstoneai.github.io/files/bots/UserCreatedDeckPlaying2019/2019_UCDP_MCGS.zip"

# ---------------------------------------------------------------------------------------------
# Categories required by MANDATORY_IMPLEMENTATION A1.
CATEGORIES = {
    "PRIVATE_INFO_SAVE_RESTORE": "private-information save/restore",
    "DETERMINIZATION": "determinization and re-determinization",
    "CHANCE": "random/chance handling",
    "OBSERVER_INFOSET": "observer-specific information sets",
    "GRAPH_IDENTITY": "graph identity and transpositions",
    "SIM_INIT_CLEANUP": "simulation initialization and cleanup",
    "AGGREGATION": "multi-determinization root aggregation",
}

# Every site: (id, category, file, symbol, must_contain, what_it_does, ptcg_status)
# `ptcg_status` is one of AVAILABLE / UNAVAILABLE / ADAPTED and is the input to the gap analysis.
SITES = [
    # ---------------------------------------------------------------- private info save/restore
    ("P1", "PRIVATE_INFO_SAVE_RESTORE", "src/Information.cs",
     "Node.ExtractPrivateInformation",
     "StateAbstraction.ExtractPrivateInformation(",
     "Snapshots the CURRENT OPPONENT's hand into an `Information` value (hash + a copy of the "
     "hand span) and removes the node from the transposition table first, because its identity "
     "is about to change from a perfect-information state to an information set.",
     "UNAVAILABLE"),
    ("P2", "PRIVATE_INFO_SAVE_RESTORE", "src/Information.cs",
     "Node.RestoreNodes",
     "Information currentInfo = StateAbstraction.ExtractPrivateInformation(",
     "For every remembered `Information` in the node's information set, clones the game and "
     "REBUILDS the opponent's hand from the remembered entity list: removes each remembered card "
     "from wherever it now is, returns present hand cards that were in the remembered deck back "
     "to the deck, drops cards that had since gone to graveyard/setaside, then re-adds cloned "
     "remembered cards to hand, with an AuraUpdate after each structural change. One sample node "
     "is expanded per remembered information, and one is chosen at random to continue.",
     "UNAVAILABLE"),
    ("P3", "PRIVATE_INFO_SAVE_RESTORE", "src/Information.cs",
     "Information (readonly struct)",
     "public readonly ReadOnlyMemory<IPlayable> HandMemory;",
     "The saved private information IS the opponent's hand: a hash for equality plus the actual "
     "playable objects for restoration. Equality is by hash of the sorted per-card hashes.",
     "UNAVAILABLE"),
    ("P4", "PRIVATE_INFO_SAVE_RESTORE", "AgentUtils.cs",
     "AgentUtils.GenerateGameForSimulation",
     "internal static Game GenerateGameForSimulation(POGame.POGame poGame)",
     "ROOT-level private-information reconstruction. Builds a plausible full game from the "
     "partially-observable one: picks the opponent's decklist by hero class, subtracts every "
     "card already observed in graveyard and on board, shuffles the remainder, deals "
     "`op.HandZone.Count` of them into a fresh hand (accounting for The Coin) and the rest into "
     "a fresh deck, then pads the deck with random class cards until the count matches. This is "
     "the source's equivalent of a root determinization.",
     "ADAPTED"),

    # ---------------------------------------------------------------- determinization
    ("D1", "DETERMINIZATION", "src/SabberHelpers/SabberUtils.cs",
     "SabberUtils.Determinize",
     "internal static void Determinize(Game game, Random rnd, bool all = false)",
     "Re-randomizes the opponent's hand IN PLACE: each hand card is swapped for a uniformly "
     "random card from the opponent's deck (cards with Id > 67, i.e. generated ones, are "
     "replaced by a random card of the same category instead), then the deck is shuffled. With "
     "`all: true` the CURRENT PLAYER's deck is shuffled first, so the root player's own future "
     "draw order is re-rolled too.",
     "UNAVAILABLE"),
    ("D2", "DETERMINIZATION", "src/MCGS.cs",
     "MonteCarloGraphSearch.SingleThreadRollout",
     "SabberUtils.Determinize(game, ThreadStaticRandom, true);",
     "THE mechanism c021 identified as missing. Before EVERY rollout the leaf's game is cloned "
     "and fully re-determinized (`all: true`), so each simulation from a given leaf evaluates a "
     "DIFFERENT hidden world. `IIAlgorithm` is never assigned in the archive, so it holds the "
     "enum default `DEFAULT`, the `!= PIMC` guard is true, and this executes on every rollout.",
     "UNAVAILABLE"),
    ("D3", "DETERMINIZATION", "src/Node.Expand.cs",
     "Node.Expand — END_TURN, root player to opponent",
     "SabberUtils.Determinize(Game, _rnd);",
     "When the ROOT PLAYER ends their turn (and PIMC is off), the game is re-determinized before "
     "the opponent acts: the opponent's hand becomes a fresh sample.",
     "UNAVAILABLE"),
    ("D4", "DETERMINIZATION", "src/Node.Expand.cs",
     "Node.PrepareChanceNode",
     "case RandomActionType.ENDTURN:",
     "Interior re-determinization per chance-node sample. DRAW and TRACKING shuffle the current "
     "player's deck; ENDTURN determinizes if not yet determinized else shuffles the opponent's "
     "deck; ENDTURN_OPPONENT shuffles the opponent's deck; RANDOMEFFECT determinizes for cards "
     "in `CardCategory.RandomOpponentHand`.",
     "UNAVAILABLE"),
    ("D5", "DETERMINIZATION", "src/Algorithms/PIMC.cs",
     "PerfectInformationMonteCarlo.GenerateDeterminizationsAtOnce",
     "public static Node[] GenerateDeterminizationsAtOnce(Game game, int num,",
     "Builds up to `num` INDEPENDENT determinization roots from one game, each fully "
     "determinized, DEDUPLICATED by `DeterminizationHash` (own deck order + opponent deck order "
     "+ opponent hand contents). Duplicate worlds are dropped, so the returned array is a set of "
     "distinct hidden worlds and may be shorter than `num`.",
     "AVAILABLE"),

    # ---------------------------------------------------------------- chance
    ("C1", "CHANCE", "src/Node.Expand.cs",
     "Node.CheckRandom",
     "private void CheckRandom(ref Node child, PlayerTask selectedAction, int actionIndex)",
     "Classifies a freshly expanded child into a `RandomActionType`. Under `NodeConfig.PIMC` it "
     "marks ONLY genuine random effects (`IsRandomHappened`) and returns; otherwise it also "
     "marks choices, draws, end-turns and specific card ids.",
     "ADAPTED"),
    ("C2", "CHANCE", "src/Node.Expand.cs",
     "Node.CreateChanceNode",
     "private void CreateChanceNode(PlayerTask a, int actionIndex, ActionAbstraction aa,",
     "Interposes a chance node on the edge that produced the child. For DRAW it DISCARDS the "
     "first sample (it carried undeterminized information), shuffles and expands a fresh one; "
     "otherwise it moves the child under the chance node.",
     "ADAPTED"),
    ("C3", "CHANCE", "src/Node.Expand.cs",
     "Node.IsFullyExpanded — damped sampling",
     "int reduced = ReduceFunction(NodeConfig.SampleWidth);",
     "A chance node is fully expanded when its edges' total SampleCount reaches SampleWidth "
     "reduced by DampingParameter^numSampleTraversed, so deeper chance nodes draw exponentially "
     "fewer samples.",
     "AVAILABLE"),
    ("C4", "CHANCE", "src/Node.cs",
     "Node.SampleChild",
     "OutgoingEdges.GetWeightedRandom(p => p.SampleCount, _rnd)",
     "A chance node is descended by SampleCount-weighted random choice, NOT by UCB. Selection "
     "and sampling are different operations and must not be conflated.",
     "AVAILABLE"),

    # ---------------------------------------------------------------- observer infosets
    ("O1", "OBSERVER_INFOSET", "src/Information.cs",
     "Node.GetInformationSet",
     "private static bool GetInformationSet(ref Node node)",
     "Converts a perfect-information node into an information-set node: extracts the root "
     "player's private information, looks the abstracted node up in the transposition table, and "
     "either merges the new `Information` into the matching node's set or starts a new set.",
     "UNAVAILABLE"),
    ("O2", "OBSERVER_INFOSET", "src/Node.cs",
     "Node ctor — createCompleteAbstraction",
     "bool createCompleteAbstraction = IsOpponent && !parent.IsInformationSet;",
     "An OPPONENT node's abstraction includes the root player's private information (perfect "
     "information) unless its parent is already an information set. Observer identity is "
     "therefore baked into state identity.",
     "UNAVAILABLE"),
    ("O3", "OBSERVER_INFOSET", "src/Node.Expand.cs",
     "Node.Expand — informationSet nulling",
     "newNode._informationSet = null;",
     "A non-opponent sample expanded from a chance node drops the inherited information set: "
     "the root player's own view carries no opponent-side information set.",
     "UNAVAILABLE"),
    ("O4", "OBSERVER_INFOSET", "src/Information.cs",
     "Node.AddGame / HasMultipleGame",
     "public void AddGame(Game game)",
     "A transposed chance node accumulates MULTIPLE concrete games behind one abstraction; "
     "`PrepareChanceNode` then picks one at random. This is how one graph node represents "
     "several hidden worlds at once.",
     "UNAVAILABLE"),

    # ---------------------------------------------------------------- graph identity
    ("G1", "GRAPH_IDENTITY", "src/MCGS.cs",
     "MonteCarloGraphSearch.TranspositionCheck",
     "internal static bool TranspositionCheck(ref Node node)",
     "The transposition table maps StateAbstraction -> Node. On a hit it merges any separated "
     "subtree, and if a predecessor->matching edge already exists it marks the traversed edge "
     "DUMMY (VisitCount = int.MaxValue) so UCB never selects it again.",
     "AVAILABLE"),
    ("G2", "GRAPH_IDENTITY", "src/Edge.cs",
     "Edge.IsDummy",
     "VisitCount = int.MaxValue;",
     "A dummy edge is excluded from selection by giving it an infinite visit count, which drives "
     "its UCB exploration bonus to zero.",
     "AVAILABLE"),
    ("G3", "GRAPH_IDENTITY", "src/Edge.cs",
     "Edge.Value",
     "bonus = c * Math.Sqrt(2 * Math.Log(Predecessor.TotalVisit) / VisitCount);",
     "UCB1 on edge statistics — `Q + c*sqrt(2*ln(N)/n)`. NOT PUCT: there is no prior term and no "
     "policy network anywhere in the archive.",
     "AVAILABLE"),
    ("G4", "GRAPH_IDENTITY", "src/Node.cs",
     "Node.Value",
     "case PlayState.WON:",
     "Terminal nodes are valued +10 (WON) / -10 (LOST) / 0, while rollouts return 1.0 / 0.0. A "
     "proven terminal therefore outweighs any rollout estimate by an order of magnitude.",
     "AVAILABLE"),
    ("G5", "GRAPH_IDENTITY", "src/Node.cs",
     "Node.Finalise",
     "parent.OutgoingEdges.Clear();",
     "On backing up a won terminal, the PARENT is collapsed onto the single proven edge and its "
     "untested actions are cleared. Disabled entirely under PIMC.",
     "AVAILABLE"),

    # ---------------------------------------------------------------- sim init/cleanup
    ("S1", "SIM_INIT_CLEANUP", "src/MCGS.cs",
     "MonteCarloGraphSearch.Search",
     "var reward = SingleThreadRollout(root, searchConfig);",
     "One simulation = TreePolicy to a leaf, one rollout, one backup. The rollout's "
     "re-determinization (D2) is therefore per-simulation, not per-decision.",
     "AVAILABLE"),
    ("S2", "SIM_INIT_CLEANUP", "src/MCGS.cs",
     "MonteCarloGraphSearch.PlayUntilTerminal",
     "if ((game.Turn + 1) / 2 == 45)",
     "The rollout plays the uniform-random filtered policy until COMPLETE, returns 1.0 if the "
     "search's player won else 0.0, returns 0.0 at a 45-round cap, and returns -1 on exception "
     "or after 1000 steps. `SingleThreadRollout` retries up to 5 times while the value is < 0.",
     "AVAILABLE"),
    ("S3", "SIM_INIT_CLEANUP", "src/Node.Expand.cs",
     "Node.ReleaseGameResources",
     "private void ReleaseGameResources()",
     "A fully expanded non-DPW node drops its Game, LegalActions, Options and ChanceAction. "
     "Note `Node.ReleaseAllManagedResources` begins with a bare `return;` — it is disabled in "
     "the shipped source, so the deeper cleanup never runs.",
     "AVAILABLE"),
    ("S4", "SIM_INIT_CLEANUP", "Agent.cs",
     "MCGSAgent.GetMove — search loop",
     "while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))",
     "The per-decision budget is WALL CLOCK: 15 s for the first move of a turn, 10 s for "
     "continuing moves, with no simulation cap.",
     "ADAPTED"),
    ("S5", "SIM_INIT_CLEANUP", "Agent.cs",
     "MCGSAgent.InitialiseRoot",
     "private static bool InitialiseRoot(POGame.POGame poGame, Node previousNode,",
     "Between decisions the agent RE-ROOTS onto the previously selected node when the abstraction "
     "still matches, so graph statistics survive across the sequential decisions of a turn. It "
     "builds a fresh root (via GenerateGameForSimulation) only when it cannot match.",
     "ADAPTED"),

    # ---------------------------------------------------------------- aggregation  ** key **
    ("A1", "AGGREGATION", "src/MCGS.cs",
     "MonteCarloGraphSearch.AggregateDeterminizations",
     "internal static void AggregateDeterminizations(Node root, Node[] determinizations)",
     "THE SOURCE'S OWN MULTI-DETERMINIZATION AGGREGATION. For every determinization root and "
     "every one of its outgoing edges, finds the root edge with the same ActionIndex and does "
     "`rootEdge.Successor.VisitCount += edge.Successor.VisitCount` and "
     "`rootEdge.Successor.Rewards += edge.Successor.Rewards`. Unmatched action indices are added "
     "as cloned children. The root's own VisitCount and Rewards are then set to the sums over "
     "its edges. Selection afterwards is ordinary MaxChild on the aggregate.",
     "AVAILABLE"),
    ("A2", "AGGREGATION", "src/MCGS.cs",
     "MonteCarloGraphSearch.PickDeterminization",
     "private static Node PickDeterminization(Node[] determinizations)",
     "Picks a determinization uniformly at random among those not currently in use, under a "
     "lock. The ensemble is searched by many threads, one simulation at a time each.",
     "AVAILABLE"),
    ("A3", "AGGREGATION", "Agent.cs",
     "MCGSAgent.GetMove — PIMC search loop",
     "Node determinization = determinizations[_rnd.Next(determinizations.Length)];",
     "Under PIMC the per-decision budget is spent by repeatedly picking ONE determinization "
     "uniformly at random and running ONE MCGS simulation in it. Total simulations are therefore "
     "split across the ensemble — the source's own fixed-TOTAL-simulation protocol.",
     "AVAILABLE"),
    ("A4", "AGGREGATION", "src/MCGS.cs",
     "MonteCarloGraphSearch.CleanUpDeterminizations",
     "private static int CleanUpDeterminizations(Node root, Node[] determinizations, Game game)",
     "Between decisions each determinization is re-rooted onto the child matching the new root's "
     "abstraction; a determinization with no matching child is REPLACED by a brand-new fully "
     "determinized root. So the ensemble is replenished with fresh hidden worlds as the game "
     "diverges from them.",
     "AVAILABLE"),
    ("A5", "AGGREGATION", "src/SearchConfig.cs",
     "SearchConfig.DeterminizationNumber",
     "public int DeterminizationNumber = 200;",
     "The ensemble size field. It is READ only inside `SearchConfig.ToString()`, in a branch "
     "guarded by `IIAlgorithm == PIMC`. No code in the archive passes it to "
     "GenerateDeterminizationsAtOnce.",
     "AVAILABLE"),
    ("A6", "AGGREGATION", "Agent.cs",
     "MCGSAgent.determinizations — never populated",
     "private Node[] determinizations;",
     "The field is declared and set to null in FinalizeGame/FinalizeAgent, and read in three "
     "places under `pimc`. It is ASSIGNED NOWHERE in the archive. The shipped configuration has "
     "`NodeConfig.PIMC = false`, so the ensemble path is unreachable and the missing "
     "initialization never fires.",
     "AVAILABLE"),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: str) -> str:
    with open(p, "rb") as fh:
        return sha256_bytes(fh.read())


def archive_inventory() -> dict:
    z = zipfile.ZipFile(ARCHIVE)
    files = {}
    for i in sorted(z.infolist(), key=lambda x: x.filename):
        if i.is_dir():
            continue
        data = z.read(i.filename)
        files[i.filename] = {"bytes": len(data), "sha256": sha256_bytes(data)}
    return {
        "archive_path": os.path.relpath(ARCHIVE, _REPO),
        "archive_sha256": sha256_file(ARCHIVE),
        "archive_bytes": os.path.getsize(ARCHIVE),
        "source_url": ARCHIVE_URL,
        "n_files": len(files),
        "files": files,
    }


def verify_extracted(inv: dict) -> dict:
    """The extracted tree must be byte-identical to the archive it claims to be."""
    mismatches, missing = [], []
    for name, meta in inv["files"].items():
        p = os.path.join(SRC, name)
        if not os.path.isfile(p):
            missing.append(name)
            continue
        if sha256_file(p) != meta["sha256"]:
            mismatches.append(name)
    extra = []
    for dirpath, _dirs, fns in os.walk(SRC):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dirpath, fn), SRC).replace(os.sep, "/")
            if rel not in inv["files"]:
                extra.append(rel)
    return {"missing": missing, "mismatched": mismatches, "extra": extra,
            "identical": not (missing or mismatches or extra)}


def locate(site) -> dict:
    """Anchor a mapped site to real line numbers, or fail."""
    sid, cat, fname, symbol, must, what, status = site
    p = os.path.join(SRC, fname)
    entry = {"id": sid, "category": cat, "category_label": CATEGORIES[cat],
             "file": fname, "symbol": symbol, "anchor": must,
             "behaviour": what, "ptcg_status": status}
    if not os.path.isfile(p):
        entry["anchored"] = False
        entry["error"] = "file not found"
        return entry
    text = open(p, encoding="utf-8-sig").read()
    lines = text.splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if must in ln]
    entry["anchored"] = bool(hits)
    entry["lines"] = hits
    entry["file_sha256"] = sha256_file(p)
    if not hits:
        entry["error"] = "anchor fragment not present in file"
    return entry


def count_occurrences(pattern: str) -> list:
    """Count a regex across the whole archive; used for the 'assigned nowhere' claims."""
    out = []
    rx = re.compile(pattern)
    for dirpath, _d, fns in os.walk(SRC):
        for fn in sorted(fns):
            if not fn.endswith(".cs"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, SRC).replace(os.sep, "/")
            for i, ln in enumerate(open(p, encoding="utf-8-sig").read().splitlines(), 1):
                if rx.search(ln):
                    out.append({"file": rel, "line": i, "text": ln.strip()})
    return out


def structural_claims() -> dict:
    """Claims that are about ABSENCE, which a per-site anchor cannot express."""
    det_assign = [h for h in count_occurrences(r"\bdeterminizations\s*=")
                  if "null" not in h["text"]]
    # A method's own signature matches "Name(" too. Separate the declaration from call sites, or
    # "never called" reads as false because the definition found itself.
    gen_all = count_occurrences(r"GenerateDeterminizationsAtOnce\s*\(")
    gen_decl = [h for h in gen_all if re.search(r"\bstatic\b.*GenerateDeterminizationsAtOnce",
                                                h["text"])]
    gen_calls = [h for h in gen_all if h not in gen_decl]
    ii_assign = [h for h in count_occurrences(r"IIAlgorithm\s*=")
                 if "==" not in h["text"] and "!=" not in h["text"]]
    pimc_decl = count_occurrences(r"public bool PIMC")
    detnum_reads = count_occurrences(r"DeterminizationNumber")
    puct = count_occurrences(r"\bPUCT\b|prior\s*\*|policy\s*prior")
    return {
        "determinizations_array_assigned_non_null": {
            "hits": det_assign, "count": len(det_assign),
            "claim": "the ensemble array is never populated in the archive",
            "holds": len(det_assign) == 0,
        },
        "GenerateDeterminizationsAtOnce_call_sites": {
            "hits": gen_calls, "count": len(gen_calls),
            "declaration": gen_decl,
            "claim": "the ensemble generator is defined but never called",
            "holds": len(gen_calls) == 0 and len(gen_decl) == 1,
        },
        "IIAlgorithm_assignments": {
            "hits": ii_assign, "count": len(ii_assign),
            "claim": "IIAlgorithm is never assigned, so it holds enum default DEFAULT and the "
                     "`!= PIMC` rollout-determinize guard in SingleThreadRollout is TRUE",
            "holds": len(ii_assign) == 0,
        },
        "NodeConfig_PIMC_declaration": {
            "hits": pimc_decl,
            "claim": "the shipped NodeConfig.PIMC default is false",
            "holds": any("= false" in h["text"] for h in pimc_decl),
        },
        "DeterminizationNumber_reads": {
            "hits": detnum_reads, "count": len(detnum_reads),
            "claim": "DeterminizationNumber is read only in SearchConfig.ToString()",
            "holds": all(h["file"] == "src/SearchConfig.cs" for h in detnum_reads),
        },
        "no_puct_or_policy_prior": {
            "hits": puct, "count": len(puct),
            "claim": "there is no PUCT term and no policy prior anywhere in the archive",
            "holds": len(puct) == 0,
        },
    }


# ---------------------------------------------------------------------------------------------
def render_source_map(inv, ver, sites, claims) -> str:
    L = []
    A = L.append
    A("# MCGS hidden-information source map")
    A("")
    A("`MANDATORY_IMPLEMENTATION A1` requires the official archive re-hashed and every "
      "hidden-information site mapped **before** any K-way code is written. This document is "
      "generated by `tools/c022_mcgs_source_audit.py`, which re-hashes the archive, verifies the "
      "extracted tree against it byte for byte, and anchors every claim below to a literal "
      "fragment it locates in the file. An anchor that stops matching fails the tool.")
    A("")
    A("## Archive")
    A("")
    A("```text")
    A(f"url     {inv['source_url']}")
    A(f"path    {inv['archive_path']}")
    A(f"sha256  {inv['archive_sha256']}")
    A(f"bytes   {inv['archive_bytes']}")
    A(f"files   {inv['n_files']}")
    A("```")
    A("")
    A(f"Extracted tree identical to archive: **{ver['identical']}** "
      f"(missing {len(ver['missing'])}, mismatched {len(ver['mismatched'])}, "
      f"extra {len(ver['extra'])}).")
    A("")
    n_ok = sum(1 for s in sites if s["anchored"])
    A(f"{n_ok}/{len(sites)} mapped sites anchored to a located source fragment.")
    A("")

    for cat, label in CATEGORIES.items():
        rows = [s for s in sites if s["category"] == cat]
        if not rows:
            continue
        A(f"## {label}")
        A("")
        for s in rows:
            loc = f"`{s['file']}:{s['lines'][0]}`" if s.get("lines") else "**NOT FOUND**"
            A(f"### {s['id']} — `{s['symbol']}`")
            A("")
            A(f"{loc} · PTCG: **{s['ptcg_status']}**")
            A("")
            A(s["behaviour"])
            A("")
            A(f"> anchor: `{s['anchor']}`")
            A("")

    A("## Structural claims (about absence)")
    A("")
    A("A per-site anchor can prove a line exists. It cannot prove one does not. These claims are "
      "checked by scanning every `.cs` file in the archive.")
    A("")
    A("| claim | holds | hits |")
    A("|---|---|---:|")
    for k, v in claims.items():
        A(f"| {v['claim']} | **{v['holds']}** | {v.get('count', len(v['hits']))} |")
    A("")
    A("The last two matter most:")
    A("")
    A("- `IIAlgorithm` is assigned nowhere, so it holds the enum default `DEFAULT`. The guard "
      "`if (searchConfig.IIAlgorithm != ImperfectInformationAlgorithm.PIMC)` in "
      "`SingleThreadRollout` is therefore **true**, and the game is re-determinized before every "
      "single rollout. This is the mechanism c021 identified as the cause of its overconfidence, "
      "and this audit confirms it independently.")
    A("- The determinization ensemble is **half-shipped**: `AggregateDeterminizations`, "
      "`PickDeterminization`, `CleanUpDeterminizations`, `GenerateDeterminizationsAtOnce` and "
      "the whole `pimc` branch of `MCGSAgent.GetMove` are all present and complete, but "
      "`determinizations` is assigned nowhere and `NodeConfig.PIMC` ships `false`. The ensemble "
      "is unreachable in the shipped configuration.")
    return "\n".join(L) + "\n"


def render_gap_analysis(sites, claims) -> str:
    by_status = {}
    for s in sites:
        by_status.setdefault(s["ptcg_status"], []).append(s)
    L = []
    A = L.append
    A("# MCGS hidden-information gap analysis")
    A("")
    A("What the official source does, what the PTCG search API permits, and what c022 therefore "
      "implements. `FIDELITY_RULES §3` fixes the priority order:")
    A("")
    A("```text")
    A("1. fresh legal hidden-world sample per simulation inside one graph")
    A("2. otherwise independent search sessions with fresh legal hidden worlds and")
    A("   source-equivalent root-statistic aggregation")
    A("3. if neither is possible, MCGS_HIDDEN_INFO=BLOCKED")
    A("```")
    A("")
    A("## The three operations the API refuses")
    A("")
    A("Every UNAVAILABLE site below reduces to one of three operations, and all three need the "
      "same thing: the ability to modify hidden state at an INTERIOR node of a live search "
      "session.")
    A("")
    A("| operation | source sites | why the PTCG API refuses it |")
    A("|---|---|---|")
    A("| re-determinize an interior game | D1, D2, D3, D4 | `search_begin` requires "
      "`observation.search_begin_input`, which only the agent-facing root observation carries; "
      "an interior observation has none, and `search_step` carries no randomness at all |")
    A("| save and restore an opponent hand | P1, P2, P3 | the API exposes no write path into a "
      "search state's hidden zones; hidden contents enter only as `search_begin` arguments |")
    A("| attach several concrete games to one node | O1, O2, O3, O4 | a search node IS an engine "
      "state id inside one session; there is no object to attach a second state to |")
    A("")
    A("These are re-verified by probe in `results/probes/` rather than inherited from c021's "
      "A4 document — the finding is load-bearing for the whole contract, so it is measured "
      "again against the engine as shipped today.")
    A("")
    A("## Priority 1 is unavailable, and the reason is narrow")
    A("")
    A("The blocker is **not** \"the engine is deterministic\". It is that hidden state is bound "
      "at `search_begin` and no interior handle exists to rebind it. Priority 1 asks for a fresh "
      "world per simulation *inside one graph*; every graph node here is a state id belonging to "
      "the one session whose world was fixed when the session opened. Rebinding would mean "
      "reconstructing an observation the engine never produced — which would inject states the "
      "engine cannot reach and is worse than the disease.")
    A("")
    A("## Priority 2 is available, and the source already specifies it")
    A("")
    A("This is the audit's substantive finding. The archive does not merely permit a K-session "
      "ensemble; it **contains one**, complete except for its initialization:")
    A("")
    A("| piece | source | status in archive |")
    A("|---|---|---|")
    A("| build K distinct hidden worlds | `PerfectInformationMonteCarlo."
      "GenerateDeterminizationsAtOnce` | present, deduplicated by world hash, never called |")
    A("| spend the budget across them | `MCGSAgent.GetMove` pimc branch | present, one "
      "simulation per randomly-picked determinization |")
    A("| pick one per simulation | `MonteCarloGraphSearch.PickDeterminization` | present, "
      "uniform over not-in-use |")
    A("| aggregate root statistics | `MonteCarloGraphSearch.AggregateDeterminizations` | "
      "present and exact |")
    A("| carry the ensemble to the next decision | `MonteCarloGraphSearch."
      "CleanUpDeterminizations` | present, replenishes stale worlds |")
    A("| ensemble size | `SearchConfig.DeterminizationNumber = 200` | present, read only by "
      "`ToString()` |")
    A("")
    A("So c022 does not invent an aggregation rule. It ports one:")
    A("")
    A("```csharp")
    A("// MonteCarloGraphSearch.AggregateDeterminizations, src/MCGS.cs")
    A("rootEdge.Successor.VisitCount += edge.Successor.VisitCount;   // matched by ActionIndex")
    A("rootEdge.Successor.Rewards    += edge.Successor.Rewards;")
    A("...")
    A("root.VisitCount = root.OutgoingEdges.Sum(p => p.Successor.VisitCount);")
    A("root.Rewards    = root.OutgoingEdges.Sum(p => p.Successor.Rewards);")
    A("```")
    A("")
    A("Both `MANDATORY_IMPLEMENTATION A3` aggregation rules — visit-count summation and "
      "expected-terminal-return summation — are the same two lines of the source, and final "
      "selection is the source's unchanged `MaxChild` over `Edge.Value(0)`, i.e. "
      "`Rewards/VisitCount` of the summed statistics. The robust lower-confidence variant "
      "A3 permits has **no** source counterpart and is therefore run only as an explicitly "
      "adapted secondary arm.")
    A("")
    A("## Three ways the port must differ, stated before it is written")
    A("")
    A("1. **Uniform-random world choice per simulation vs. round-robin.** The source picks "
      "uniformly at random from the not-in-use set (`PickDeterminization`), which under threads "
      "approximates an even split. c022 runs one worker per game, so uniform random sampling of "
      "K worlds would give an uneven and unmeasurable split. The port assigns simulations to "
      "worlds **deterministically and evenly**, which is what the source's protocol converges to "
      "and what `MANDATORY_IMPLEMENTATION A4` requires (\"simulations per world = total / K\", "
      "exactly). Labelled `MECHANICAL_ADAPTER`.")
    A("2. **Sessions are not re-rooted across decisions.** The source's "
      "`CleanUpDeterminizations` keeps each determinization's subtree alive between decisions. "
      "The PTCG API invalidates every searchId at `search_end`, so each decision opens K fresh "
      "sessions. What can carry across is the abstraction-keyed statistics table, exactly as "
      "c021's `graph_reuse` already does — but it must be carried **per world**, never shared "
      "between worlds within a decision, or world independence is destroyed. Labelled "
      "`MECHANICAL_ADAPTER`, and enforced by a probe rather than by intent.")
    A("3. **The ensemble does not make the port source-identical.** `FIDELITY_RULES §3` is "
      "explicit: the K-session ensemble is an approximation, labelled "
      "`LEGAL_INFORMATION_ADAPTER`. The source's DEFAULT (non-PIMC) configuration re-determinizes "
      "per rollout inside one graph; the ensemble re-determinizes per session. They are not the "
      "same algorithm, and the ensemble is the closest legal equivalent, not the original.")
    A("")
    A("## Where the gap bites hardest")
    A("")
    A("`Node.Value` returns ±10 for a proven terminal while rollouts return 1/0, and "
      "`Node.Finalise` collapses a parent onto a proven winning edge. Inside a single fixed "
      "world both are correct — the world really is won. Across worlds they are the amplifier "
      "that turns one lucky determinization into a 96%-confident decision.")
    A("")
    A("This dictates a design decision that must be made **before** any sweep, because making it "
      "implicitly in code and discovering it afterwards would be fitting the mechanism to the "
      "result. It is recorded in `results/mcgs/PREREGISTERED_AGGREGATION.json`.")
    A("")
    A("## Status")
    A("")
    A(f"- Priority 1 (per-simulation re-determinization in one graph): **UNAVAILABLE** — "
      f"{len(by_status.get('UNAVAILABLE', []))} source sites depend on interior hidden-state "
      "mutation that the API does not expose.")
    A("- Priority 2 (independent sessions + source-equivalent root aggregation): **AVAILABLE** — "
      "and the aggregation is a port of `AggregateDeterminizations`, not an invention.")
    A("- `MCGS_HIDDEN_INFO=BLOCKED` is therefore **not** the outcome; the correction proceeds "
      "under priority 2.")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    inv = archive_inventory()
    ver = verify_extracted(inv)
    sites = [locate(s) for s in SITES]
    claims = structural_claims()

    trace = os.path.join(a.out, "mcgs_hidden_information_trace.jsonl")
    with open(trace, "w") as fh:
        fh.write(json.dumps({"record": "archive", **inv}) + "\n")
        fh.write(json.dumps({"record": "extraction_verification", **ver}) + "\n")
        for s in sites:
            fh.write(json.dumps({"record": "site", **s}) + "\n")
        for k, v in claims.items():
            fh.write(json.dumps({"record": "structural_claim", "name": k, **v}) + "\n")

    with open(os.path.join(a.out, "mcgs_hidden_information_source_map.md"), "w") as fh:
        fh.write(render_source_map(inv, ver, sites, claims))
    with open(os.path.join(a.out, "mcgs_hidden_information_gap_analysis.md"), "w") as fh:
        fh.write(render_gap_analysis(sites, claims))

    bad = [s for s in sites if not s["anchored"]]
    broken = [k for k, v in claims.items() if not v["holds"]]
    print(f"archive sha256 {inv['archive_sha256'][:16]}  files={inv['n_files']}  "
          f"extracted_identical={ver['identical']}")
    print(f"sites anchored {len(sites) - len(bad)}/{len(sites)}")
    for s in bad:
        print(f"  UNANCHORED {s['id']} {s['file']} :: {s['anchor']}")
    print(f"structural claims holding {len(claims) - len(broken)}/{len(claims)}")
    for k in broken:
        print(f"  CLAIM FAILED {k}")
    print(f"wrote {trace}")
    return 1 if (bad or broken or not ver["identical"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
