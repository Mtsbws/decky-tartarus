"""Razer feature reports over hidraw (the keypad's USB interface 2), and input reports."""
from __future__ import annotations

import errno
import fcntl
import os
import time
from typing import Optional

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


class HidrawReader:
    """Non-blocking reader for one hidraw node's input reports (interface 1's depth)."""

    REPORT_MAX = 64

    def __init__(self, path: str):
        self.path = path
        self.fd: Optional[int] = os.open(path, os.O_RDONLY | os.O_NONBLOCK)

    def read_report(self) -> Optional[bytes]:
        """One report, or None when none is waiting. A 0-byte read means the node is gone."""
        if self.fd is None:
            raise OSError(errno.EBADF, "reader closed")
        try:
            data = os.read(self.fd, self.REPORT_MAX)
        except BlockingIOError:
            return None
        if not data:
            raise OSError(errno.ENODEV, "hidraw node gone")
        return data

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
