"""Competition entrypoint for the Pokémon TCG AI Battle (cabt) challenge.

Deterministic **safe baseline**: it returns the validated 60-card deck during
deck selection and, for every valid engine selection, a legal deterministic list
of option indices (delegated to :mod:`cg.safe_policy`). It makes no attempt at
strategy and uses no randomness.

Imports use the ``cg`` package (a symlink to ``starter_kit`` at the repository
root and inside ``starter_kit``), matching the Kaggle submission convention. Do
not mix ``cg.*`` and ``starter_kit.*`` imports in one process — they resolve to
the same files but as distinct module objects, each re-initialising the engine.
Importing this module has no side effects beyond those imports; it runs no games.
"""

from cg.api import to_observation_class
from cg.safe_policy import load_deck, select_for

# The validated deck is loaded once, lazily, and cached. Deck loading validates
# that exactly 60 integer card IDs are present (raises on violation).
_DECK: list[int] | None = None


def _deck() -> list[int]:
    global _DECK
    if _DECK is None:
        _DECK = load_deck()
    return list(_DECK)


def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG agent entrypoint.

    During deck selection (``obs.select is None``) return the 60-card deck.
    Otherwise return a deterministic, legal ``list[int]`` of option indices.
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _deck()
    return select_for(obs.select)
