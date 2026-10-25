"""RecordCapture: turns key presses on any keyboard into a Binding."""
from __future__ import annotations

from typing import List, Optional, Set

from .bindings import Binding
from .codes import canonical, category

MODIFIER_ORDER = ("Ctrl", "RCtrl", "Shift", "RShift", "Alt", "RAlt", "Super")


class RecordCapture:
    def __init__(self) -> None:
        self._order: List[str] = []  # names in first-press order
        self._down: Set[str] = set()

    def feed(self, name: str, down: bool) -> Optional[Binding]:
        """Feed one key event. Returns the Binding once every pressed key is released."""
        try:
            name = canonical(name)
        except KeyError:
            return None
        if down:
            if name not in self._down:
                self._down.add(name)
                if name not in self._order:
                    self._order.append(name)
            return None
        if name not in self._down:
            return None  # released before recording saw it pressed
        self._down.discard(name)
        if self._down:
            return None
        names, self._order = self._order, []
        if len(names) == 1:
            return Binding(category(names[0]), (names[0],))
        mods = [m for m in MODIFIER_ORDER if m in names]
        rest = [n for n in names if n not in MODIFIER_ORDER]
        return Binding("shortcut", tuple(mods + rest))
