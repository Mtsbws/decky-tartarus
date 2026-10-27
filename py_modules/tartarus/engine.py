"""RemapEngine: turns raw keypad events into output events, with no I/O of its own."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, FrozenSet, List, Optional, Protocol, Sequence, Set

from .analog import DEFAULT_MM, KeyTracker, mm_to_depth
from .bindings import Binding
from .codes import WHEEL_DOWN, WHEEL_UP, code_for
from .config import Profile
from .devmap import ALL_CONTROLS, ANALOG_KEYS, DPAD_CARDINALS, FACTORY_CODES
from .dpad import resolve_dpad

MACRO_DELAY = 0.015  # seconds between a step's down and up, and between steps

HOLD_TYPES = ("key", "modifier", "mouse", "media", "combo")
_STEAM_KEYS = {"menu": ("Ctrl", "1"), "qam": ("Ctrl", "2")}
_WHEEL_DELTA = {WHEEL_UP: 1, WHEEL_DOWN: -1}
_ORDER = {control: i for i, control in enumerate(ALL_CONTROLS)}


class Emitter(Protocol):
    def key(self, code: int, down: bool) -> None: ...  # keyboard key or mouse button
    def wheel(self, delta: int) -> None: ...  # +1 up, -1 down
    def sync(self) -> None: ...
    def steam_action(self, action: str) -> None: ...  # "menu" | "qam"


class RemapEngine:
    def __init__(self, emitter: Emitter, profile: Profile,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 steam_mode: str = "api") -> None:
        self._out = emitter
        self._profile = profile
        self._sleep = sleep
        self.steam_mode = steam_mode
        self._passthrough = False
        self._counts: Dict[int, int] = {}  # output code -> how many triggers hold it
        self._held: Dict[str, List[int]] = {}  # control -> codes it holds down
        self._pressed: Set[str] = set()  # controls whose trigger is down
        self._dpad_pressed: Set[str] = set()  # physical cardinals down
        self._dpad_active: FrozenSet[str] = frozenset()
        self._macros: Dict[str, asyncio.Task] = {}
        self._trackers: Dict[str, KeyTracker] = {}
        self._build_trackers()

    # Record mode forwards raw events. Switching either way releases what is held,
    # so a key pressed in one mode can't stay down in the other.
    @property
    def passthrough(self) -> bool:
        return self._passthrough

    @passthrough.setter
    def passthrough(self, value: bool) -> None:
        if value != self._passthrough:
            self.release_all()
        self._passthrough = value

    def handle_key(self, code: int, value: int) -> None:
        if value == 2:  # kernel autorepeat
            return
        is_down = value == 1
        control = None if self._passthrough else FACTORY_CODES.get(code)
        if control is None:
            if is_down:
                self._down(code)
            else:
                self._up(code)
        elif control in DPAD_CARDINALS:
            self._dpad(control, is_down)
        else:
            self._trigger(control, is_down)
        self._out.sync()

    def handle_wheel(self, value: int) -> None:
        if value == 0:
            return
        if self._passthrough:
            self._out.wheel(value)
            self._out.sync()
            return
        control = "wheel_up" if value > 0 else "wheel_down"
        for _ in range(abs(value)):
            self._trigger(control, True)
            self._out.sync()
            self._trigger(control, False)
            self._out.sync()

    def handle_depth(self, depths: bytes) -> None:
        """One driver-mode depth report: byte i is ANALOG_KEYS[i]."""
        for control, depth in zip(ANALOG_KEYS, depths):
            tracker = self._trackers[control]
            if depth == tracker.last:
                continue
            for _slot, is_down in tracker.feed(depth):
                if not self._passthrough:  # still fed, so a key held into Record re-arms first
                    self._trigger(control, is_down)
        self._out.sync()

    def set_profile(self, profile: Profile) -> None:
        self.release_all()
        self._profile = profile
        self._build_trackers()

    def _build_trackers(self) -> None:
        """One tracker per analog key; a new one inherits the old one's depth and re-arm wait."""
        for control in ANALOG_KEYS:
            tracker = KeyTracker(mm_to_depth(DEFAULT_MM))
            old = self._trackers.get(control)
            if old is not None:
                tracker.last = old.last
                tracker.reset()
            self._trackers[control] = tracker

    def release_all(self) -> None:
        for task in self._macros.values():
            task.cancel()
        self._macros.clear()
        for code, count in self._counts.items():
            if count > 0:
                self._out.key(code, False)
        self._counts.clear()
        self._held.clear()
        self._pressed.clear()
        self._dpad_pressed.clear()
        self._dpad_active = frozenset()
        for tracker in self._trackers.values():
            tracker.reset()
        self._out.sync()

    # --- controls ---

    def _dpad(self, cardinal: str, is_down: bool) -> None:
        if is_down:
            self._dpad_pressed.add(cardinal)
        else:
            self._dpad_pressed.discard(cardinal)
        before = self._dpad_active
        after = resolve_dpad(frozenset(self._dpad_pressed), self._profile.dpad_mode)
        self._dpad_active = after
        for control in sorted(before - after, key=_ORDER.get):
            self._trigger(control, False)
        for control in sorted(after - before, key=_ORDER.get):
            self._trigger(control, True)

    def _trigger(self, control: str, is_down: bool) -> None:
        if not is_down:
            if control in self._pressed:
                self._pressed.discard(control)
                for code in reversed(self._held.pop(control, [])):
                    self._up(code)
            return
        if control in self._pressed:
            return
        self._pressed.add(control)
        b: Optional[Binding] = self._profile.bindings.get(control)
        if b is None:
            return
        if b.type in HOLD_TYPES:
            held = []
            for name in b.keys:
                code = code_for(name)
                if code in _WHEEL_DELTA:
                    self._out.wheel(_WHEEL_DELTA[code])
                else:
                    self._down(code)
                    held.append(code)
            self._held[control] = held
        elif b.type == "shortcut":
            self._tap(b.keys)
        elif b.type == "macro":
            running = self._macros.get(control)
            if running is None or running.done():
                self._macros[control] = asyncio.get_running_loop().create_task(self._macro(control, b.steps))
        elif b.type == "steam":
            if self.steam_mode == "api":
                self._out.steam_action(b.action)
            elif self.steam_mode == "keys":
                self._tap(_STEAM_KEYS[b.action])
        # "disable" does nothing

    async def _macro(self, control: str, steps: Sequence[Sequence[str]]) -> None:
        try:
            for i, step in enumerate(steps):
                if i:
                    await self._sleep(MACRO_DELAY)
                codes = self._press_names(step)
                self._out.sync()
                await self._sleep(MACRO_DELAY)
                self._release_codes(codes)
                self._out.sync()
        finally:
            if self._macros.get(control) is asyncio.current_task():
                del self._macros[control]

    # --- outputs ---

    def _tap(self, names: Sequence[str]) -> None:
        self._release_codes(self._press_names(names))

    def _press_names(self, names: Sequence[str]) -> List[int]:
        codes = []
        for name in names:
            code = code_for(name)
            if code in _WHEEL_DELTA:
                self._out.wheel(_WHEEL_DELTA[code])
            else:
                self._down(code)
                codes.append(code)
        return codes

    def _release_codes(self, codes: List[int]) -> None:
        for code in reversed(codes):
            self._up(code)

    def _down(self, code: int) -> None:
        count = self._counts.get(code, 0)
        self._counts[code] = count + 1
        if count == 0:
            self._out.key(code, True)

    def _up(self, code: int) -> None:
        count = self._counts.get(code, 0)
        if count == 0:
            return  # not held (e.g. released by release_all already)
        if count == 1:
            del self._counts[code]
            self._out.key(code, False)
        else:
            self._counts[code] = count - 1
