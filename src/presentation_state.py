"""
Pure helpers for UI presentation state.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from models import PortInfo


def summarize_port_chips(ports: Sequence[PortInfo], limit: int = 3) -> tuple[str, ...]:
    """Returns up to ``limit`` port labels for compact folder summaries."""
    return tuple(f":{port.port}" for port in ports[:limit])


def merge_group_visibility_state(
    expanded_groups: set[str],
    known_groups: set[str],
    groups: Iterable[tuple[str, int]],
) -> tuple[set[str], set[str]]:
    """
    Registers discovered groups without opening them automatically.

    Folder expansion is user-owned state: newly discovered localhost groups stay
    collapsed until the user explicitly opens them.
    Returns updated ``expanded_groups`` and ``known_groups`` copies.
    """
    next_expanded = set(expanded_groups)
    next_known = set(known_groups)

    for group_key, _active_count in groups:
        if group_key not in next_known:
            next_known.add(group_key)

    return next_expanded, next_known
