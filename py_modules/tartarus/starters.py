"""Starter profiles: ready-made layouts a fresh install gets and "New profile" can copy.

Data only, as binding text like `config.STEAMOS_DEFAULT`; config.py builds profiles from it.
`bindings` lists only controls that differ from the factory key; `secondary` maps a control to
(binding text, mm). The tables in docs/starter-profiles.md describe the same layouts.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

STARTER_PREFIX = "starter:"


@dataclass(frozen=True)
class Starter:
    id: str
    name: str
    bindings: Mapping[str, str]
    actuation: Mapping[str, float]
    secondary: Mapping[str, Tuple[str, float]]
    hypershift: Mapping[str, str]


def _starter(slug: str, name: str, bindings: dict, actuation: dict,
             secondary: Optional[dict] = None, hypershift: Optional[dict] = None) -> Starter:
    return Starter(STARTER_PREFIX + slug, name, MappingProxyType(bindings), MappingProxyType(actuation),
                   MappingProxyType(secondary or {}), MappingProxyType(hypershift or {}))


# Movement on the keys; the D-pad holds weapon slots 3-6.
_FPS_WASD = _starter("fps-wasd", "FPS – WASD", {
    "k01": "Esc", "k02": "1", "k03": "2", "k04": "T", "k05": "F",
    "k06": "Tab", "k07": "Q", "k08": "W", "k09": "E", "k10": "R",
    "k11": "Shift", "k12": "A", "k13": "S", "k14": "D", "k15": "Y",
    "k16": "M", "k17": "Z", "k18": "G", "k19": "C", "k20": "Space",
    "top_button": "Alt",
    "dpad_up": "3", "dpad_right": "4", "dpad_down": "5", "dpad_left": "6",
    "wheel_up": "H", "wheel_down": "V", "wheel_click": "N",
}, {"k01": 2.5})

# Movement on the D-pad; the keys that held WASD take weapon slots and interact. No chat key.
_FPS_DPAD = _starter("fps-dpad", "FPS – D-pad", {
    "k01": "Esc", "k02": "1", "k03": "2", "k04": "3", "k05": "4",
    "k06": "Tab", "k07": "Q", "k08": "5", "k09": "E", "k10": "R",
    "k11": "Shift", "k12": "6", "k13": "F", "k14": "T", "k15": "G",
    "k16": "M", "k17": "Z", "k18": "X", "k19": "C", "k20": "Space",
    "top_button": "Alt",
    "dpad_up": "W", "dpad_right": "D", "dpad_down": "S", "dpad_left": "A",
    "wheel_up": "H", "wheel_down": "V", "wheel_click": "N",
}, {"k01": 2.5})

# World of Warcraft's default hotbar on twelve keys; holding k19 sends Ctrl+ the same keys (bar 2).
# k18's deep press (B, bags) is the one dual-stage demo, on a non-essential function.
_MMO = _starter("mmo", "MMO", {
    "k01": "Esc", "k02": "1", "k03": "2", "k04": "3", "k05": "4",
    "k06": "Tab", "k07": "5", "k08": "6", "k09": "7", "k10": "8",
    "k11": "Shift", "k12": "9", "k13": "0", "k14": "Minus", "k15": "Equal",
    "k16": "Ctrl", "k17": "C", "k18": "M", "k19": "Hypershift", "k20": "Alt",
    "top_button": "Space",
    "dpad_up": "W", "dpad_right": "D", "dpad_down": "S", "dpad_left": "A",
    "wheel_up": "PageUp", "wheel_down": "PageDown", "wheel_click": "NumLock",
}, {"k01": 2.5}, secondary={"k18": ("B", 3.0)}, hypershift={
    "k02": "Ctrl+1", "k03": "Ctrl+2", "k04": "Ctrl+3", "k05": "Ctrl+4",
    "k07": "Ctrl+5", "k08": "Ctrl+6", "k09": "Ctrl+7", "k10": "Ctrl+8",
    "k12": "Ctrl+9", "k13": "Ctrl+0", "k14": "Ctrl+Minus", "k15": "Ctrl+Equal",
})

STARTERS: Tuple[Starter, ...] = (_FPS_WASD, _FPS_DPAD, _MMO)


def find_starter(starter_id: str) -> Optional[Starter]:
    for s in STARTERS:
        if s.id == starter_id:
            return s
    return None
