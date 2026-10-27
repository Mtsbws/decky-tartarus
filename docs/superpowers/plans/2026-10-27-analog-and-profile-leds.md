# Analog Keys and Profile LEDs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Driver mode whenever the plugin has the keypad, with per-key actuation (1.5-3.6 mm), a secondary function per key, and the profile LEDs showing the active profile.

**Architecture:** A new pure module `analog.py` turns depth reports into per-key A/B down/up events (`KeyTracker`). The engine owns one tracker per key 01-20, built from the profile, and routes A to control `kNN` and B to control `kNN.b`, so both reuse the existing held/release bookkeeping. The service manages the device mode (driver on connect, normal on disconnect and stop), reads interface 1's hidraw node with `loop.add_reader`, drops system keys, and sends the profile LEDs. Settings stay schema 2 with optional fields.

**Tech Stack:** Python 3 stdlib (`unittest`, `asyncio`), TypeScript + React with `@decky/ui` / `@decky/api` (pnpm, rollup).

**Spec:** `docs/superpowers/specs/2026-10-27-analog-and-profile-leds-design.md`. Evidence: `docs/superpowers/synapse-capture-findings.md`. Read both before any task.

## Milestones

| Milestone | Tasks | Done when |
|---|---|---|
| M1 Profile LEDs (normal mode) | 1-2 | Suite green; Deck check M1. **Stop.** |
| M2 Driver mode lifecycle, system keys, unload fix | 3-9 | Suite green; `pnpm build` clean; Deck check M2. **Stop.** |
| M3 Actuation per key + recording from depth | 10-12 | Suite green; Deck check M3. **Stop.** |
| M4 Secondary function | 13-15 | Suite green; Deck check M4. **Stop.** |
| M5 Editor UI | 16-18 | `pnpm build` clean; Deck check M5; final whole-branch review (Opus). **Stop.** |

One change from the suggested order: depth → single-function presses at the default 1.5 mm lands in M2, not M3. Without it, M2 would leave keys 01-20 dead between milestones. M3 adds the per-key settings on top.

At each stop: commit, tell the user to `/clear`, and start the next milestone from this file with `/model sonnet`.

Tests: `python3 -m unittest discover -s tests -t .` from the repo root (144 tests green at the start). Frontend: `pnpm build` with no type errors. Deploy: `scripts/deploy.sh <host>`, then the user runs the printed `sudo cp` (Decky live-reloads the plugin on the copy, which is also an unload).

**Hardware checks.** Claude has no sudo on the Deck. Every Deck check is a checklist the user runs. Claude asks before each new kind of send and waits for the result. For checks outside the plugin, the tools are `scripts/deck-probe.py` (`getmode`, `setmode 03|00`, `led R G B`, `read N`; stop the plugin first) and `scripts/read-depth.py` (read-only). Claude can read the plugin log over ssh without sudo: `ssh <host> 'tail -n 200 ~/homebrew/logs/decky-tartarus/*.log'`. If that path is wrong, ask the user where it is.

## Global Constraints

- Stdlib-only Python, root backend, atomic settings writes via `save_config`, nothing written outside the settings folder.
- Commands the plugin may send (all to interface 2, status `0x02` = OK): lighting as today; get mode `0x00`/`0x84` args `00 00`; set mode `0x00`/`0x04` args `03 00` (driver) or `00 00` (normal); profile LEDs `0x0F`/`0x02` args `01 0B 01 00 01 01 R G B` with `FF` on, `00` off (R top, G middle, B bottom). Nothing else.
- Depth reports: interface 1 hidraw, report ID `0x06`, byte n (1-19) = key n, byte 20 = k20, bytes 21-23 ignored.
- mm → depth: piecewise linear through (1.5, 16), (2.5, 120), (3.6, 251), rounded. Hysteresis 8: down at `depth >= fire`, up at `depth < fire - 8`.
- Actuation: keys k01-k20 only, 1.5-3.6 mm in 0.1 mm steps, default 1.5 mm. B at least 0.5 mm deeper than A.
- Secondary semantics: A down past A; A up then B down past B; B up below B's release; A silent until below A's release (re-arm); a jump straight past B sends only B; B re-fires from between A and B without re-arm.
- Dropped in both modes: `KEY_POWER` (116), `KEY_SLEEP` (142), `KEY_WAKEUP` (143). In driver mode, also the factory codes of k01-k20 (logged once per connection). Other unknown codes pass through as today.
- Analog switch: global, on by default, stored in the settings file. Driver-mode failure → normal mode, logged, panel says "Analog keys unavailable".
- `stop()` under 1 s; releases held outputs, then sends normal mode, before anything that can block.
- No periodic `00/84` polling. No InputPlumber code copied (GPL).
- Settings stay `SCHEMA_VERSION = 2`: new fields are optional, so a v2 file loads unchanged. A version bump would make an older plugin treat the file as corrupt and move it aside. No backup is needed since nothing is migrated.
- Bad stored values (actuation off range/step, secondary B not 0.5 mm deeper, unparsable B binding, non-analog control) are dropped per key with a warning.
- Every active-profile change still goes through `engine.set_profile`.

## Review Focus

1. **A key is held through a profile switch, a Record start or the analog toggle in driver mode.** `release_all` releases the output. The tracker must not re-fire on the next report while the key is still down: it waits until the key drops below its release point. Test in Task 7 (`test_release_all_blocks_until_rearm`).
2. **The keypad disappears mid-session (hub drop) in driver mode.** The depth reader errors or reports EOF. That must disconnect cleanly like an evdev read failure. The normal-mode send to the gone device fails quietly, and the reconnect re-enters driver mode. Test in Task 8 (`test_depth_read_error_disconnects_and_reconnects_in_driver_mode`).
3. **Driver mode works but opening the depth node fails.** Keys 01-20 would be dead. The service must send normal mode back and fall back. Test in Task 8 (`test_depth_open_failure_restores_normal_mode`).
4. **The user sets an LED pattern with ints (`[1, 0, 0]`) from the frontend.** `(1, 0, 0) == (True, False, False)` in Python, so a bare `in LED_ORDER` check passes and stores ints. Test in Task 2.
5. **Slider values arrive as floats like `2.6000000000000005`.** Step and gap checks compare tenths (`round(mm * 10)`), never raw floats, and the stored value is `round(mm, 1)`. Tests in Tasks 10 and 15.

---

## M1: Profile LEDs (normal mode)

### Task 1: LED report, sent on connect, switch, resume and lighting change

**Files:**
- Modify: `py_modules/tartarus/lighting.py`
- Modify: `py_modules/tartarus/service.py`
- Test: `tests/test_lighting.py`, Create `tests/test_service_leds.py`

**Interfaces:**
- Produces: `lighting.leds_report(leds: Tuple[bool, bool, bool]) -> bytes`. In `TartarusService`: `_send_command(report: bytes, what: str) -> bool` and `_apply_leds() -> None`.

- [ ] **Step 1: Write the failing tests**
  - `tests/test_lighting.py::test_leds_report`: `r = leds_report((True, False, True))` → `r[5:17] == bytes([0x09, 0x0F, 0x02, 0x01, 0x0B, 0x01, 0x00, 0x01, 0x01, 0xFF, 0x00, 0xFF])`, `r[1] == 0x1F`, `len(r) == 90`, and `r[88]` is the XOR of `r[2:88]`. `leds_report((False, False, False))[14:17] == b"\x00\x00\x00"`.
  - `tests/test_service_leds.py` (Rig + `FakeSender` from the existing tests; settings file with profile `p2` leds `(True, False, False)` and game `"5"` → `p2`):
    - `test_connect_sends_leds_after_lighting`: on connect the sent reports are `effect_reports(...) + [leds_report(NO_LEDS)]`, in that order.
    - `test_switch_sends_active_leds`: `set_running_app(5, "X")` → last sent is `leds_report((True, False, False))`. `set_running_app(None, None)` → `leds_report(NO_LEDS)`. Reporting app 5 twice sends nothing the second time.
    - `test_set_lighting_resends_leds`: after `set_lighting(...)` the last sent report is the active profile's LED report.
    - `test_resume_resends_leds`: as `test_service.py::test_resume_reconnects`. After the reconnect, the LED report was sent twice in total.
    - `test_led_failure_is_logged_not_raised`: sender status `0x05` → `assertLogs("tartarus", "WARNING")`, and the switch still happened (`state()["active_profile"] == "p2"`).
    - `test_no_send_while_disconnected`: switching with no nodes sends nothing.

- [ ] **Step 2: Run them, expect FAIL** (`ImportError: leds_report`)

- [ ] **Step 3: Implement**
  - `leds_report` in `lighting.py`: `build_report(0x0F, 0x02, bytes([0x01, 0x0B, 0x01, 0x00, 0x01, 0x01, R, G, B]))`, with `0xFF` for True and `0x00` for False. Add a `_PROFILE_LED = 0x0B` constant.
  - In the service, factor the send/status/log out of `_apply_lighting` into `_send_command(report, what) -> bool`. It returns False and warns on no hidraw, OSError or status ≠ `0x02`, and never raises.
  - `_apply_leds()` sends `leds_report(self._profile().leds)` when connected. Call it at the end of `_apply_lighting()`, whether or not lighting succeeded (this covers connect, resume and `set_lighting`), and in `_switch` after `engine.set_profile`.

- [ ] **Step 4: Run the full suite, expect PASS.** Tests in `tests/test_service_lighting.py` that compare the whole sent list now also see the LED report at the end. Update them to expect it; don't weaken them to a prefix check.

- [ ] **Step 5: Commit** `feat: send profile LEDs on connect, switch and lighting change`

### Task 2: Choose a profile's LED pattern

**Files:**
- Modify: `py_modules/tartarus/service.py`, `main.py`, `src/api.ts`
- Test: `tests/test_service_leds.py`, `tests/test_service.py` (`test_state_shape`, plugin callables)

**Interfaces:**
- Produces: `TartarusService.set_leds(profile_id: str, leds: Sequence[bool]) -> None`; callable `set_leds(profile_id, leds: list) -> state`. State: `profiles[i]["leds"]: [bool, bool, bool]` and top-level `"led_patterns": [[bool]*3, ...]` (`LED_ORDER`, in order). TS: `ProfileState.leds: [boolean, boolean, boolean]`, `State.led_patterns: boolean[][]`, `setLeds = callable<[profileId: string, leds: boolean[]], State>("set_leds")`.

- [ ] **Step 1: Write the failing tests**
  - `test_set_leds_persists_and_sends_when_active`: `set_leds("p2", [False, True, True])` → reloaded file has `p2.leds == (False, True, True)`. While p2 is active, the last sent report is its LED report. While it isn't, nothing is sent.
  - `test_set_leds_rejects`: each raises `ValueError` and changes nothing: Default; a pattern used by another profile; `[False, False, False]`; `[1, 0, 0]`; `[True, False]`; unknown profile id.
  - `test_state_shape`: add `leds` per profile and `led_patterns`.
  - Plugin callable test: `set_leds` returns state.

- [ ] **Step 2: Run them, expect FAIL**

- [ ] **Step 3: Implement** `set_leds`. Require a list or tuple of exactly 3 `bool` instances (check `isinstance(v, bool)`, never compare ints). Require a pattern in `LED_ORDER`, unused by any other profile, and not Default. Save via `_save()`, then `_apply_leds()` if the profile is active. Add the callable in `main.py` and the types and callable in `api.ts` (no UI yet; that is Task 18).

- [ ] **Step 4: Full suite PASS; `pnpm build` clean**

- [ ] **Step 5: Commit** `feat: pick a profile's LED pattern`

### Deck check M1 (user runs; no new kind of send: the LED command was already checked in normal mode)

Deploy. With two games assigned to two profiles: start each game → the LEDs show its pattern; back to the library → all off. Change the lighting effect and brightness in the panel → LEDs stay correct. Suspend and resume → LEDs correct. Unplug/replug → LEDs correct. Report pass/fail per line.

---

## M2: Driver mode lifecycle, system keys, unload fix

### Task 3: Find and fix the slow unload

**Files:**
- Modify: `py_modules/tartarus/service.py`, `main.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Produces: `stop()` unchanged in signature. Order: `engine.release_all()` → `_leave_driver_mode()` (a no-op stub until Task 8) → the rest. Every step is bounded. `Plugin._uninstall` calls `service.stop()`.

Use superpowers:systematic-debugging. The cause is unknown. Candidates: the supervisor await, pending `_emit_safely` tasks, a pending macro, uinput destroy, ungrab, the frontend.

- [ ] **Step 1: Instrument.** Log `stop: <step> done in N ms` at info level after each step of `stop()`, and `unload done in N ms` in `Plugin._unload`. Deploy (the copy triggers an unload of the old version, then a load). Ask the user to deploy once more, so the instrumented version gets unloaded. Read the log. Look at the step timings and whether Decky still says "still alive 5 seconds after stop request". If `_unload` finishes fast and Decky still kills the process, the cause is outside `stop()` (e.g. a pending task or the `_main` task). Look at how Decky's sandboxed plugin process exits, in the installed loader on the Deck (`~/homebrew/services/`, read-only).

- [ ] **Step 2: Write a failing test for the found cause** (for example `test_stop_cancels_pending_emits` if pending emit tasks keep the loop alive: a slow `emit` that sleeps 10 s, then `stop()` finishes under 1 s and the task is cancelled). Also add `test_stop_releases_before_anything_else`: hold k01 (Esc bound), make the supervisor cancel hang (patch `_supervisor` with a task that ignores cancellation for 0.2 s). The Esc release must be in `emitter.out` before the supervisor await returns.

- [ ] **Step 3: Fix.** Reorder `stop()` as in Interfaces. Bound the supervisor await with `asyncio.wait_for(..., 0.5)`. Cancel and drop `self._pending` tasks. Add whatever the found cause needs. `_uninstall` calls `self.service.stop()` when the service exists (stop is idempotent).

- [ ] **Step 4: Full suite PASS. Deploy twice more and read the log: no "still alive", and `stop` under 1 s.** Remove noisy per-step logs, keeping one `stopped in N ms` line.

- [ ] **Step 5: Commit** `fix: stop finishes inside Decky's unload limit`

### Task 4: Drop system keys from the keypad

**Files:**
- Modify: `py_modules/tartarus/devmap.py`, `py_modules/tartarus/service.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Produces: `devmap.SYSTEM_CODES = frozenset({116, 142, 143})  # KEY_POWER, KEY_SLEEP, KEY_WAKEUP`; `devmap.ANALOG_KEYS = tuple(f"k{i:02d}" for i in range(1, 21))`.

- [ ] **Step 1: Failing test** `test_system_keys_dropped`: connect, push `(EV_KEY, 142, 1), (EV_KEY, 142, 0), (EV_KEY, 116, 1), (EV_KEY, 143, 1)` → `emitter.out` has none of them. An unknown code (e.g. 183, F13) still passes through. Also during Record: a system key is not fed to the capture.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** In `_on_readable`, `continue` on `EV_KEY` codes in `SYSTEM_CODES` before the capture and the engine.
- [ ] **Step 4: Full suite PASS**
- [ ] **Step 5: Commit** `fix: never pass power and sleep keys from the keypad`

### Task 5: Device mode report, depth node, hidraw reader

**Files:**
- Create: `py_modules/tartarus/devmode.py`
- Modify: `py_modules/tartarus/lighting.py` (docstring: drop "never build set-device-mode", point to `devmode.py`), `py_modules/tartarus/linux/discovery.py`, `py_modules/tartarus/linux/hidraw.py`
- Test: Create `tests/test_devmode.py`; `tests/test_discovery.py`

**Interfaces:**
- Produces:
  - `devmode.DRIVER_MODE = 0x03`, `devmode.NORMAL_MODE = 0x00`, `devmode.set_mode_report(mode: int) -> bytes` (`ValueError` for any other mode).
  - `TartarusNodes(event: List[str], hidraw: Optional[str], depth: Optional[str] = None)`: `depth` is the interface 1 hidraw node. `DEPTH_INTERFACE = 1` next to `LIGHTING_INTERFACE`.
  - `hidraw.HidrawReader(path: str)`: opens `O_RDONLY | O_NONBLOCK`; `.fd`; `.read_report() -> Optional[bytes]` (one report, `None` on `BlockingIOError`, raises `OSError` on others, and raises `OSError(ENODEV)` on a 0-byte read); `.close()` is idempotent.

- [ ] **Step 1: Failing tests**
  - `test_set_mode_report`: `set_mode_report(DRIVER_MODE)[5:10] == bytes([0x02, 0x00, 0x04, 0x03, 0x00])`, normal → `... 0x00, 0x00`, CRC as in `test_leds_report`. `set_mode_report(0x02)` raises.
  - `tests/test_discovery.py`: extend the fake sysfs with a hidraw node on interface 1 (`...:1.1/`) → `nodes.depth` is it, `nodes.hidraw` is still interface 2. Without one → `depth is None`.
  - `HidrawReader` on a pipe: written bytes come back from `read_report()`. Empty pipe → `None`. Closed writer → `OSError`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** as in Interfaces.
- [ ] **Step 4: Full suite PASS**
- [ ] **Step 5: Commit** `feat: device mode report and interface 1 reader`

### Task 6: Depth mapping and the single-function tracker

**Files:**
- Create: `py_modules/tartarus/analog.py`
- Test: Create `tests/test_analog.py`

**Interfaces:**
- Produces:
  - `MM_MIN = 1.5`, `MM_MAX = 3.6`, `DEFAULT_MM = 1.5`, `MIN_GAP_MM = 0.5`, `HYSTERESIS = 8`, `DEPTH_POINTS = ((1.5, 16), (2.5, 120), (3.6, 251))` (the one table to refine).
  - `tenths(mm: float) -> int` (`round(mm * 10)`).
  - `valid_mm(mm) -> bool`: an `int` or `float` (not `bool`), `MM_MIN <= mm <= MM_MAX`, and `abs(mm * 10 - round(mm * 10)) < 1e-6`.
  - `mm_to_depth(mm: float) -> int`.
  - `parse_depth_report(data: bytes) -> Optional[bytes]`: the 20 key depths (`data[1:21]`) when `data[0] == 0x06` and `len(data) >= 21`, else `None`.
  - `class KeyTracker(fire_a: int, fire_b: Optional[int] = None)`, with `.feed(depth: int) -> List[Tuple[str, bool]]` (slot `"a"` or `"b"`, down) and `.reset() -> None` (see Task 7). Task 13 adds the secondary behaviour. Here, a `fire_b` other than `None` raises `NotImplementedError`.

- [ ] **Step 1: Failing tests**
  - `test_mm_to_depth`: `1.5 → 16`, `2.5 → 120`, `3.6 → 251`, `2.0 → 68`, `3.0 → 180`, `1.6 → 26`. Monotonic over all 22 steps.
  - `test_valid_mm`: true for `1.5`, `3.6`, `2.6000000000000005`, `2`. False for `1.4`, `3.7`, `2.55`, `True`, `"2.0"`, `None`.
  - `test_parse_depth_report`: a 24-byte `0x06` report → 20 bytes. Report ID `0x01` → `None`. 10 bytes → `None`.
  - `test_single_down_up_with_hysteresis` (fire 16): 15 → `[]`; 16 → `[("a", True)]`; 200 → `[]`; 9 → `[]`; 8 → `[]`; 7 → `[("a", False)]`; 16 → `[("a", True)]`.
  - `test_single_fast_jump`: 0 → 255 → `[("a", True)]`; 255 → 0 → `[("a", False)]`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** `mm_to_depth` interpolates linearly between the two `DEPTH_POINTS` that bracket `mm` and returns `round(...)`.
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: depth mapping and key tracker`

### Task 7: Engine handles depth (default actuation)

**Files:**
- Modify: `py_modules/tartarus/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `KeyTracker`, `mm_to_depth`, `DEFAULT_MM`, `ANALOG_KEYS`.
- Produces: `RemapEngine.handle_depth(depths: bytes) -> None` (20 bytes, index i = `ANALOG_KEYS[i]`). The engine builds one tracker per key on `__init__` and `set_profile`. In M2 every key uses `mm_to_depth(DEFAULT_MM)`. Slot `"a"` triggers control `kNN` through the existing `_trigger`. `KeyTracker.reset()` semantics: the tracker forgets what it holds. If the last depth it saw is at or above its lowest release point, it ignores everything until the depth drops below that point (re-arm).

- [ ] **Step 1: Failing tests**
  - `test_depth_press_and_release`: profile with k01 → `Esc`. `handle_depth` with byte 0 at 16 → Esc down; at 7 → Esc up. Other bytes 0 → nothing else.
  - `test_depth_uses_k01_binding_types`: k02 bound to a macro and k03 to `steam:menu`. A depth press runs them like `handle_key` does.
  - `test_depth_ignored_in_passthrough`: `passthrough = True` → no output.
  - `test_release_all_blocks_until_rearm` (Review Focus 1): k01 at 200 → Esc down. `set_profile(same)` → Esc up. 210 → nothing. 5 → nothing. 16 → Esc down.
  - `test_unchanged_bytes_do_nothing`: the same report twice → output once.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** `release_all` calls `reset()` on every tracker. In passthrough, `handle_depth` still feeds the trackers but drops their events, so a key held into Record doesn't fire when Record ends. One `sync()` per report.
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: engine turns key depth into presses`

### Task 8: Mode lifecycle in the service

**Files:**
- Modify: `py_modules/tartarus/config.py` (`Config.analog: bool = True`; dump/parse `"analog"`, non-bool → `True`), `py_modules/tartarus/service.py`, `main.py`, `src/api.ts`
- Test: Create `tests/test_service_analog.py`; `tests/test_config.py`

**Interfaces:**
- Consumes: `set_mode_report`, `HidrawReader`, `TartarusNodes.depth`, `engine.handle_depth`, `parse_depth_report`, `ANALOG_KEYS`.
- Produces:
  - Service ctor kwarg `open_hidraw: Callable[[str], Any] = HidrawReader`.
  - `_enter_driver_mode() -> None` and `_leave_driver_mode() -> None`. `self._analog: Optional[str]` is `"on"`, `"off"` (switch off), `"unavailable"`, or `None` when disconnected.
  - `set_analog(enabled: bool) -> None`; callable `set_analog(enabled) -> state`.
  - State `"analog": {"enabled": bool, "status": "on" | "off" | "unavailable" | None, "default_mm": 1.5, "min_mm": 1.5, "max_mm": 3.6, "min_gap_mm": 0.5}`. TS type `AnalogState` and `setAnalog`.
- Lifecycle:
  - Connect order: grab → `_enter_driver_mode` (send driver mode, status `0x02`, then open the depth reader and `add_reader`) → lighting → LEDs.
  - Failure (no `depth` or `hidraw` node, OSError, status ≠ `0x02`, reader open fails after the mode was set) → send normal mode if driver mode was set, `_analog = "unavailable"`, warning.
  - `_disconnect` and `stop`: `release_all`, then `_leave_driver_mode` (remove the reader, close it, send normal mode if the mode is on; failures logged at info), then ungrab as today.
  - Depth reader errors are treated like an evdev read failure: `_disconnect()`.
  - In driver mode, `EV_KEY` factory codes of `ANALOG_KEYS` are dropped and logged once per connection.

- [ ] **Step 1: Failing tests** (Rig with `FakeSender` and a pipe-backed `FakeHidraw` exposing `push(report: bytes)` and `unplug()`):
  - `test_connect_enters_driver_mode`: sent order `set_mode_report(DRIVER_MODE)`, then the lighting reports, then the LED report. `state()["analog"]["status"] == "on"`. Pushing a depth report with k01 at 20 → the k01 binding goes down.
  - `test_driver_mode_status_failure_falls_back`: driver mode answered `0x05` → status `"unavailable"`, warning logged, evdev k01 still works.
  - `test_no_depth_node_falls_back`: `TartarusNodes(..., depth=None)` → no mode report sent, status `"unavailable"`.
  - `test_depth_open_failure_restores_normal_mode` (Review Focus 3): `open_hidraw` raises → the sent reports include driver then normal mode; status `"unavailable"`.
  - `test_stop_sends_normal_mode_after_release`: hold k01 by depth, `stop()` → in a shared log list, the emitter's k01 release comes before `set_mode_report(NORMAL_MODE)`, and that comes before any ungrab.
  - `test_depth_read_error_disconnects_and_reconnects_in_driver_mode` (Review Focus 2): `FakeHidraw.unplug()` → disconnected, the held output released, then on reconnect a second driver-mode report is sent.
  - `test_resume_reenters_driver_mode`: as `test_resume_reconnects`: normal mode sent, then driver mode again.
  - `test_analog_keys_evdev_dropped_in_driver_mode`: evdev `KEY_1` (k01's factory code) → no output, one info log for repeated codes. `KEY_LEFTALT` (top button) still remaps.
  - `test_set_analog_toggles_at_runtime`: hold k01 by depth, `set_analog(False)` → release first, then normal mode sent, reader closed, status `"off"`, setting persisted. `set_analog(True)` → driver mode again. Non-bool → `ValueError`.
  - `test_analog_off_at_connect`: stored `"analog": false` → no mode report, status `"off"`.
  - `tests/test_config.py`: `analog` round-trips; missing or `"yes"` → `True`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** as in Interfaces. Drain the reader per readable callback (loop `read_report()` until `None`, at most 64 reports). Each report goes to `engine.handle_depth` at once.
- [ ] **Step 4: Full suite PASS; `pnpm build` clean.** `TWO_NODES` has no `depth` node, so older service tests now run in the "unavailable" fallback. That is fine, as long as no test changes its assertions to pass.
- [ ] **Step 5: Commit** `feat: driver mode while the plugin has the keypad`

### Task 9: Panel analog switch

**Files:**
- Modify: `src/Panel.tsx`

- [ ] **Step 1: Implement.** In the Keypad section, a `ToggleField` "Analog keys" bound to `state.analog.enabled` (backend state, not local state; see the remount note in `Panel.tsx`) that calls `setAnalog`. Under it, when connected: status `"unavailable"` → "Analog keys unavailable: keys work at the fixed hardware point."; `"off"` → "Keys work at the fixed hardware point.".
- [ ] **Step 2: `pnpm build` clean**
- [ ] **Step 3: Commit** `feat: analog keys switch in the panel`

### Deck check M2 (user runs; Claude asks before the first deploy, since it enters driver mode)

1. Deploy (this is also the unload check from Task 3: no "still alive" in the log).
2. Panel shows Analog on. Keys 01-20 type at a light press (1.5 mm). Top button, D-pad and wheel work. No suspend in the next minute.
3. **Profile LEDs in driver mode:** switch games → LEDs follow. Change the effect, then the brightness → LEDs stay. If the LEDs don't change in driver mode, stop and plan the fallback with the user: send the LED report before `_enter_driver_mode`, on connect and on switch (switch would then need normal → LEDs → driver, which the user must approve). If that fails too, stop and ask.
4. Toggle Analog off → keys type at the hardware point. Toggle back on.
5. Unplug → replug → keys work, analog on. Suspend → resume → same.
6. Disable the plugin in Decky → keys 01-20 type normally (normal mode restored). Re-enable.
7. Update `docs/superpowers/synapse-capture-findings.md` "Still a guess" with the LED-in-driver-mode result.

---

## M3: Actuation per key + recording from depth

### Task 10: `actuation` in the profile

**Files:**
- Modify: `py_modules/tartarus/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Profile.actuation: Dict[str, float] = field(default_factory=dict)` (only keys set away from the default, values `round(mm, 1)`). JSON `"actuation": {"k01": 2.5}` per profile, always written.

- [ ] **Step 1: Failing tests**
  - `test_actuation_round_trip`.
  - `test_v2_file_without_actuation_loads` → `{}`.
  - `test_bad_actuation_dropped` (one warning each): `{"k01": 1.4, "k02": 2.55, "k03": "2", "top_button": 2.0, "k99": 2.0, "k04": true}` → `{}`, and `{"k05": 2.6000000000000005}` → `{"k05": 2.6}` (Review Focus 5). A value of exactly 1.5 is dropped silently, since it is the default.
  - A non-dict `actuation` → `{}`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** in `_parse_profile` and `_dump`, using `analog.valid_mm`. `create_profile` copies it (`dict(source.actuation)`). Add that to `test_create_profile_copies_and_caps`.
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: store actuation per key`

### Task 11: Engine uses the profile's actuation; set one key or all keys

**Files:**
- Modify: `py_modules/tartarus/engine.py`, `py_modules/tartarus/service.py`, `main.py`, `src/api.ts`
- Test: `tests/test_engine.py`, `tests/test_service_analog.py`

**Interfaces:**
- Produces:
  - Engine trackers use `mm_to_depth(profile.actuation.get(key, DEFAULT_MM))`.
  - `set_actuation(profile_id: str, control: str, mm: float) -> None`
  - `set_all_actuation(profile_id: str, mm: float) -> None`
  - Both raise `ValueError` for invalid mm or a non-analog control. A value equal to `DEFAULT_MM` removes the entry. They save, and call `set_profile` on the engine if the profile is active (via `_edited`).
  - Callables `set_actuation`, `set_all_actuation` → state.
  - State `profiles[i]["actuation"]: {control: mm}`.
  - TS `ProfileState.actuation: Record<string, number>`, `setActuation`, `setAllActuation`.

- [ ] **Step 1: Failing tests**
  - Engine `test_actuation_point_from_profile`: k01 at 2.5 → depth 119 nothing, 120 down, 112 still down, 111 up.
  - Service `test_set_actuation`: persists `2.5`. `1.5` removes the key. `3.7`, `"k21"` and `"top_button"` raise. The active profile's engine follows (depth 119 no longer fires k01).
  - `test_set_all_actuation`: all 20 keys at `2.0`. Then `1.5` → `{}`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Full suite PASS; `pnpm build` clean**
- [ ] **Step 5: Commit** `feat: actuation point per key`

### Task 12: Record from depth

**Files:**
- Modify: `py_modules/tartarus/service.py`
- Test: `tests/test_service_record.py`

**Interfaces:**
- Behaviour: while a capture runs in driver mode, the depth handler (before `engine.handle_depth`) feeds the first key whose depth reaches `mm_to_depth(MM_MIN)` (16) as `FACTORY_OUTPUT[key]` down. When that key drops below 8 it is fed up, so the capture finishes. Other keys are ignored until then. Keys pressed when Record starts must re-arm first: reuse a `KeyTracker(16)` per key, `reset()` on start.

- [ ] **Step 1: Failing tests** `test_record_from_depth`: record_start, depth k02 at 20 then 0 → `record_result` `{"type": "key", "keys": ["2"]}`. `test_record_depth_first_key_wins`: k02 at 20, k03 at 30, both to 0 → `"2"`. `test_record_depth_held_key_needs_rearm`: k01 at 200 before record_start, k01 at 210 → nothing. k01 to 0, then 20, then 0 → `"1"`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: record keypad keys in driver mode`

### Deck check M3 (user runs; Claude asks before the probe step's sends)

1. Deploy. There is no UI yet: with the plugin disabled, the user adds `"actuation": {"k01": 3.6}` to the Default profile in `settings.json` (sudo), then re-enables the plugin. A light press on 01 does nothing; a full press types.
2. Editor → Record → press key 05 → binding recorded as `5`.
3. **Normal-mode hardware point** (spec: measure once). Disable the plugin. Run `deck-probe.py setmode 00`. In a text field, press key 01 slowly until `1` appears and hold it there. With the key still held, run `deck-probe.py setmode 03`, then `deck-probe.py read 5`, and release slowly. The first `iface 1 06 …` line in `~/tartarus-probe.log` gives the depth at the hardware point. Repeat 3 times. Finish with `setmode 00`. Record the result in `synapse-capture-findings.md`. If it maps to more than 1.8 mm (depth > 47), ask the user which default to ship (1.5 mm or the measured point) before release. M4 can go on meanwhile.

---

## M4: Secondary function

### Task 13: Secondary in the tracker

**Files:**
- Modify: `py_modules/tartarus/analog.py`
- Test: `tests/test_analog.py`

**Interfaces:**
- Produces: `KeyTracker(fire_a, fire_b)` with `fire_b > fire_a`. States: idle, A held, B held, latched (between, A silent). Transitions:

| State | Report | Events → next state |
|---|---|---|
| idle | `d >= fire_b` | `[("b", True)]` → B |
| idle | `fire_a <= d < fire_b` | `[("a", True)]` → A |
| A | `d >= fire_b` | `[("a", False), ("b", True)]` → B |
| A | `d < fire_a - 8` | `[("a", False)]` → idle |
| B | `d < fire_a - 8` | `[("b", False)]` → idle |
| B | `d < fire_b - 8` | `[("b", False)]` → latched |
| latched | `d >= fire_b` | `[("b", True)]` → B |
| latched | `d < fire_a - 8` | `[]` → idle |

`reset()` with the last depth `>= fire_a - 8` → blocked until `d < fire_a - 8`, as in Task 7.

- [ ] **Step 1: Failing tests** (fire_a 16, fire_b 251), one per spec bullet:
  - `test_secondary_a_then_b_then_up`: 20 → A down; 100 → `[]`; 251 → A up, B down; 242 → B up; 100 → `[]`; 7 → `[]`; 20 → A down.
  - `test_secondary_fast_jump_only_b`: 0 → 255 → `[("b", True)]`; → 0 → `[("b", False)]`.
  - `test_secondary_b_refires_without_rearm`: …B held, 200 → B up; 251 → B down; 200 → B up; 7 → `[]`.
  - `test_secondary_reset_blocks`: B held, `reset()`, 255 → `[]`, 7 → `[]`, 251 → `[("b", True)]`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** the table; remove the `NotImplementedError`.
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: secondary function in the key tracker`

### Task 14: `secondary` in the profile

**Files:**
- Modify: `py_modules/tartarus/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) Secondary(binding: Binding, actuation: float)` (setters replace it, never mutate); `Profile.secondary: Dict[str, Secondary] = field(default_factory=dict)`. JSON `"secondary": {"k05": {"binding": {...binding_to_dict...}, "actuation": 3.6}}`. `gap_ok(a_mm: float, b_mm: float) -> bool` in `analog.py`: `tenths(b) - tenths(a) >= 5`.

- [ ] **Step 1: Failing tests**
  - `test_secondary_round_trip`.
  - Missing → `{}`.
  - `test_bad_secondary_dropped` (warning each): non-analog control; bad binding dict; actuation `3.7`; B `2.0` with A `1.6` (gap 0.4); B `2.1` with A `1.6` is kept (`gap_ok(1.6, 2.1)`, Review Focus 5).
  - The gap is checked against the parsed A (a dropped A means 1.5).
  - `create_profile` copies it with `dict(source.secondary)` (safe because `Secondary` is frozen); add that to `test_create_profile_copies_and_caps`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: store secondary functions`

### Task 15: Engine slot B and the service setters

**Files:**
- Modify: `py_modules/tartarus/engine.py`, `py_modules/tartarus/service.py`, `main.py`, `src/api.ts`
- Test: `tests/test_engine.py`, `tests/test_service_analog.py`

**Interfaces:**
- Produces:
  - `engine.B_SUFFIX = ".b"`. A tracker gets `fire_b = mm_to_depth(secondary.actuation)` when the key has one. Slot `"b"` triggers control `kNN.b`, whose binding is `profile.secondary[kNN].binding` (resolve in `_trigger` via a `_binding_for(control)` helper).
  - `set_secondary(profile_id: str, control: str, mm: Optional[float]) -> None`. `None` removes it. Turning it on with no B yet stores `Secondary(Binding("disable", ()), mm)`. Changing mm keeps the binding.
  - `set_binding(profile_id, "kNN.b", b)` (and so `set_binding_text`) sets B's binding. `ValueError` if the key has no secondary.
  - Gap rule (shared helper): `set_secondary` refuses B < A + 0.5. `set_actuation` and `set_all_actuation` move B down to `A + 0.5` when needed, and refuse the whole change (nothing modified) if that would pass 3.6.
  - Callable `set_secondary` → state.
  - State `profiles[i]["secondary"]: {control: {"binding", "label", "actuation"}}`. TS `ProfileState.secondary` and `setSecondary`.

- [ ] **Step 1: Failing tests**
  - Engine `test_secondary_crouch_prone`: k05 A = `C` at 1.5, B = `Z` at 3.6. Depth 20 → C down; 255 → C up, Z down; 200 → Z up; 0 → nothing.
  - Engine `test_release_all_with_b_held`: Z down, `release_all` → Z up; next report 255 → nothing.
  - Engine `test_b_macro`: a macro on B runs.
  - Service `test_set_secondary_and_binding`: on at 3.6 → B `disable`. `set_binding_text("default", "k05.b", "Z")`. Reload keeps both. `set_binding("default", "k06.b", ...)` → `ValueError`.
  - Service `test_secondary_gap_rules`: A 2.0, B 2.4 → refused. `set_actuation(k05, 3.2)` with B 3.6 → refused (B would need 3.7), nothing changes. `set_actuation(k05, 3.1)` with B 3.4 → B becomes 3.6. `set_all_actuation(3.2)` with any secondary → refused, nothing changed. `set_all_actuation(2.0)` with B 2.2 → B becomes 2.5, other secondaries untouched.
  - Service `test_switch_releases_b`: B held, `set_running_app` to another profile → B output released.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Full suite PASS; `pnpm build` clean**
- [ ] **Step 5: Commit** `feat: secondary function per key`

### Deck check M4 (user runs)

Deploy. Settings file (plugin disabled): k12 secondary B = `Z` at 3.6, A = `C`. In RuneScape or a text field: half press → `C` held; full press → `C` released, `Z` held; back to half → `Z` released, no `C`; release and half press → `C`. Fast full press → only `Z`. Disable the plugin while holding the key at B → nothing stays stuck.

---

## M5: Editor UI

All editor controls must work with the D-pad and A button (wrap groups in `Focusable` with `flow-children` as the existing editor does), and take their values from backend state.

### Task 16: Actuation slider, All keys, badges, analog note

**Files:**
- Create: `src/editor/AnalogSettings.tsx`
- Modify: `src/editor/Editor.tsx`, `src/editor/Keypad.tsx`

**Interfaces:**
- Produces: `AnalogSettings(props: { control: string; state: State; profile: ProfileState; onChanged(s: State): void })`, rendered under `BindingPicker` when `control` matches `/^k\d\d$/`.

- [ ] **Step 1: Implement**
  - `SliderField` "Actuation", min 1.5, max 3.6, step 0.1, showing `x.x mm`, value `profile.actuation[control] ?? state.analog.default_mm`. Send `setActuation` on change (debounce 300 ms like the panel's lighting slider; a backend error shows inline in red).
  - An "All keys" row: a slider plus an "Apply to all keys" `DialogButton` → `setAllActuation`. A refusal shows the backend message.
  - When `state.analog.status !== "on"`: a note "Applies only with analog keys on."
  - Keypad: a key with an actuation entry shows its mm (e.g. `2.5`) in the corner label's row, right-aligned at fontSize 9. A key with a secondary shows a small `2×` badge. The rest of the look stays as today.
- [ ] **Step 2: `pnpm build` clean**
- [ ] **Step 3: Commit** `feat: actuation controls in the editor`

### Task 17: Secondary function controls

**Files:**
- Modify: `src/editor/AnalogSettings.tsx`, `src/editor/BindingPicker.tsx` (only if it needs a label prop), `src/editor/Editor.tsx`

- [ ] **Step 1: Implement**
  - `ToggleField` "Secondary function". On → `setSecondary(profile.id, control, 3.6)`; off → `setSecondary(profile.id, control, null)`. If A > 3.1 the backend refuses and the toggle shows its message.
  - When on: a heading "Deep press: <label>", a `BindingPicker` with `control={control + ".b"}` (factory button hidden: `profile.bindings[...]` has no `.b` entry, so it already is), and a slider for B's actuation (min A + 0.5, max 3.6) → `setSecondary`.
- [ ] **Step 2: `pnpm build` clean**
- [ ] **Step 3: Commit** `feat: secondary function in the editor`

### Task 18: LED pattern in the profile bar

**Files:**
- Modify: `src/editor/ProfileBar.tsx`

- [ ] **Step 1: Implement.** Next to the profile dropdown: three small dots (top/middle/bottom, lit = `#dfe3e6`, off = `#434b57`) for `profile.leds`. For non-Default profiles, a `Dropdown` "LEDs" whose options are the viewed profile's own pattern plus the `state.led_patterns` not used by other profiles (each label drawn as `●○○`) → `setLeds`. Default shows the dots only.
- [ ] **Step 2: `pnpm build` clean**
- [ ] **Step 3: Commit** `feat: pick profile LEDs in the editor`

### Deck check M5 (user runs)

Deploy. Using only the D-pad and A: select key 05, set actuation 2.5, see the badge; turn on the secondary function, record B, set B 3.4; apply All keys 2.0 → B stays ≥ 2.5; pick another LED pattern for a profile → LEDs change if it's active; Analog off → the note shows. Then the final whole-branch review with an `opus` subagent.
