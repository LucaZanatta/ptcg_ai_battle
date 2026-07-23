"""Deterministic, legal, engine-agnostic action selection for the cabt agent.

What "safe" guarantees
----------------------
For any *valid* cabt ``Select`` (bounds satisfying
``0 <= minCount <= maxCount <= len(option)``), :func:`select_for` /
:func:`select_indices` return a deterministic ``list[int]`` of distinct,
in-range option indices whose length the engine accepts. The chosen length is
exactly ``maxCount`` and the chosen indices are the first ``maxCount`` options in
engine order (``list(range(maxCount))``); an empty list is returned when
``maxCount == 0``.

This convention is engine-sanctioned: the reference environment ships
``first_agent`` returning ``list(range(obs["select"]["maxCount"]))``
(``kaggle_environments/envs/cabt/cabt.py``). Because ``maxCount`` always lies in
``[minCount, maxCount]`` and never exceeds ``len(option)``, this selection is
always legal for a valid observation.

Why engine option order
------------------------
The engine presents ``option`` already filtered to legal choices, so any fixed
prefix of it is legal. Taking the first ``maxCount`` options makes the choice
reproducible and free of any tie-breaking heuristic.

What "safe" does NOT guarantee
------------------------------
Strategic quality. This module never scores options; it is a legality and
determinism baseline, not a strategy agent.

Malformed observations
-----------------------
Bounds that violate the cabt ``Select`` contract (non-integer / negative counts,
``minCount > maxCount``, ``maxCount > len(option)``) raise
:class:`MalformedSelection` rather than silently fabricating an action. The
public production path is only required to be safe for valid cabt observations;
impossible engine states are surfaced, not hidden.

Determinism
-----------
No random-number generation, no wall-clock, no dependence on dict hash-iteration
or mutable hidden state. Given the same inputs the outputs are identical.
"""

from __future__ import annotations

import os
from typing import Any, List, Sequence, Tuple

DECK_SIZE = 60


class MalformedSelection(ValueError):
    """Raised when selection metadata violates the cabt ``Select`` contract."""


class MalformedDeck(ValueError):
    """Raised when a deck is not exactly ``DECK_SIZE`` integer card IDs."""


def _as_int(value: Any, name: str) -> int:
    """Coerce an integer-like value to ``int``; reject ``bool`` and non-integers."""
    if isinstance(value, bool):
        raise MalformedSelection(f"{name} must be an integer, not bool: {value!r}")
    try:
        return int(value.__index__())
    except AttributeError:
        raise MalformedSelection(
            f"{name} must be integer-like, got {type(value).__name__}: {value!r}"
        )


def validate_bounds(num_options: Any, min_count: Any, max_count: Any) -> Tuple[int, int, int]:
    """Validate cabt selection bounds. Return ``(num_options, min_count, max_count)``.

    Raises :class:`MalformedSelection` if the bounds are not a valid cabt
    ``Select`` contract: counts must be non-negative integers with
    ``min_count <= max_count <= num_options``.
    """
    n = _as_int(num_options, "num_options")
    lo = _as_int(min_count, "minCount")
    hi = _as_int(max_count, "maxCount")
    if n < 0:
        raise MalformedSelection(f"num_options must be non-negative, got {n}")
    if lo < 0 or hi < 0:
        raise MalformedSelection(f"counts must be non-negative, got minCount={lo}, maxCount={hi}")
    if lo > hi:
        raise MalformedSelection(f"minCount ({lo}) > maxCount ({hi})")
    if hi > n:
        raise MalformedSelection(f"maxCount ({hi}) > number of options ({n})")
    return n, lo, hi


def select_indices(num_options: Any, min_count: Any, max_count: Any) -> List[int]:
    """Deterministically select the first ``max_count`` option indices.

    Returns ``[]`` when ``max_count == 0``. Raises :class:`MalformedSelection`
    for invalid bounds (see :func:`validate_bounds`).
    """
    _n, _lo, hi = validate_bounds(num_options, min_count, max_count)
    return list(range(hi))


def select_for(select: Any) -> List[int]:
    """Deterministic selection for a ``Select``-like object.

    Duck-typed: ``select`` must expose ``option`` (a sized sequence),
    ``minCount`` and ``maxCount``. Returns deterministic indices via
    :func:`select_indices`.
    """
    return select_indices(len(select.option), select.minCount, select.maxCount)


def validate_selection(
    indices: Sequence[Any], num_options: Any, min_count: Any, max_count: Any
) -> bool:
    """Verify ``indices`` satisfy the engine contract for the given bounds.

    Returns ``True`` if valid; otherwise raises :class:`MalformedSelection`.
    A valid selection is a list of distinct integers, each in
    ``[0, num_options)``, whose length is in ``[min_count, max_count]``.
    """
    n, lo, hi = validate_bounds(num_options, min_count, max_count)
    if not isinstance(indices, list):
        raise MalformedSelection(f"selection must be a list, got {type(indices).__name__}")
    ints = [_as_int(i, "index") for i in indices]
    if len(set(ints)) != len(ints):
        raise MalformedSelection(f"selection contains duplicate indices: {indices!r}")
    if not (lo <= len(ints) <= hi):
        raise MalformedSelection(
            f"selection count {len(ints)} outside [minCount={lo}, maxCount={hi}]"
        )
    for i in ints:
        if not (0 <= i < n):
            raise MalformedSelection(f"index {i} out of range [0, {n})")
    return True


def default_deck_path() -> str:
    """Resolve ``deck.csv`` relative to this module (falling back to the Kaggle
    runner path). Never a user-specific absolute path."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv")
    if os.path.exists(local):
        return local
    return "/kaggle_simulations/agent/deck.csv"


def parse_deck(text: str, *, deck_size: int = DECK_SIZE) -> List[int]:
    """Parse deck text into a list of exactly ``deck_size`` integer card IDs.

    Empty/whitespace-only lines are ignored. Any non-empty line that is not an
    integer raises :class:`MalformedDeck` (no silent omission). A total count
    other than ``deck_size`` raises :class:`MalformedDeck`.
    """
    ids: List[int] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped == "":
            continue
        try:
            ids.append(int(stripped))
        except ValueError:
            raise MalformedDeck(f"deck line {lineno} is not an integer card ID: {line!r}")
    if len(ids) != deck_size:
        raise MalformedDeck(f"deck must contain exactly {deck_size} card IDs, found {len(ids)}")
    return ids


def load_deck(path: str | None = None) -> List[int]:
    """Load and validate the deck from ``path`` (default: :func:`default_deck_path`)."""
    if path is None:
        path = default_deck_path()
    with open(path, "r") as fh:
        return parse_deck(fh.read())
