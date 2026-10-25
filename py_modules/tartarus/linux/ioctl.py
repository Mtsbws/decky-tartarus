"""ioctl request numbers (asm-generic/ioctl.h, linux/input.h, linux/uinput.h, linux/hidraw.h)."""
from __future__ import annotations

_NONE, _WRITE, _READ = 0, 1, 2


def IOC(dir: int, type_char: str, nr: int, size: int) -> int:
    return (dir << 30) | (size << 16) | (ord(type_char) << 8) | nr


def IO(type_char: str, nr: int) -> int:
    return IOC(_NONE, type_char, nr, 0)


def IOW(type_char: str, nr: int, size: int) -> int:
    return IOC(_WRITE, type_char, nr, size)


def IOR(type_char: str, nr: int, size: int) -> int:
    return IOC(_READ, type_char, nr, size)


def IOWR(type_char: str, nr: int, size: int) -> int:
    return IOC(_READ | _WRITE, type_char, nr, size)


EVIOCGRAB = IOW("E", 0x90, 4)

UI_DEV_CREATE = IO("U", 1)
UI_DEV_DESTROY = IO("U", 2)
UI_DEV_SETUP = IOW("U", 3, 92)  # struct uinput_setup
UI_SET_EVBIT = IOW("U", 100, 4)
UI_SET_KEYBIT = IOW("U", 101, 4)
UI_SET_RELBIT = IOW("U", 102, 4)


def EVIOCGNAME(n: int) -> int:
    return IOR("E", 0x06, n)


def EVIOCGBIT(ev: int, n: int) -> int:
    return IOR("E", 0x20 + ev, n)


def HIDIOCSFEATURE(n: int) -> int:
    return IOWR("H", 0x06, n)


def HIDIOCGFEATURE(n: int) -> int:
    return IOWR("H", 0x07, n)
