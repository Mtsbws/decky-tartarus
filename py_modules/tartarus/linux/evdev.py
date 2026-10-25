"""Reading and grabbing /dev/input/event* nodes."""
from __future__ import annotations

import fcntl
import os
import struct
from typing import List, Tuple

from .ioctl import EVIOCGBIT, EVIOCGNAME, EVIOCGRAB

INPUT_EVENT = struct.Struct("llHHi")  # struct input_event: timeval, type, code, value

EV_SYN, EV_KEY, EV_REL = 0, 1, 2
SYN_REPORT = 0
REL_X, REL_Y, REL_WHEEL, REL_WHEEL_HI_RES = 0, 1, 8, 11
KEY_BITS_BYTES = 96  # (KEY_MAX 0x2ff + 1) / 8


class InputDevice:
    def __init__(self, path: str) -> None:
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = bytearray(256)
            fcntl.ioctl(self.fd, EVIOCGNAME(len(buf)), buf)
            self.name = bytes(buf).split(b"\0", 1)[0].decode(errors="replace")
        except OSError:
            os.close(self.fd)
            raise

    def grab(self) -> None:
        fcntl.ioctl(self.fd, EVIOCGRAB, 1)

    def ungrab(self) -> None:
        fcntl.ioctl(self.fd, EVIOCGRAB, 0)

    def read_events(self) -> List[Tuple[int, int, int]]:
        """Every queued (type, code, value). Raises OSError(ENODEV) once the device is gone."""
        events = []
        while True:
            try:
                data = os.read(self.fd, INPUT_EVENT.size * 64)
            except BlockingIOError:
                break
            if not data:
                break
            for i in range(0, len(data) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
                _sec, _usec, type_, code, value = INPUT_EVENT.unpack_from(data, i)
                events.append((type_, code, value))
        return events

    def has_key(self, code: int) -> bool:
        buf = bytearray(KEY_BITS_BYTES)
        fcntl.ioctl(self.fd, EVIOCGBIT(EV_KEY, len(buf)), buf)
        return bool(buf[code // 8] >> (code % 8) & 1)

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
