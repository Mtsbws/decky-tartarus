"""Razer feature reports for the keypad's lighting (pure; sending is linux/hidraw.py).

Byte values come from the OpenRazer source for 1532:0244, as recorded in the spike
findings. Only firmware-native effects ship. The device-mode report (00/04) is in
devmode.py.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

TRANSACTION_ID = 0x1F
BREATHING_TRANSACTION_ID = 0x3F
REPORT_LEN = 90

EFFECTS = ("static", "breathing", "spectrum", "wave", "reactive", "starlight")

_EXTENDED_MATRIX = 0x0F
_SET_EFFECT = 0x02
_SET_BRIGHTNESS = 0x04
_VARSTORE = 0x01
_BACKLIGHT_LED = 0x05
_PROFILE_LED = 0x0B  # one RGB LED to the firmware: R = top, G = middle, B = bottom

_WAVE_DIRECTION = 1  # left -> right
_REACTIVE_SPEED = 2
_STARLIGHT_SPEED = 2

_SET_FRAME = 0x03
_FRAME_SELECT = bytes([0x00, 0x00, 0x08, 0x00, 0x00, 0x00])
_FRAME_CELLS = 21

# Custom-frame cell of each lit control (Deck probe, 2026-10-28). The scroll wheel has one LED;
# the top button and the D-pad have none, so they are not here.
FRAME_INDEX: Dict[str, int] = {**{"k%02d" % n: n - 1 for n in range(1, 20)},
                               "wheel_up": 19, "wheel_down": 19, "wheel_click": 19, "k20": 20}
FAINT = "#262626"

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


def leds_report(leds: Tuple[bool, bool, bool]) -> bytes:
    """The profile-LED report as Synapse sends it: each LED fully on or off."""
    rgb = bytes(0xFF if on else 0x00 for on in leds)
    return build_report(_EXTENDED_MATRIX, _SET_EFFECT,
                        bytes([_VARSTORE, _PROFILE_LED, 0x01, 0x00, 0x01, 0x01]) + rgb)


def custom_frame_reports(colors: Sequence[str]) -> List[bytes]:
    """Select the custom frame (0F/02), then send its 21 cells (0F/03); no brightness change."""
    if len(colors) != _FRAME_CELLS:
        raise ValueError("a frame needs %d colours, got %d" % (_FRAME_CELLS, len(colors)))
    rgb = b"".join(_rgb(c) for c in colors)
    return [
        build_report(_EXTENDED_MATRIX, _SET_EFFECT, _FRAME_SELECT),
        build_report(_EXTENDED_MATRIX, _SET_FRAME, bytes([0, 0, 0, 0, _FRAME_CELLS - 1]) + rgb),
    ]


def hypershift_frame(lit: Iterable[str], color: str) -> List[str]:
    """The 21 cell colours: lit controls in `color`, the rest faint. Controls without an LED are ignored."""
    cells = [FAINT] * _FRAME_CELLS
    for control in lit:
        index = FRAME_INDEX.get(control)
        if index is not None:
            cells[index] = color
    return cells
