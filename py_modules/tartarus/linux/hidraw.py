"""Razer feature reports over hidraw (the keypad's USB interface 2)."""
from __future__ import annotations

import fcntl
import os
import time

from .ioctl import HIDIOCGFEATURE, HIDIOCSFEATURE


def send_feature(path: str, report: bytes) -> int:
    """Send one 90-byte report and return the status byte of the device's reply."""
    buf = b"\x00" + report  # report ID 0
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)
        time.sleep(0.001)
        resp = bytearray(len(buf))
        fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), resp)
        return resp[1]
    finally:
        os.close(fd)
