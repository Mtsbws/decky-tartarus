"""Virtual keyboard and mouse through /dev/uinput, and the engine's Emitter on top of them."""
from __future__ import annotations

import fcntl
import os
import struct
from typing import Callable, Iterable, Optional

from ..codes import KEYS
from .evdev import EV_KEY, EV_REL, EV_SYN, INPUT_EVENT, REL_WHEEL, REL_WHEEL_HI_RES, REL_X, REL_Y, SYN_REPORT
from .ioctl import UI_DEV_CREATE, UI_DEV_DESTROY, UI_DEV_SETUP, UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT

# BUS_USB with a pid.codes test ID: the combination tested through Moonlight in S2.
BUS_USB = 0x03
VENDOR, PRODUCT, VERSION = 0x1209, 0x0001, 1

BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, BTN_SIDE, BTN_EXTRA = 0x110, 0x111, 0x112, 0x113, 0x114
MOUSE_BUTTONS = (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, BTN_SIDE, BTN_EXTRA)
BTN_MISC, KEY_OK = 0x100, 0x160  # BTN_* codes live in [0x100, 0x160)


def is_button(code: int) -> bool:
    return BTN_MISC <= code < KEY_OK


class _Virtual:
    def __init__(self, name: str, keys: Iterable[int], rels: Iterable[int] = ()) -> None:
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for code in keys:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            rels = list(rels)
            if rels:
                fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
                for code in rels:
                    fcntl.ioctl(self.fd, UI_SET_RELBIT, code)
            setup = struct.pack("HHHH80sI", BUS_USB, VENDOR, PRODUCT, VERSION, name.encode()[:79], 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise
        self._dirty = False

    def emit(self, type_: int, code: int, value: int) -> None:
        os.write(self.fd, INPUT_EVENT.pack(0, 0, type_, code, value))
        self._dirty = True

    def syn(self) -> None:
        if self._dirty:
            os.write(self.fd, INPUT_EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0))
            self._dirty = False

    def close(self) -> None:
        if self.fd < 0:
            return
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
            self.fd = -1


class VirtualKeyboard(_Virtual):
    def __init__(self, name: str) -> None:
        # Every keyboard code in KEYS; no EV_REP, so the engine decides about repeats.
        super().__init__(name, sorted(c for c in KEYS.values() if c > 0 and not is_button(c)))


class VirtualMouse(_Virtual):
    def __init__(self, name: str) -> None:
        super().__init__(name, MOUSE_BUTTONS, (REL_X, REL_Y, REL_WHEEL, REL_WHEEL_HI_RES))


class UinputEmitter:
    """The engine's Emitter: buttons go to the mouse, every other key to the keyboard."""

    def __init__(self, on_steam: Callable[[str], None],
                 keyboard: Optional[_Virtual] = None, mouse: Optional[_Virtual] = None) -> None:
        self._on_steam = on_steam
        self.keyboard = keyboard if keyboard is not None else VirtualKeyboard("Decky Tartarus Keyboard")
        try:
            self.mouse = mouse if mouse is not None else VirtualMouse("Decky Tartarus Mouse")
        except OSError:
            self.keyboard.close()
            raise

    def key(self, code: int, down: bool) -> None:
        target = self.mouse if is_button(code) else self.keyboard
        target.emit(EV_KEY, code, 1 if down else 0)

    def wheel(self, delta: int) -> None:
        self.mouse.emit(EV_REL, REL_WHEEL, delta)

    def sync(self) -> None:
        self.keyboard.syn()
        self.mouse.syn()

    def steam_action(self, action: str) -> None:
        self._on_steam(action)

    def close(self) -> None:
        try:
            self.keyboard.close()
        finally:
            self.mouse.close()
