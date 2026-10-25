"""TartarusService: owns the devices, the engine and the settings file while the plugin runs."""
from __future__ import annotations

import asyncio
import errno
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional, Set

from .bindings import Binding, binding_label, binding_to_dict
from .config import DPAD_MODES, active_profile, load_config, save_config
from .devmap import ALL_CONTROLS
from .engine import RemapEngine
from .linux.discovery import TartarusNodes, find_tartarus
from .linux.evdev import EV_KEY, EV_REL, REL_WHEEL, InputDevice
from .linux.uinput import UinputEmitter

STEAM_ACTION_MODE = "api"  # S3: Navigation API with a toggle; "keys" goes nowhere under Moonlight

Emit = Callable[..., Awaitable[None]]


def _boottime() -> float:
    clock = getattr(time, "CLOCK_BOOTTIME", None)  # Linux only; the Mac test run has none
    return time.clock_gettime(clock) if clock is not None else time.monotonic()


class ResumeDetector:
    """CLOCK_BOOTTIME keeps counting through suspend and CLOCK_MONOTONIC doesn't,
    so a jump in their difference means the Deck slept."""

    THRESHOLD = 2.0

    def __init__(self) -> None:
        self._offset: Optional[float] = None

    def check(self, boottime: float, monotonic: float) -> bool:
        offset = boottime - monotonic
        slept = self._offset is not None and offset - self._offset > self.THRESHOLD
        self._offset = offset
        return slept


class TartarusService:
    POLL_INTERVAL = 2.0  # seconds between sysfs scans while the keypad is absent
    RESUME_INTERVAL = 5.0  # seconds between suspend checks

    def __init__(self, settings_path: Path, emit: Emit, log: Optional[logging.Logger] = None, *,
                 find: Callable[[], Optional[TartarusNodes]] = find_tartarus,
                 open_device: Callable[[str], Any] = InputDevice,
                 make_emitter: Callable[[Callable[[str], None]], Any] = UinputEmitter) -> None:
        self._path = Path(settings_path)
        self._emit = emit
        self._log = log or logging.getLogger("tartarus")
        self._find = find
        self._open_device = open_device
        self._make_emitter = make_emitter
        self._config = load_config(self._path)
        self._emitter: Any = None
        self._engine: Optional[RemapEngine] = None
        self._devices: List[Any] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._supervisor: Optional[asyncio.Task] = None
        self._resume = ResumeDetector()
        self._pending: Set[asyncio.Task] = set()

    # --- lifecycle ---

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._emitter = self._make_emitter(self._on_steam)
        self._engine = RemapEngine(self._emitter, self._profile(), steam_mode=STEAM_ACTION_MODE)
        self._supervisor = self._loop.create_task(self._supervise())

    async def stop(self) -> None:
        """Safe after a failed or missing start, and safe to call twice."""
        if self._supervisor is not None:
            self._supervisor.cancel()
            try:
                await self._supervisor
            except asyncio.CancelledError:
                pass
            except Exception:
                self._log.exception("supervisor failed")
            self._supervisor = None
        self._disconnect(notify=False)
        if self._emitter is not None:
            try:
                self._emitter.close()
            except OSError:
                self._log.exception("destroying the virtual devices failed")
            self._emitter = None
        self._engine = None

    async def _supervise(self) -> None:
        loop = asyncio.get_running_loop()
        next_poll = next_resume = loop.time()
        while True:
            now = loop.time()
            if now >= next_resume:
                next_resume = now + self.RESUME_INTERVAL
                if self._resume.check(_boottime(), time.monotonic()) and self._devices:
                    self._log.info("resumed from sleep; reconnecting the keypad")
                    self._disconnect()
                    next_poll = now
            if not self._devices and now >= next_poll:
                next_poll = now + self.POLL_INTERVAL
                nodes = self._find()
                if nodes is not None:
                    self._connect(nodes)
            await asyncio.sleep(min(self.POLL_INTERVAL, self.RESUME_INTERVAL) / 2)

    # --- devices ---

    def _connect(self, nodes: TartarusNodes) -> None:
        opened = []
        try:
            for path in nodes.event:
                dev = self._open_device(path)
                opened.append(dev)
                dev.grab()
        except OSError as e:
            for dev in opened:
                dev.close()  # closing the fd drops any grab we got
            if e.errno == errno.EBUSY:
                self._log.warning("keypad is grabbed by another process; retrying")
            else:
                self._log.warning("opening the keypad failed (%s); retrying", e)
            return
        assert self._loop is not None
        for dev in opened:
            self._loop.add_reader(dev.fd, self._on_readable, dev)
        self._devices = opened
        self._log.info("keypad connected: %s", ", ".join(nodes.event))
        self._notify()

    def _disconnect(self, notify: bool = True) -> None:
        if self._engine is not None:
            self._engine.release_all()
        if not self._devices:
            return
        for dev in self._devices:
            if self._loop is not None:
                self._loop.remove_reader(dev.fd)
            try:
                dev.ungrab()
            except OSError:
                pass  # already gone
            dev.close()
        self._devices = []
        self._log.info("keypad disconnected")
        if notify:
            self._notify()

    def _on_readable(self, dev: Any) -> None:
        try:
            events = dev.read_events()
        except OSError as e:
            self._log.info("keypad read failed (%s)", e)
            self._disconnect()
            return
        engine = self._engine
        if engine is None:
            return
        for type_, code, value in events:
            if type_ == EV_KEY:
                engine.handle_key(code, value)
            elif type_ == EV_REL and code == REL_WHEEL:
                engine.handle_wheel(value)

    def _on_steam(self, action: str) -> None:
        self._log.info("steam action %s", action)

    # --- events to the frontend ---

    def _notify(self) -> None:
        self._send("state_changed", self.state())

    def _send(self, event: str, *args: Any) -> None:
        if self._loop is None:
            return
        task = self._loop.create_task(self._emit_safely(event, *args))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _emit_safely(self, event: str, *args: Any) -> None:
        try:
            await self._emit(event, *args)
        except Exception:
            self._log.exception("emit %s failed", event)

    # --- settings ---

    def _profile(self):
        return active_profile(self._config)

    def state(self) -> dict:
        profile = self._profile()
        bindings = {}
        for control in ALL_CONTROLS:
            b = profile.bindings[control]
            bindings[control] = {"binding": binding_to_dict(b), "label": binding_label(b)}
        return {
            "connected": bool(self._devices),
            "dpad_mode": profile.dpad_mode,
            "steam_mode": STEAM_ACTION_MODE,
            "bindings": bindings,
        }

    def set_binding(self, control: str, b: Binding) -> None:
        if control not in ALL_CONTROLS:
            raise ValueError(f"unknown control {control!r}")
        self._profile().bindings[control] = b
        self._save()

    def set_dpad_mode(self, mode: str) -> None:
        if mode not in DPAD_MODES:
            raise ValueError(f"unknown d-pad mode {mode!r}")
        self._profile().dpad_mode = mode
        self._save()

    def _save(self) -> None:
        save_config(self._path, self._config)
        if self._engine is not None:
            self._engine.set_profile(self._profile())
