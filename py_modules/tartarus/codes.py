"""Canonical key names and their evdev codes (linux/input-event-codes.h)."""
from __future__ import annotations

from typing import Dict, Optional

# Pseudo-codes for wheel outputs. They never reach uinput as EV_KEY;
# the engine turns them into REL_WHEEL ticks.
WHEEL_UP = -1
WHEEL_DOWN = -2

KEYS: Dict[str, int] = {
    # Letters
    "A": 30, "B": 48, "C": 46, "D": 32, "E": 18, "F": 33, "G": 34, "H": 35,
    "I": 23, "J": 36, "K": 37, "L": 38, "M": 50, "N": 49, "O": 24, "P": 25,
    "Q": 16, "R": 19, "S": 31, "T": 20, "U": 22, "V": 47, "W": 17, "X": 45,
    "Y": 21, "Z": 44,
    # Digits
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    # Function keys
    "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64, "F7": 65,
    "F8": 66, "F9": 67, "F10": 68, "F11": 87, "F12": 88,
    "F13": 183, "F14": 184, "F15": 185, "F16": 186, "F17": 187, "F18": 188,
    "F19": 189, "F20": 190, "F21": 191, "F22": 192, "F23": 193, "F24": 194,
    # Editing and navigation
    "Esc": 1, "Tab": 15, "CapsLock": 58, "Space": 57, "Enter": 28,
    "Backspace": 14, "Delete": 111, "Insert": 110, "Home": 102, "End": 107,
    "PageUp": 104, "PageDown": 109, "Up": 103, "Down": 108, "Left": 105,
    "Right": 106,
    # Punctuation
    "Minus": 12, "Equal": 13, "LeftBracket": 26, "RightBracket": 27,
    "Backslash": 43, "Semicolon": 39, "Apostrophe": 40, "Grave": 41,
    "Comma": 51, "Period": 52, "Slash": 53,
    # System
    "PrintScreen": 99, "Pause": 119, "ScrollLock": 70, "NumLock": 69,
    # Keypad
    "KP0": 82, "KP1": 79, "KP2": 80, "KP3": 81, "KP4": 75, "KP5": 76,
    "KP6": 77, "KP7": 71, "KP8": 72, "KP9": 73, "KPEnter": 96, "KPPlus": 78,
    "KPMinus": 74, "KPAsterisk": 55, "KPSlash": 98, "KPDot": 83,
    # Modifiers (plain names are the left-hand keys)
    "Shift": 42, "Ctrl": 29, "Alt": 56, "Super": 125,
    "RShift": 54, "RCtrl": 97, "RAlt": 100,
    # Mouse
    "LMB": 0x110, "RMB": 0x111, "MMB": 0x112, "Mouse4": 0x113, "Mouse5": 0x114,
    "WheelUp": WHEEL_UP, "WheelDown": WHEEL_DOWN,
    # Media
    "Vol+": 115, "Vol-": 114, "Mute": 113, "Play": 164, "Next": 163, "Prev": 165,
}

MODIFIERS = frozenset({"Shift", "Ctrl", "Alt", "Super", "RShift", "RCtrl", "RAlt"})
MOUSE = frozenset({"LMB", "RMB", "MMB", "Mouse4", "Mouse5", "WheelUp", "WheelDown"})
MEDIA = frozenset({"Vol+", "Vol-", "Mute", "Play", "Next", "Prev"})

_BY_LOWER = {name.lower(): name for name in KEYS}
_BY_CODE = {code: name for name, code in KEYS.items()}


def canonical(name: str) -> str:
    """The canonical spelling of a key name; raises KeyError if unknown."""
    return _BY_LOWER[name.strip().lower()]


def code_for(name: str) -> int:
    return KEYS[canonical(name)]


def name_for(code: int) -> Optional[str]:
    return _BY_CODE.get(code)


def category(name: str) -> str:
    """One of "key", "modifier", "mouse", "media"."""
    name = canonical(name)
    if name in MODIFIERS:
        return "modifier"
    if name in MOUSE:
        return "mouse"
    if name in MEDIA:
        return "media"
    return "key"
