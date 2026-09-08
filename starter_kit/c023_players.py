"""c023 — a single loader for every kind of player in this campaign.

A *player* here is exactly what the competition packages: a directory holding `main.py` and
`deck.csv` (plus, for package-style agents, whatever modules `main.py` imports). That is the
shape of the official samples, of every public kernel this campaign extracted, and of every
candidate it builds — so one loader covers all three and no comparison is ever between two
differently-constructed objects.

Two properties this module exists to guarantee:

1. **Fresh state per game per seat.** Every one of these agents keeps module-level state (turn
   counters, attack plans, ability flags) and none of them reset on the deck handshake. c005
   established that a shared instance silently leaks a previous game's plan into the next one.
   So each load gets its own module name, and package-style agents get their newly-imported
   top-level modules purged afterwards — otherwise `sys.modules["policy_core"]` survives the
   game and the *next* load silently reuses the previous game's state.

2. **Provenance that travels with the object.** `main_sha256`, `deck_sha256` and the resolved
   directory ride on the loaded player, so an evaluation record can prove which bytes played.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from typing import Any, Callable, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEACHER_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                               "results", "artifacts", "teacher_sources")
KERNEL_SOURCES = os.path.join(_REPO, "external_refs", "c023_public_kernels", "_extracted")
C023_AGENTS = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint",
                           "agents")

# Registry: player_id -> (directory, origin class). Origin drives the reuse/licence question,
# never the evaluation: every player is measured identically.
OFFICIAL = {
    "official_dragapult": (os.path.join(TEACHER_SOURCES, "dragapult"), "official_kaggle_sample"),
    "official_mega_lucario": (os.path.join(TEACHER_SOURCES, "mega_lucario"), "official_kaggle_sample"),
    "official_mega_abomasnow": (os.path.join(TEACHER_SOURCES, "mega_abomasnow"), "official_kaggle_sample"),
    "official_iono": (os.path.join(TEACHER_SOURCES, "iono"), "official_kaggle_sample"),
}

PUBLIC = {
    "pub_jazivxt_codex_alakazam": (os.path.join(KERNEL_SOURCES, "jazivxt_codex-sol-eclipse-alakazam"),
                                   "public_kernel"),
    "pub_jazivxt_rising_tide_v21": (os.path.join(KERNEL_SOURCES, "jazivxt_a-better-hand-alakazam-rising-tide-v21"),
                                    "public_kernel"),
    "pub_prvsiyan_lucario_v12": (os.path.join(KERNEL_SOURCES, "prvsiyan_ptcg-ai-battle-search-audited-alakazam-v12"),
                                 "public_kernel"),
    "pub_raunakdey_heuristic": (os.path.join(KERNEL_SOURCES, "raunakdey07_pok-mon-tcg-advanced-heuristic-agent"),
                                "public_kernel"),
    "pub_tetsutani_grimmsnarl": (os.path.join(KERNEL_SOURCES, "tetsutani_grimmsnarl-ex-damage-transfer-control"),
                                 "public_kernel"),
    "pub_makthanithin_lucario_1084": (os.path.join(KERNEL_SOURCES, "makthanithin_pokemon-tcg-ai-battle-1084-5-baseline"),
                                      "public_kernel"),
    # Added after our own ladder replays showed Crustle Wall is the champion's WORST real
    # matchup (0.222 over 9 games) and that no panel opponent resembled it.
    "pub_prvsiyan_crustle_wall": (os.path.join(KERNEL_SOURCES, "prvsiyan_ptcg-tusk-crustle-terrakion-v1-public"),
                                  "public_kernel"),
}

# The c024 additions. The c023 panel was assembled by vote count and archetype coverage; these
# were selected on a different criterion -- the author advertises a ladder rating in the title.
# Every one of them claims a number above our champion's 788.1, and none had ever been run here.
# Same classification as everything else in PUBLIC: opponents and sources of technique, never a
# submission base, because the Kaggle API exposes no licence field for a notebook.
C024_KERNELS = os.path.join(_REPO, "external_refs", "c024_public_kernels", "_extracted")

PUBLIC.update({
    "pub_soutasakurai_libraryout_1208": (
        os.path.join(C024_KERNELS, "soutasakurai_max-elo-1208-libraryout-w-crustle-great-tusk"),
        "public_kernel"),
    "pub_prvsiyan_tusk_1208_v24": (
        os.path.join(C024_KERNELS, "prvsiyan_ptcg-ai-battle-static-deck-tusk-1208-v24"),
        "public_kernel"),
    "pub_prvsiyan_lopunny_1208": (
        os.path.join(C024_KERNELS, "prvsiyan_ptcg-rmy-surface-souta-1208-loader-v1"),
        "public_kernel"),
    "pub_ryotasueyoshi_alakazam_5th": (
        os.path.join(C024_KERNELS, "ryotasueyoshi_rule-based-not-psychic-alakazam-best-5th"),
        "public_kernel"),
    "pub_masamikobayashi_archaludon": (
        os.path.join(C024_KERNELS, "masamikobayashi_a-sample-archaludon-75-wr-vs-my-1300-starmie"),
        "public_kernel"),
    "pub_romanrozen_v10_950": (
        os.path.join(C024_KERNELS, "romanrozen_strong-start-baseline-agent-v10-lb-950"),
        "public_kernel"),
    "pub_borealis27_1050": (
        os.path.join(C024_KERNELS, "borealis27_elo-1050-rule-based-agent-matchup-tests"),
        "public_kernel"),
    "pub_aristophanivan_multiply_940": (
        os.path.join(C024_KERNELS, "aristophanivan_multiply-agent-best-940-lb"),
        "public_kernel"),
    "pub_penguin069_915": (
        os.path.join(C024_KERNELS, "penguin069_public-scores-915"), "public_kernel"),
})

# Our own two custom agents, extracted from the exact archives that were uploaded. They are on
# the panel for one reason: their Kaggle ladder score rates are already measured (0.3333 and
# 0.4206 over 33 and 107 public games), so measuring them locally turns the local-to-ladder
# calibration from a line through two points into a line through four.
C024_AGENTS = os.path.join(_REPO, "results", "c024_final_sprint", "agents")

OURS = {
    "c014_archaludon_expert": (os.path.join(KERNEL_SOURCES, "c014_archaludon_expert"),
                               "c023_prior_contract_submission"),
    "c015_anti_meta_expert": (os.path.join(KERNEL_SOURCES, "c015_anti_meta_expert"),
                              "c023_prior_contract_submission"),
}

# player_id -> the name the kernel itself declares as its competition callable, for the kernels
# that do not call it `agent`. Taken from the kernel's own EXPECTED_FINAL_CALLABLE constant.
_ENTRYPOINT_ALIASES = {
    "pub_prvsiyan_lopunny_1208": "mega_lopunny_cleanroom_entrypoint",
}

_load_counter = [0]
_SHA: Dict[str, str] = {}


def sha256_file(path: str) -> str:
    if path in _SHA:
        return _SHA[path]
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    _SHA[path] = h.hexdigest()
    return _SHA[path]


def registry() -> Dict[str, Any]:
    """Every player this repository can currently run, resolved and existence-checked."""
    out: Dict[str, Any] = {}
    for src, origin_map in (("official", OFFICIAL), ("public", PUBLIC), ("ours", OURS)):
        for pid, (d, origin) in origin_map.items():
            out[pid] = {"player_id": pid, "dir": d, "origin": origin, "source_class": src,
                        "exists": os.path.isfile(os.path.join(d, "main.py"))}
    for root in (C024_AGENTS,):
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                d = os.path.join(root, name)
                if os.path.isfile(os.path.join(d, "main.py")):
                    out[name] = {"player_id": name, "dir": d, "origin": "c024_candidate",
                                 "source_class": "candidate", "exists": True}
    if os.path.isdir(C023_AGENTS):
        for name in sorted(os.listdir(C023_AGENTS)):
            d = os.path.join(C023_AGENTS, name)
            if os.path.isfile(os.path.join(d, "main.py")):
                out[name] = {"player_id": name, "dir": d, "origin": "c023_candidate",
                             "source_class": "candidate", "exists": True}
    return out


def resolve(player_id: str) -> str:
    reg = registry()
    if player_id not in reg:
        raise KeyError(f"unknown player_id {player_id!r}; known: {sorted(reg)}")
    d = reg[player_id]["dir"]
    if not os.path.isfile(os.path.join(d, "main.py")):
        raise FileNotFoundError(f"{player_id}: no main.py under {d}")
    return d


class LoadedPlayer:
    """One game's worth of one agent: a callable, its deck, and the hashes of the bytes that ran."""

    def __init__(self, player_id: str, directory: str, module: Any, deck: List[int],
                 purge: List[str]):
        self.player_id = player_id
        self.dir = directory
        self._mod = module
        self._purge = purge
        self.deck = deck
        self.main_sha256 = sha256_file(os.path.join(directory, "main.py"))
        deck_path = os.path.join(directory, "deck.csv")
        self.deck_sha256 = sha256_file(deck_path) if os.path.exists(deck_path) else None

    def __call__(self, obs: Any) -> List[int]:
        # The working directory is set to the agent's own package for the duration of the call.
        # Most agents read their deck.csv at import time, when the loader has already chdir'd --
        # but some read it LAZILY, on the first call, by which time the loader has restored the
        # cwd and the relative open() fails. (Same shape as the tetsutani sys.path defect: work
        # deferred past the point where the loader had set things up.) Two agents share a process
        # here, so the cwd cannot simply be left set; it is set and restored per call instead.
        old = os.getcwd()
        try:
            os.chdir(self.dir)
        except Exception:
            pass
        try:
            return self._mod.agent(obs)
        finally:
            try:
                os.chdir(old)
            except Exception:
                pass

    def close(self) -> None:
        """Drop the modules this load introduced, so the next load starts from zero state."""
        for name in self._purge:
            sys.modules.pop(name, None)
        self._purge = []


def make_fresh(player_id: str) -> LoadedPlayer:
    """Load a FRESH instance. Never cache the result across games."""
    d = os.path.abspath(resolve(player_id))
    _load_counter[0] += 1
    modname = f"c023_player_{_load_counter[0]}"
    before = set(sys.modules)
    old_cwd = os.getcwd()
    os.chdir(d)  # the agents read a relative deck.csv at import time
    # The agent's own directory must STAY on sys.path. Package-style agents (tetsutani) import
    # their policy lazily at the first real decision, long after this function returns; restoring
    # sys.path here made that import fail and the agent silently played its legal-but-mindless
    # fallback for the whole game, which reads as a weak agent rather than as a harness bug.
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        spec = importlib.util.spec_from_file_location(modname, os.path.join(d, "main.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[modname] = mod
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old_cwd)
    # Not every kernel names its competition callable `agent`. The prvsiyan Lopunny loader
    # declares `EXPECTED_FINAL_CALLABLE = 'mega_lopunny_cleanroom_entrypoint'` and leaves the
    # binding to its own submission builder, which the extractor does not run. Without this the
    # module loads cleanly and then every decision raises AttributeError -- 6 errored games and
    # no score, which is how it first showed up. Bind by the kernel's own declared name; never
    # guess, and never fall back to "the only function that takes one argument".
    if not hasattr(mod, "agent"):
        alias = _ENTRYPOINT_ALIASES.get(player_id)
        if alias and hasattr(mod, alias):
            mod.agent = getattr(mod, alias)
        else:
            raise AttributeError(
                f"{player_id}: main.py exposes no `agent`; add its declared entry point to "
                f"_ENTRYPOINT_ALIASES (module defines: "
                f"{[n for n in vars(mod) if callable(vars(mod)[n]) and not n.startswith('_')][:8]})")
    # Package-style agents (tetsutani) import helper modules under their own top-level names.
    # Those must not survive the game, or the next load reuses this game's state.
    purge = [n for n in set(sys.modules) - before]
    # The deck handshake is also a CALL, and agents that read deck.csv lazily need the cwd set
    # for it too -- not only for the import.
    os.chdir(d)
    try:
        deck = list(mod.agent({"select": None, "logs": [], "current": None}))
    finally:
        os.chdir(old_cwd)
    return LoadedPlayer(player_id, d, mod, deck, purge)


def agent_callable(player: LoadedPlayer) -> Callable[[Any], List[int]]:
    """A genuine one-parameter closure.

    `kaggle_environments` passes (observation, configuration) to ANY callable accepting two
    parameters, so a default-argument capture silently receives the config as its second
    argument and every game dies as a swallowed error. Recorded three times in this repo.
    """
    def f(o):
        return player(o)
    return f
