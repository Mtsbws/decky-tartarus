"""RemapEngine: turns raw keypad events into output events, with no I/O of its own."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, FrozenSet, List, Optional, Protocol, Sequence, Set, Tuple

from .actuation import DEFAULT_MM, KeyTracker, mm_to_depth
from .bindings import Binding
from .codes import WHEEL_DOWN, WHEEL_UP, code_for
from .config import Profile
from .devmap import ALL_CONTROLS, ACTUATION_KEYS, DPAD_CARDINALS, FACTORY_CODES
from .dpad import resolve_dpad
from .layers import B_SUFFIX, HYPERSHIFT, STANDARD

MACRO_DELAY = 0.015  # seconds between a step's down and up, and between steps
WHEEL_HOLD = 0.03  # seconds a wheel notch holds its binding, and the gap between notches; games poll once a frame

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
                 steam_mode: str = "api",
                 on_layer: Callable[[bool], None] = lambda active: None) -> None:
        self._out = emitter
        self._on_layer = on_layer
        self._profile = profile
        self._sleep = sleep
        self.steam_mode = steam_mode
        self._passthrough = False
        self._counts: Dict[int, int] = {}  # output code -> how many triggers hold it
        self._held: Dict[str, List[int]] = {}  # control -> codes it holds down
        self._pressed: Dict[str, str] = {}  # control whose trigger is down -> layer its press started in
        self._hypershift_down = False
        self._hypershift_control: Optional[str] = None
        self._dpad_pressed: Set[str] = set()  # physical cardinals down
        self._dpad_active: FrozenSet[str] = frozenset()
        self._macros: Dict[str, asyncio.Task] = {}
        self._wheel_pending: Dict[str, List[str]] = {}  # wheel control -> layers of the notches not yet played
        self._wheel_tasks: Dict[str, asyncio.Task] = {}
        self._trackers: Dict[str, KeyTracker] = {}
        self._key_layer: Dict[str, str] = {}  # depth key -> layer its current press belongs to
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
        self._wheel_pending.setdefault(control, []).extend([self._active_layer()] * abs(value))
        running = self._wheel_tasks.get(control)
        if running is None or running.done():
            self._wheel_tasks[control] = asyncio.get_running_loop().create_task(self._wheel(control))
            self._wheel_notch(control)  # the first notch goes down now, not on the next loop turn

    def _wheel_notch(self, control: str) -> None:
        self._trigger(control, True, self._wheel_pending[control].pop(0))
        self._out.sync()

    async def _wheel(self, control: str) -> None:
        """Plays a wheel control's notches one at a time, each held for WHEEL_HOLD in the layer it was turned in."""
        try:
            while True:
                await self._sleep(WHEEL_HOLD)
                self._trigger(control, False)
                self._out.sync()
                if not self._wheel_pending.get(control):
                    break
                await self._sleep(WHEEL_HOLD)
                self._wheel_notch(control)
        finally:
            if self._wheel_tasks.get(control) is asyncio.current_task():
                del self._wheel_tasks[control]
                self._wheel_pending.pop(control, None)

    def handle_depth(self, depths: bytes) -> None:
        """One driver-mode depth report: byte i is ACTUATION_KEYS[i]."""
        for control, depth in zip(ACTUATION_KEYS, depths):
            tracker = self._trackers[control]
            if depth == tracker.last:
                continue
            if tracker.idle:  # a press keeps the layer (and fire points) it started in
                layer = self._active_layer()
                tracker.fire_a, tracker.fire_b = self._points(control, layer)
                self._key_layer[control] = layer
            layer = self._key_layer.get(control, STANDARD)
            for slot, is_down in tracker.feed(depth):
                if not self._passthrough:  # still fed, so a key held into Record re-arms first
                    self._trigger(control if slot == "a" else control + B_SUFFIX, is_down, layer)
        self._out.sync()

    def set_profile(self, profile: Profile) -> None:
        self.release_all()
        self._profile = profile
        self._build_trackers()

    def _build_trackers(self) -> None:
        """One tracker per actuation key; a new one inherits the old one's depth and re-arm wait."""
        for control in ACTUATION_KEYS:
            secondary = self._profile.secondary.get(control)
            tracker = KeyTracker(mm_to_depth(self._profile.actuation.get(control, DEFAULT_MM)),
                                 mm_to_depth(secondary.actuation) if secondary is not None else None)
            old = self._trackers.get(control)
            if old is not None:
                tracker.last = old.last
                tracker.reset()
            self._trackers[control] = tracker

    def _points(self, control: str, layer: str) -> Tuple[int, Optional[int]]:
        """(fire_a, fire_b) depths for `control` in `layer`; a key the layer doesn't list uses the standard points."""
        profile = self._profile
        if layer == HYPERSHIFT and control in profile.hypershift.bindings:
            actuation, secondary = profile.hypershift.actuation, profile.hypershift.secondary
        else:
            actuation, secondary = profile.actuation, profile.secondary
        entry = secondary.get(control)
        return (mm_to_depth(actuation.get(control, DEFAULT_MM)),
                mm_to_depth(entry.actuation) if entry is not None else None)

    def release_all(self) -> None:
        for task in self._macros.values():
            task.cancel()
        self._macros.clear()
        for task in self._wheel_tasks.values():
            task.cancel()
        self._wheel_tasks.clear()
        self._wheel_pending.clear()
        for code, count in self._counts.items():
            if count > 0:
                self._out.key(code, False)
        self._counts.clear()
        self._held.clear()
        self._pressed.clear()
        self._key_layer.clear()
        was_active = self._hypershift_down
        self._hypershift_down = False
        self._hypershift_control = None
        self._dpad_pressed.clear()
        self._dpad_active = frozenset()
        for tracker in self._trackers.values():
            tracker.reset()
        self._out.sync()
        if was_active:
            self._on_layer(False)

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

    def _active_layer(self) -> str:
        return HYPERSHIFT if self._hypershift_down else STANDARD

    def _trigger(self, control: str, is_down: bool, layer: Optional[str] = None) -> None:
        if not is_down:
            if control in self._pressed:
                del self._pressed[control]
                if control == self._hypershift_control:
                    self._hypershift_down = False
                    self._hypershift_control = None
                    self._on_layer(False)
                for code in reversed(self._held.pop(control, [])):
                    self._up(code)
            return
        if control in self._pressed:
            return
        layer = layer or self._active_layer()
        self._pressed[control] = layer
        b = self._binding_for(control, layer)
        if b is None:
            return
        if b.type == "hypershift":
            self._hypershift_down = True
            self._hypershift_control = control
            self._on_layer(True)
        elif b.type in HOLD_TYPES:
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
            elif self.steam_mode == "keys" and b.action in _STEAM_KEYS:
                self._tap(_STEAM_KEYS[b.action])
        # "disable" does nothing

    def _binding_for(self, control: str, layer: str) -> Optional[Binding]:
        """The binding a press of `control` in `layer` runs; a control the layer doesn't list uses its standard one."""
        profile = self._profile
        is_secondary = control.endswith(B_SUFFIX)
        base = control[:-len(B_SUFFIX)] if is_secondary else control
        if layer == HYPERSHIFT and base in profile.hypershift.bindings:
            if not is_secondary:
                return profile.hypershift.bindings[base]
            entry = profile.hypershift.secondary.get(base)
            return entry.binding if entry is not None else None
        if is_secondary:
            secondary = profile.secondary.get(base)
            return secondary.binding if secondary is not None else None
        return profile.bindings.get(base)

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
