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
    for src, origin_map in (("official", OFFICIAL), ("public", PUBLIC)):
        for pid, (d, origin) in origin_map.items():
            out[pid] = {"player_id": pid, "dir": d, "origin": origin, "source_class": src,
                        "exists": os.path.isfile(os.path.join(d, "main.py"))}
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
        return self._mod.agent(obs)

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
    # Package-style agents (tetsutani) import helper modules under their own top-level names.
    # Those must not survive the game, or the next load reuses this game's state.
    purge = [n for n in set(sys.modules) - before]
    deck = list(mod.agent({"select": None, "logs": [], "current": None}))
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
