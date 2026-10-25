"""The keypad's physical controls and what it sends from the factory.

Source: the S1 table in docs/superpowers/spike-findings.md.
"""
from __future__ import annotations

from typing import Dict

from .codes import KEYS

KEY_CONTROLS = tuple(f"k{i:02d}" for i in range(1, 21)) + ("top_button", "wheel_click")
WHEEL_CONTROLS = ("wheel_up", "wheel_down")
DPAD_CARDINALS = ("dpad_up", "dpad_right", "dpad_down", "dpad_left")
DPAD_DIAGONALS = ("dpad_up_right", "dpad_down_right", "dpad_down_left", "dpad_up_left")
ALL_CONTROLS = KEY_CONTROLS + WHEEL_CONTROLS + DPAD_CARDINALS + DPAD_DIAGONALS

# Control id -> the key name it sends with no remapping. Rows: k01-05, k06-10,
# k11-15, k16-19 (four keys), k20 is the big thumb key.
_FACTORY_KEYS = {
    "k01": "1", "k02": "2", "k03": "3", "k04": "4", "k05": "5",
    "k06": "Tab", "k07": "Q", "k08": "W", "k09": "E", "k10": "R",
    "k11": "CapsLock", "k12": "A", "k13": "S", "k14": "D", "k15": "F",
    "k16": "Shift", "k17": "Z", "k18": "X", "k19": "C",
    "k20": "Space",
    "top_button": "Alt",
    "wheel_click": "MMB",
    "dpad_up": "Up", "dpad_right": "Right", "dpad_down": "Down", "dpad_left": "Left",
}

# Evdev code -> control id, for every EV_KEY the keypad sends.
FACTORY_CODES: Dict[int, str] = {KEYS[name]: control for control, name in _FACTORY_KEYS.items()}

# Control id -> factory binding text. Diagonals hold both neighbouring cardinals.
FACTORY_OUTPUT: Dict[str, str] = dict(_FACTORY_KEYS)
FACTORY_OUTPUT.update({
    "wheel_up": "WheelUp",
    "wheel_down": "WheelDown",
    "dpad_up_right": "hold:Up+Right",
    "dpad_down_right": "hold:Down+Right",
    "dpad_down_left": "hold:Down+Left",
    "dpad_up_left": "hold:Up+Left",
})
