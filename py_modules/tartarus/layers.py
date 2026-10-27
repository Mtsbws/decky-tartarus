"""Control addressing: which key, in which layer, primary or secondary function.

A control id is `X` (standard layer) or `X.h` (Hypershift layer) for any
control X; `kNN.b` / `kNN.h.b` address a key's secondary function.
"""
from __future__ import annotations

from dataclasses import dataclass

from .devmap import ACTUATION_KEYS, ALL_CONTROLS

B_SUFFIX = ".b"  # control kNN.b is key kNN's secondary function
H_SUFFIX = ".h"  # control X.h is X in the Hypershift layer
STANDARD = "standard"
HYPERSHIFT = "hypershift"


@dataclass(frozen=True)
class ControlRef:
    base: str
    layer: str
    slot: str  # "a" primary, "b" secondary function


def parse_control(control: str) -> ControlRef:
    rest, slot, layer = control, "a", STANDARD
    if rest.endswith(B_SUFFIX):
        rest, slot = rest[:-len(B_SUFFIX)], "b"
    if rest.endswith(H_SUFFIX):
        rest, layer = rest[:-len(H_SUFFIX)], HYPERSHIFT
    valid = ACTUATION_KEYS if slot == "b" else ALL_CONTROLS
    if rest not in valid:
        raise ValueError(f"unknown control {control!r}")
    return ControlRef(rest, layer, slot)
