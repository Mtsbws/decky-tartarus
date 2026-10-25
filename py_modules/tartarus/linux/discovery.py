"""Finding the keypad's event and hidraw nodes in sysfs.

Event and hidraw numbers change on replug and reboot, so callers look them up
each time instead of caching them.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import List, Optional

VENDOR, PRODUCT = "1532", "0244"
HID_ID = "HID_ID=0003:00001532:00000244"
LIGHTING_INTERFACE = 2  # USB interface 2 (mouse protocol) takes the lighting reports
KEY_A = 30

_IFACE = re.compile(r"/\d+-[\d.]+:\d+\.(\d+)/")  # USB interface segment, e.g. 1-1.4.2:1.2
_NUMBER = re.compile(r"(\d+)$")


@dataclass
class TartarusNodes:
    event: List[str]
    hidraw: Optional[str]


def _read(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _numbered(paths: List[str]) -> List[str]:
    return sorted(paths, key=lambda p: int(_NUMBER.search(p).group(1)))


def _events(sys_root: str) -> List[str]:
    return _numbered(glob.glob(os.path.join(sys_root, "class", "input", "event*")))


def _is_tartarus(sys_event: str) -> bool:
    ids = os.path.join(sys_event, "device", "id")
    return (_read(os.path.join(ids, "vendor")), _read(os.path.join(ids, "product"))) == (VENDOR, PRODUCT)


def _has_key(sys_event: str, code: int) -> bool:
    # capabilities/key is hex words, most significant first, 64 bits each on the Deck.
    words = (_read(os.path.join(sys_event, "device", "capabilities", "key")) or "").split()
    word, bit = divmod(code, 64)
    if word >= len(words):
        return False
    try:
        return bool(int(words[-1 - word], 16) >> bit & 1)
    except ValueError:
        return False


def _interface(sys_path: str) -> Optional[int]:
    match = _IFACE.search(os.path.realpath(sys_path) + "/")
    return int(match.group(1)) if match else None


def find_tartarus(sys_root: str = "/sys") -> Optional[TartarusNodes]:
    event = ["/dev/input/" + os.path.basename(p) for p in _events(sys_root) if _is_tartarus(p)]
    if not event:
        return None
    hidraw = None
    for sys_hid in _numbered(glob.glob(os.path.join(sys_root, "class", "hidraw", "hidraw*"))):
        device = os.path.join(sys_hid, "device")
        uevent = _read(os.path.join(device, "uevent")) or ""
        if HID_ID in uevent.splitlines() and _interface(device) == LIGHTING_INTERFACE:
            hidraw = "/dev/" + os.path.basename(sys_hid)
            break
    return TartarusNodes(event=event, hidraw=hidraw)


def list_keyboards(sys_root: str = "/sys") -> List[str]:
    """Other keyboards (for recording a shortcut): not the keypad, not our virtual devices."""
    out = []
    for sys_event in _events(sys_root):
        if _is_tartarus(sys_event) or not _has_key(sys_event, KEY_A):
            continue
        name = _read(os.path.join(sys_event, "device", "name")) or ""
        if name.startswith("Decky Tartarus"):
            continue
        out.append("/dev/input/" + os.path.basename(sys_event))
    return out
