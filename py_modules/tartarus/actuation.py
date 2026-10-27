"""Key depth (driver mode) to key presses (pure).

Depth is a byte per key, 0x00 up to 0xFF fully down. Millimetre settings map to depth
through points measured against Synapse on this keypad (synapse-capture-findings.md).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

MM_MIN = 1.5
MM_MAX = 3.6
DEFAULT_MM = 1.5
MIN_GAP_MM = 0.5
HYSTERESIS = 8  # a key releases below its fire point minus this (about 0.07 mm)

# (mm, depth where Synapse fires): the one table to refine.
DEPTH_POINTS = ((1.5, 16), (2.5, 120), (3.6, 251))

DEPTH_REPORT_ID = 0x06
_KEYS = 20


def tenths(mm: float) -> int:
    return round(mm * 10)


def valid_mm(mm) -> bool:
    if isinstance(mm, bool) or not isinstance(mm, (int, float)):
        return False
    return MM_MIN <= mm <= MM_MAX and abs(mm * 10 - round(mm * 10)) < 1e-6


def gap_ok(a_mm: float, b_mm: float) -> bool:
    """B sits at least MIN_GAP_MM deeper than A (compared in tenths, never raw floats)."""
    return tenths(b_mm) - tenths(a_mm) >= tenths(MIN_GAP_MM)


def mm_to_depth(mm: float) -> int:
    """Piecewise linear through DEPTH_POINTS, clamped to its ends."""
    points = DEPTH_POINTS
    if mm <= points[0][0]:
        return points[0][1]
    for (mm0, d0), (mm1, d1) in zip(points, points[1:]):
        if mm <= mm1:
            return round(d0 + (mm - mm0) * (d1 - d0) / (mm1 - mm0))
    return points[-1][1]


def parse_depth_report(data: bytes) -> Optional[bytes]:
    """The 20 key depths from one interface 1 report, or None if it isn't a depth report."""
    if len(data) < _KEYS + 1 or data[0] != DEPTH_REPORT_ID:
        return None
    return bytes(data[1:_KEYS + 1])


class KeyTracker:
    """One key's state: fires slot "a" on the report that crosses its point, and slot "b"
    past the deeper point when the key has a secondary function.

    With B, only one slot is ever held. Coming up from B, the key is latched: A stays silent
    until the key drops below A's release point, while B can fire again from there.
    """

    def __init__(self, fire_a: int, fire_b: Optional[int] = None):
        self.fire_a = fire_a
        self.fire_b = fire_b
        self._held: Optional[str] = None  # "a", "b" or None
        self._latched = False
        self._blocked = False
        self.last = 0

    def feed(self, depth: int) -> List[Tuple[str, bool]]:
        self.last = depth
        release_a = self.fire_a - HYSTERESIS
        if self._blocked:
            if depth < release_a:
                self._blocked = False
            return []
        if self.fire_b is None:
            return self._feed_single(depth, release_a)
        return self._feed_secondary(depth, release_a, self.fire_b - HYSTERESIS)

    def _feed_single(self, depth: int, release_a: int) -> List[Tuple[str, bool]]:
        if self._held is None and depth >= self.fire_a:
            self._held = "a"
            return [("a", True)]
        if self._held == "a" and depth < release_a:
            self._held = None
            return [("a", False)]
        return []

    def _feed_secondary(self, depth: int, release_a: int, release_b: int) -> List[Tuple[str, bool]]:
        if self._held is None:
            if depth >= self.fire_b:
                self._held = "b"
                self._latched = False
                return [("b", True)]
            if self._latched:
                if depth < release_a:
                    self._latched = False
                return []
            if depth >= self.fire_a:
                self._held = "a"
                return [("a", True)]
            return []
        if self._held == "a":
            if depth >= self.fire_b:
                self._held = "b"
                return [("a", False), ("b", True)]
            if depth < release_a:
                self._held = None
                return [("a", False)]
            return []
        if depth < release_a:
            self._held = None
            return [("b", False)]
        if depth < release_b:
            self._held = None
            self._latched = True
            return [("b", False)]
        return []

    def reset(self) -> None:
        """Forget what is held; a key still down stays silent until it drops below its release point."""
        self._held = None
        self._latched = False
        self._blocked = self.last >= self.fire_a - HYSTERESIS
