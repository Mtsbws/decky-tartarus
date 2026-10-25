"""Which D-pad controls are active for a set of pressed cardinals.

The hardware is 8-way but sends a diagonal as two cardinal codes, so diagonals
are worked out here.
"""
from __future__ import annotations

from typing import FrozenSet

_OPPOSITES = (("dpad_up", "dpad_down"), ("dpad_left", "dpad_right"))
_DIAGONALS = {
    frozenset({"dpad_up", "dpad_right"}): "dpad_up_right",
    frozenset({"dpad_down", "dpad_right"}): "dpad_down_right",
    frozenset({"dpad_down", "dpad_left"}): "dpad_down_left",
    frozenset({"dpad_up", "dpad_left"}): "dpad_up_left",
}


def resolve_dpad(pressed: FrozenSet[str], mode: str) -> FrozenSet[str]:
    if mode != "8way":
        # 4-way: a diagonal holds both neighbouring bindings.
        return frozenset(pressed)
    active = set(pressed)
    for a, b in _OPPOSITES:
        if a in active and b in active:
            active -= {a, b}
    diagonal = _DIAGONALS.get(frozenset(active))
    if diagonal:
        return frozenset({diagonal})
    return frozenset(active)
