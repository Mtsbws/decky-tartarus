"""TartarusService: owns the devices, the engine and the settings file while the plugin runs."""
from __future__ import annotations

import asyncio
import errno
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional, Sequence, Set, Tuple

from .actuation import (DEFAULT_MM, MIN_GAP_MM, MM_MAX, MM_MIN, KeyTracker, mm_to_depth, parse_depth_report, tenths,
                        valid_mm)
from .bindings import Binding, binding_label, binding_to_dict
from .config import (DEFAULT_ID, DPAD_MODES, LED_ORDER, MAX_APP_ID, MAX_PROFILES, Game, Lighting, Profile, clean_name,
                     default_profile, find_profile, load_config, new_profile_id, next_leds, profile_for_app, save_config)
from .codes import name_for
from .devmap import ALL_CONTROLS, ACTUATION_KEYS, FACTORY_CODES, FACTORY_OUTPUT, SYSTEM_CODES
from .devmode import DRIVER_MODE, NORMAL_MODE, set_mode_report
from .engine import RemapEngine
from .lighting import EFFECTS, effect_reports, leds_report
from .linux.discovery import PRODUCT, VENDOR, TartarusNodes, find_tartarus, list_keyboards
from .linux.evdev import EV_KEY, EV_REL, REL_WHEEL, InputDevice
from .linux.hidraw import HidrawReader, send_feature
from .linux.uinput import UinputEmitter
from .record import RecordCapture

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
    RECORD_TIMEOUT = 10.0  # seconds before Record gives up with a null result

    def __init__(self, settings_path: Path, emit: Emit, log: Optional[logging.Logger] = None, *,
                 find: Callable[[], Optional[TartarusNodes]] = find_tartarus,
                 open_device: Callable[[str], Any] = InputDevice,
                 make_emitter: Callable[[Callable[[str], None]], Any] = UinputEmitter,
                 list_keyboards: Callable[[], List[str]] = list_keyboards,
                 send_feature: Callable[[str, bytes], int] = send_feature,
                 open_hidraw: Callable[[str], Any] = HidrawReader) -> None:
        self._path = Path(settings_path)
        self._emit = emit
        self._log = log or logging.getLogger("tartarus")
        self._find = find
        self._open_device = open_device
        self._make_emitter = make_emitter
        self._list_keyboards = list_keyboards
        self._send_feature = send_feature
        self._open_hidraw = open_hidraw
        self._config = load_config(self._path)
        try:
            self._lighting_reports()
        except ValueError as e:  # config.py doesn't know the effect names; a stored one may be stale
            self._log.warning("stored lighting is invalid (%s); using the default", e)
            self._config.lighting = Lighting()
        self._running: Optional[Tuple[int, str]] = None  # (app id, name); never persisted
        self._emitter: Any = None
        self._engine: Optional[RemapEngine] = None
        self._devices: List[Any] = []
        self._hidraw: Optional[str] = None
        self._depth_path: Optional[str] = None  # interface 1's hidraw node
        self._depth: Any = None  # its reader, while in driver mode
        self._driver_mode = False  # the keypad is in driver mode because we put it there
        self._actuation: Optional[str] = None  # "on" | "off" | "unavailable"; None while disconnected
        self._factory_key_logged = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._supervisor: Optional[asyncio.Task] = None
        self._resume = ResumeDetector()
        self._last_seen: Optional[TartarusNodes] = None  # nodes from the previous scan
        self._pending: Set[asyncio.Task] = set()
        self._capture: Optional[RecordCapture] = None
        self._record_devices: List[Any] = []
        # Record in driver mode: each key fires at the lightest point, and only the first key pressed counts.
        self._record_trackers = {control: KeyTracker(mm_to_depth(MM_MIN)) for control in ACTUATION_KEYS}
        self._record_key: Optional[str] = None
        self._record_timer: Optional[asyncio.TimerHandle] = None

    # --- lifecycle ---

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._emitter = self._make_emitter(self._on_steam)
        self._engine = RemapEngine(self._emitter, self._profile(), steam_mode=STEAM_ACTION_MODE)
        self._supervisor = self._loop.create_task(self._supervise())

    async def stop(self) -> None:
        """Safe after a failed or missing start, and safe to call twice.

        Never awaits: Decky closes the plugin's socket while _unload runs, and its listener then
        spins on EOF without yielding. A stop() suspended at an await would never resume, and
        Decky SIGKILLs the plugin 5 s later with the keypad still in our hands.
        """
        t0 = time.monotonic()
        if self._engine is not None:
            self._engine.release_all()
        self._leave_driver_mode()
        if self._supervisor is not None:
            if self._supervisor.done() and not self._supervisor.cancelled() and self._supervisor.exception():
                self._log.error("supervisor failed", exc_info=self._supervisor.exception())
            self._supervisor.cancel()
            self._supervisor = None
        self._record_stop()
        self._disconnect(notify=False)
        if self._emitter is not None:
            try:
                self._emitter.close()
            except OSError:
                self._log.exception("destroying the virtual devices failed")
            self._emitter = None
        self._engine = None
        for task in self._pending:
            task.cancel()
        self._pending.clear()
        self._log.info("stopped in %d ms", (time.monotonic() - t0) * 1000)

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
                # A replug creates the nodes one by one: connect once two scans agree.
                if nodes is not None and nodes == self._last_seen:
                    self._connect(nodes)
                self._last_seen = nodes
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
        self._hidraw = nodes.hidraw
        self._depth_path = nodes.depth
        self._factory_key_logged = False
        self._log.info("keypad connected: %s", ", ".join(nodes.event))
        if self._engine is not None:
            self._engine.set_profile(self._profile())
        self._enter_driver_mode()
        self._apply_lighting()
        self._notify()

    def _disconnect(self, notify: bool = True) -> None:
        if self._engine is not None:
            self._engine.release_all()
        if not self._devices:
            return
        self._leave_driver_mode()
        for dev in self._devices:
            if self._loop is not None:
                self._loop.remove_reader(dev.fd)
            try:
                dev.ungrab()
            except OSError:
                pass  # already gone
            dev.close()
        self._devices = []
        self._hidraw = None
        self._depth_path = None
        self._actuation = None
        self._last_seen = None
        self._log.info("keypad disconnected")
        if notify:
            self._notify()

    # --- driver mode ---

    def _enter_driver_mode(self) -> None:
        """Switch keys 01-20 to depth reports; on any failure the keypad stays in normal mode."""
        if not self._config.adjustable_actuation:
            self._actuation = "off"
            return
        self._actuation = "unavailable"
        if self._depth_path is None or self._hidraw is None:
            self._log.warning("adjustable actuation unavailable: no %s interface found",
                              "depth" if self._depth_path is None else "command")
            return
        if not self._send_command(set_mode_report(DRIVER_MODE), "driver mode"):
            self._log.warning("adjustable actuation unavailable: driver mode failed")
            return
        self._driver_mode = True
        try:
            reader = self._open_hidraw(self._depth_path)
        except OSError as e:
            self._log.warning("adjustable actuation unavailable: opening %s failed (%s)", self._depth_path, e)
            self._leave_driver_mode()
            self._actuation = "unavailable"
            return
        assert self._loop is not None
        self._depth = reader
        self._loop.add_reader(reader.fd, self._on_depth_readable)
        self._actuation = "on"
        self._log.info("driver mode: adjustable actuation on")

    def _leave_driver_mode(self) -> None:
        """Stop reading depth and put the keypad back in normal mode, if we changed it."""
        if self._depth is not None:
            if self._loop is not None:
                self._loop.remove_reader(self._depth.fd)
            self._depth.close()
            self._depth = None
        if self._driver_mode:
            self._driver_mode = False
            if self._send_command(set_mode_report(NORMAL_MODE), "normal mode", quiet=True):
                self._log.info("normal mode restored")

    def _on_depth_readable(self) -> None:
        reader, engine = self._depth, self._engine
        if reader is None:
            return
        for _ in range(64):  # bounded, so a flood can't starve the loop
            try:
                data = reader.read_report()
            except OSError as e:
                self._log.info("depth read failed (%s)", e)
                self._disconnect()
                return
            if data is None:
                return
            depths = parse_depth_report(data)
            if depths is not None:
                self._record_depth(depths)
                if engine is not None:
                    engine.handle_depth(depths)

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
                if code in SYSTEM_CODES:
                    continue
                if self._driver_mode and FACTORY_CODES.get(code) in ACTUATION_KEYS:
                    if not self._factory_key_logged:
                        self._factory_key_logged = True
                        self._log.info("dropping factory key %d from a depth key in driver mode", code)
                    continue
                if self._capture is not None and value != 2:
                    control = FACTORY_CODES.get(code)
                    if control is not None:
                        self._record_feed(FACTORY_OUTPUT[control], value == 1)
                engine.handle_key(code, value)
            elif type_ == EV_REL and code == REL_WHEEL:
                engine.handle_wheel(value)

    # --- lighting ---

    def _lighting_reports(self) -> List[bytes]:
        lighting = self._config.lighting
        return effect_reports(lighting.effect, lighting.color, lighting.brightness)

    def _send_command(self, report: bytes, what: str, quiet: bool = False) -> bool:
        """Send one feature report; failures are logged (at info if quiet) and return False, never raised."""
        level = logging.INFO if quiet else logging.WARNING
        if self._hidraw is None:
            self._log.log(level, "no lighting interface found; %s not applied", what)
            return False
        try:
            status = self._send_feature(self._hidraw, report)
        except OSError as e:
            self._log.log(level, "%s command failed on %s (%s)", what, self._hidraw, e)
            return False
        if status != 0x02:
            self._log.log(level, "%s command %02x/%02x returned status 0x%02x", what, report[6], report[7], status)
            return False
        return True

    def _apply_lighting(self) -> None:
        """Send the stored lighting, then the profile LEDs; failures are logged, never raised."""
        if not self._devices:
            return
        if all(self._send_command(report, "lighting") for report in self._lighting_reports()):
            lighting = self._config.lighting
            self._log.info("lighting applied: %s %s %d%% (status 0x02)",
                           lighting.effect, lighting.color, lighting.brightness)
        self._apply_leds()

    def _apply_leds(self) -> None:
        """Show the active profile's pattern on the three profile LEDs."""
        if not self._devices:
            return
        leds = self._profile().leds
        if self._send_command(leds_report(leds), "profile LED"):
            self._log.info("profile LEDs: %s", "".join("1" if on else "0" for on in leds))

    def _on_steam(self, action: str) -> None:
        self._send("steam_action", action)

    # --- record ---

    def record_start(self) -> None:
        """Capture the next key or shortcut, from the keypad (as its factory key) or any keyboard."""
        self._record_stop()
        self._capture = RecordCapture()
        for tracker in self._record_trackers.values():
            tracker.reset()
        if self._engine is not None:
            self._engine.passthrough = True
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        for path in self._list_keyboards():
            try:
                dev = self._open_device(path)  # read-only, not grabbed: it keeps typing as usual
            except OSError as e:
                self._log.info("can't read %s for recording (%s)", path, e)
                continue
            self._record_devices.append(dev)
            self._loop.add_reader(dev.fd, self._on_record_readable, dev)
        self._record_timer = self._loop.call_later(self.RECORD_TIMEOUT, self._record_timeout)

    def record_cancel(self) -> None:
        self._record_stop()

    def _record_depth(self, depths: bytes) -> None:
        """Always fed, so a key held when Record starts must re-arm before it counts."""
        for control, depth in zip(ACTUATION_KEYS, depths):
            for _slot, is_down in self._record_trackers[control].feed(depth):
                if self._capture is None or self._record_key not in (None, control):
                    continue
                self._record_key = control if is_down else None
                self._record_feed(FACTORY_OUTPUT[control], is_down)

    def _record_feed(self, name: str, down: bool) -> None:
        if self._capture is None:
            return
        b = self._capture.feed(name, down)
        if b is not None:
            self._record_stop()
            self._send("record_result", binding_to_dict(b))

    def _record_timeout(self) -> None:
        self._record_timer = None
        if self._capture is not None:
            self._record_stop()
            self._send("record_result", None)

    def _on_record_readable(self, dev: Any) -> None:
        try:
            events = dev.read_events()
        except OSError:
            self._record_close(dev)
            return
        for type_, code, value in events:
            if type_ == EV_KEY and value != 2:
                name = name_for(code)
                if name is not None:
                    self._record_feed(name, value == 1)

    def _record_close(self, dev: Any) -> None:
        if dev in self._record_devices:
            self._record_devices.remove(dev)
            if self._loop is not None:
                self._loop.remove_reader(dev.fd)
            dev.close()

    def _record_stop(self) -> None:
        self._record_key = None
        if self._record_timer is not None:
            self._record_timer.cancel()
            self._record_timer = None
        for dev in list(self._record_devices):
            self._record_close(dev)
        if self._capture is not None:
            self._capture = None
            if self._engine is not None:
                self._engine.passthrough = False

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

    def _profile(self) -> Profile:
        return profile_for_app(self._config, self._running[0] if self._running else None)

    def _switch(self, before_id: str) -> None:
        """Follow a change of the derived active profile: drop a Record capture, then swap the engine."""
        active = self._profile()
        if active.id == before_id:
            return
        if self._capture is not None:
            self._record_stop()
            self._send("record_result", None)
        if self._engine is not None:
            self._engine.set_profile(active)
        self._apply_leds()

    def set_running_app(self, app_id: Optional[int], name: Optional[str]) -> None:
        """The frontend reports the foreground game; None or 0 means none."""
        if app_id is not None and (isinstance(app_id, bool) or not isinstance(app_id, int)
                                   or not 0 <= app_id <= MAX_APP_ID):
            raise ValueError(f"invalid app id {app_id!r}")
        if not app_id:
            running = None
        else:
            clean = name.strip() if isinstance(name, str) else ""
            running = (app_id, clean or str(app_id))
        if running == self._running:
            return
        before_id = self._profile().id
        self._running = running
        if running is not None:
            game = self._config.games.get(str(running[0]))
            # A blank name must not overwrite a good stored one with the bare id.
            if game is not None and running[1] != str(running[0]) and game.name != running[1]:
                self._config.games[str(running[0])] = Game(name=running[1], profile=game.profile)
                try:
                    self._save()
                except OSError as e:
                    # A failed name refresh must never block the profile switch.
                    self._log.warning("saving the game name failed (%s); switching anyway", e)
        self._switch(before_id)
        self._notify()

    def _device_name(self) -> Optional[str]:
        if not self._devices:
            return None
        # The kernel joins vendor and product strings: "Razer Razer Tartarus Pro".
        words = self._devices[0].name.split()
        return " ".join(w for i, w in enumerate(words) if i == 0 or w != words[i - 1]) or None

    def state(self) -> dict:
        lighting = self._config.lighting
        profiles = []
        for p in self._config.profiles:
            bindings = {}
            for control in ALL_CONTROLS:
                b = p.bindings[control]
                bindings[control] = {"binding": binding_to_dict(b), "label": binding_label(b),
                                     "factory": FACTORY_OUTPUT[control]}
            games = sorted((g.name for g in self._config.games.values() if g.profile == p.id), key=str.lower)
            profiles.append({"id": p.id, "name": p.name, "is_default": p is self._config.profiles[0],
                             "games": games, "dpad_mode": p.dpad_mode, "leds": list(p.leds),
                             "actuation": dict(p.actuation), "bindings": bindings})
        return {
            "connected": bool(self._devices),
            "device": self._device_name(),
            "device_id": f"{VENDOR}:{PRODUCT}" if self._devices else None,
            "steam_mode": STEAM_ACTION_MODE,
            "lighting": {"effect": lighting.effect, "color": lighting.color, "brightness": lighting.brightness},
            "actuation": {"enabled": self._config.adjustable_actuation, "status": self._actuation, "default_mm": DEFAULT_MM,
                       "min_mm": MM_MIN, "max_mm": MM_MAX, "min_gap_mm": MIN_GAP_MM},
            "effects": list(EFFECTS),
            "active_profile": self._profile().id,
            "running_app": {"app_id": self._running[0], "name": self._running[1]} if self._running else None,
            "max_profiles": MAX_PROFILES,
            "profiles": profiles,
            "led_patterns": [list(leds) for leds in LED_ORDER],
        }

    def _edit_target(self, profile_id: str) -> Profile:
        profile = find_profile(self._config, profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id!r}")
        return profile

    def _edited(self, profile: Profile) -> None:
        self._save()
        if self._engine is not None and profile.id == self._profile().id:
            self._engine.set_profile(profile)

    def set_binding(self, profile_id: str, control: str, b: Binding) -> None:
        profile = self._edit_target(profile_id)
        if control not in ALL_CONTROLS:
            raise ValueError(f"unknown control {control!r}")
        profile.bindings[control] = b
        self._edited(profile)

    def set_dpad_mode(self, profile_id: str, mode: str) -> None:
        profile = self._edit_target(profile_id)
        if mode not in DPAD_MODES:
            raise ValueError(f"unknown d-pad mode {mode!r}")
        profile.dpad_mode = mode
        self._edited(profile)

    def set_actuation(self, profile_id: str, control: str, mm: float) -> None:
        profile = self._edit_target(profile_id)
        if control not in ACTUATION_KEYS:
            raise ValueError(f"{control!r} has no adjustable actuation")
        self._apply_actuation(profile, (control,), mm)

    def set_all_actuation(self, profile_id: str, mm: float) -> None:
        self._apply_actuation(self._edit_target(profile_id), ACTUATION_KEYS, mm)

    def _apply_actuation(self, profile: Profile, controls: Sequence[str], mm: float) -> None:
        if not valid_mm(mm):
            raise ValueError(f"actuation must be {MM_MIN}-{MM_MAX} mm in 0.1 mm steps")
        for control in controls:
            if tenths(mm) == tenths(DEFAULT_MM):
                profile.actuation.pop(control, None)
            else:
                profile.actuation[control] = round(mm, 1)
        self._edited(profile)

    def set_leds(self, profile_id: str, leds: Sequence[bool]) -> None:
        profile = self._edit_target(profile_id)
        if profile_id == DEFAULT_ID:
            raise ValueError("Default keeps all LEDs off")
        # Real bools only: (1, 0, 0) == (True, False, False), so ints would slip past the LED_ORDER check.
        if not isinstance(leds, (list, tuple)) or len(leds) != 3 or not all(isinstance(v, bool) for v in leds):
            raise ValueError(f"LED pattern must be three booleans: {leds!r}")
        pattern = tuple(leds)
        if pattern not in LED_ORDER:
            raise ValueError(f"not a lit LED pattern: {list(pattern)}")
        if any(p.leds == pattern for p in self._config.profiles if p is not profile):
            raise ValueError("another profile uses that LED pattern")
        profile.leds = pattern
        self._save()
        if profile.id == self._profile().id:
            self._apply_leds()
        self._notify()

    def _mutate(self, change: Callable[[], None]) -> None:
        """Apply an already-validated config change, persist it, follow any change of the active profile."""
        before_id = self._profile().id
        change()
        self._save()
        self._switch(before_id)
        self._notify()

    def assign_running_game(self, profile_id: str) -> None:
        self._edit_target(profile_id)
        if self._running is None:
            return
        app_id, name = str(self._running[0]), self._running[1]

        def change() -> None:
            if profile_id == DEFAULT_ID:
                self._config.games.pop(app_id, None)
            else:
                self._config.games[app_id] = Game(name=name, profile=profile_id)

        self._mutate(change)

    def create_profile(self, name: str, copy_from_id: str) -> str:
        source = self._edit_target(copy_from_id)
        if len(self._config.profiles) >= MAX_PROFILES:
            raise ValueError(f"At most {MAX_PROFILES} profiles")
        name = clean_name(self._config, name)
        profile = Profile(id=new_profile_id(self._config), name=name, dpad_mode=source.dpad_mode,
                          bindings=dict(source.bindings), leds=next_leds(self._config),
                          actuation=dict(source.actuation), secondary=dict(source.secondary))
        self._mutate(lambda: self._config.profiles.append(profile))
        return profile.id

    def rename_profile(self, profile_id: str, name: str) -> None:
        profile = self._edit_target(profile_id)
        name = clean_name(self._config, name, exclude_id=profile_id)
        self._mutate(lambda: setattr(profile, "name", name))

    def delete_profile(self, profile_id: str) -> None:
        profile = self._edit_target(profile_id)
        if profile_id == DEFAULT_ID:
            raise ValueError("Default can't be deleted")

        def change() -> None:
            self._config.profiles.remove(profile)
            for key in [k for k, g in self._config.games.items() if g.profile == profile_id]:
                del self._config.games[key]

        self._mutate(change)

    def set_lighting(self, effect: str, color: str, brightness: int) -> None:
        effect_reports(effect, color, brightness)  # raises ValueError before anything changes
        self._config.lighting = Lighting(effect=effect, color=color, brightness=brightness)
        save_config(self._path, self._config)
        self._apply_lighting()

    def set_adjustable_actuation(self, enabled: bool) -> None:
        """The panel's Adjustable actuation switch: release what is held, then change the mode at once."""
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        self._config.adjustable_actuation = enabled
        save_config(self._path, self._config)
        if self._devices:
            if self._engine is not None:
                self._engine.release_all()
            self._leave_driver_mode()
            self._enter_driver_mode()
        self._notify()

    def _save(self) -> None:
        """Persist only. Never touches the engine: set_profile releases keys the user may be holding."""
        save_config(self._path, self._config)
