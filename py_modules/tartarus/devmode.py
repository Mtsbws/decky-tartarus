"""The keypad's device mode (pure; sending is linux/hidraw.py).

Driver mode turns keys 01-20 into depth reports on interface 1 (report 0x06); normal
mode makes them plain keyboard keys again. Both take effect at once with no reset,
as checked on the Deck (docs/superpowers/synapse-capture-findings.md).
"""
from __future__ import annotations

from .lighting import build_report

DRIVER_MODE = 0x03
NORMAL_MODE = 0x00

_DEVICE = 0x00
_SET_MODE = 0x04


def set_mode_report(mode: int) -> bytes:
    if mode not in (DRIVER_MODE, NORMAL_MODE):
        raise ValueError(f"unknown device mode 0x{mode:02x}")
    return build_report(_DEVICE, _SET_MODE, bytes([mode, 0x00]))
