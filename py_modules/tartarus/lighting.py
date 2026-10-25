"""Razer feature reports for the keypad's lighting (pure; sending is linux/hidraw.py).

Byte values come from the OpenRazer source for 1532:0244, as recorded in the spike
findings. Only firmware-native effects ship; never build set-device-mode (00/04).
"""
from __future__ import annotations

import re
from typing import List

TRANSACTION_ID = 0x1F
BREATHING_TRANSACTION_ID = 0x3F
REPORT_LEN = 90

EFFECTS = ("static", "breathing", "spectrum", "wave", "reactive", "starlight")

_EXTENDED_MATRIX = 0x0F
_SET_EFFECT = 0x02
_SET_BRIGHTNESS = 0x04
_VARSTORE = 0x01
_BACKLIGHT_LED = 0x05

_WAVE_DIRECTION = 1  # left -> right
_REACTIVE_SPEED = 2
_STARLIGHT_SPEED = 2

_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def build_report(command_class: int, command_id: int, args: bytes, txid: int = TRANSACTION_ID) -> bytes:
    if len(args) > 80:
        raise ValueError("args longer than 80 bytes")
    report = bytearray(REPORT_LEN)
    report[1] = txid
    report[5] = len(args)
    report[6] = command_class
    report[7] = command_id
    report[8:8 + len(args)] = args
    crc = 0
    for b in report[2:88]:
        crc ^= b
    report[88] = crc
    return bytes(report)


def _rgb(color: str) -> bytes:
    if not isinstance(color, str) or not _COLOR.fullmatch(color):
        raise ValueError("colour must be #rrggbb: %r" % (color,))
    return bytes.fromhex(color[1:])


def _effect_args(effect: str, rgb: bytes) -> bytes:
    head = bytes([_VARSTORE, _BACKLIGHT_LED])
    if effect == "static":
        return head + bytes([0x01, 0x00, 0x00, 0x01]) + rgb
    if effect == "breathing":
        return head + bytes([0x02, 0x01, 0x00, 0x01]) + rgb
    if effect == "spectrum":
        return head + bytes([0x03, 0x00, 0x00, 0x00])
    if effect == "wave":
        return head + bytes([0x04, _WAVE_DIRECTION, 0x28, 0x00])
    if effect == "reactive":
        return head + bytes([0x05, 0x00, _REACTIVE_SPEED, 0x01]) + rgb
    if effect == "starlight":
        return head + bytes([0x07, 0x00, _STARLIGHT_SPEED, 0x01]) + rgb
    raise ValueError("unknown effect: %r" % (effect,))


def effect_reports(effect: str, color: str, brightness: int) -> List[bytes]:
    """The effect report followed by the brightness report."""
    if effect not in EFFECTS:
        raise ValueError("unknown effect: %r" % (effect,))
    rgb = _rgb(color)
    if not isinstance(brightness, int) or isinstance(brightness, bool) or not 0 <= brightness <= 100:
        raise ValueError("brightness must be an int 0-100: %r" % (brightness,))
    txid = BREATHING_TRANSACTION_ID if effect == "breathing" else TRANSACTION_ID
    return [
        build_report(_EXTENDED_MATRIX, _SET_EFFECT, _effect_args(effect, rgb), txid),
        build_report(_EXTENDED_MATRIX, _SET_BRIGHTNESS,
                     bytes([_VARSTORE, 0x00, round(brightness * 255 / 100)])),
    ]
