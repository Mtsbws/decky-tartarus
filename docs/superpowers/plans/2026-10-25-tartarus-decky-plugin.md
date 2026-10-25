# Decky Tartarus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Decky Loader plugin that remaps a Razer Tartarus Pro (`1532:0244`) in SteamOS Game Mode, opens the Steam / Quick Access menus from the keypad, and sets its lighting, all without Synapse or OpenRazer.

**Architecture:** A root Python backend (stdlib only) grabs the keypad's evdev nodes, runs a pure remap engine, and re-emits through a uinput virtual keyboard and mouse. Lighting goes out as Razer feature reports over hidraw. A React frontend (`@decky/ui`, `@decky/api`) has a Quick Access panel and a full-screen editor route. It also handles the Steam menu actions the backend sends it.

**Tech Stack:** Python 3 stdlib (`fcntl`, `struct`, `ctypes`, `asyncio`, `unittest`), TypeScript + React via the official `decky-plugin-template` (pnpm, rollup), SSH to the Deck for deploys.

**Spec:** `docs/superpowers/specs/2026-10-25-tartarus-decky-plugin-design.md`

## Milestones and stop points

| Milestone | Tasks | Ends with |
|---|---|---|
| M0 Spike (throwaway, hard gate) | S1-S5 | `docs/superpowers/spike-findings.md` committed, plan amended. **Stop.** |
| M1 Backend core (pure, tested on the Mac) | 1-5 | `python3 -m unittest` green. **Stop.** |
| M2 Remapping on the Deck | 6-9 | Keypad remapped through Moonlight using a hand-edited settings file. **Stop.** |
| M3 Lighting | 10-11 | Effects change from a backend callable, reapplied on replug. **Stop.** |
| M4 UI and packaging | 12-15 | Installable zip, full-screen editor working. Final whole-branch review (Opus). **Stop.** |

At each stop: commit, tell the user to `/clear`, and start the next milestone from this file with `/model sonnet`. Browser/device checks for a milestone go to one `sonnet` subagent or to the user's own checklist, once per milestone.

## Global Constraints

- Device: Razer Tartarus Pro 2019, USB `1532:0244`. Send only lighting commands OpenRazer sends for this ID. Never probe unknown commands or touch firmware paths.
- Backend: Python standard library only (or vendored pure-Python modules in `py_modules/`). No pip native modules, no pacman, no system udev rules, no changes outside the home directory.
- `plugin.json` has `"flags": ["root"]`.
- Settings: one JSON file at `decky.DECKY_PLUGIN_SETTINGS_DIR/settings.json`. It holds a list of profiles with one active. Stage 1 has exactly one profile and no profile UI.
- Virtual device names: `Decky Tartarus Keyboard`, `Decky Tartarus Mouse`.
- Killing, crashing or unloading the plugin must leave the keypad working with its factory keys (fd-bound grabs, plus an explicit ungrab/destroy in `_unload`).
- Idle cost: no busy loops. Wait on fds with `loop.add_reader`. Polling is allowed only at ≥2 s intervals.
- Lighting effects ship only if OpenRazer drives them on `1532:0244` with a single device command. Software-streamed effects are dropped.
- Steam menu mechanism order: `@decky/ui` navigation API, then Ctrl+1 (Steam menu) / Ctrl+2 (Quick Access) via the virtual keyboard, then ship disabled with a note.
- 4-way D-pad diagonals hold the union of both neighbouring bindings.
- No Razer images. The keypad picture is our own SVG.
- Code must run on the Deck's Decky Python (3.11). Don't use 3.12+ syntax.

## Review Focus

1. **Autorepeat events (value 2) from the keypad.** Holding a key bound to a shortcut or macro fires it once, not repeatedly. → Task 4 `test_repeat_events_ignored`.
2. **Two triggers that output the same key** (e.g. two keys both bound to `Shift`). The key stays down until the last trigger is released. → Task 4 `test_shared_output_refcounted`.
3. **Binding changed while its trigger is held.** No stuck keys: the old outputs are released when the profile changes. → Task 4 `test_set_profile_releases_held`.
4. **Keypad unplugged or the plugin unloaded while keys are held.** Every virtual key and button is released. → Task 4 `test_release_all` + Task 8 manual check.
5. **Missing, corrupt or wrong-version settings file.** The plugin starts with defaults, keeps the bad file as `settings.json.corrupt-<unix ts>`, and doesn't crash. → Task 2 `test_corrupt_file_backed_up`.

---

## File structure (real build, M1-M4)

```
plugin.json, package.json, main.py, tsconfig.json, rollup.config.js   (from template)
py_modules/tartarus/
  codes.py        key-name table <-> evdev codes, categories (modifier/mouse/media)
  bindings.py     Binding type, dict (de)serialisation, text grammar, labels
  config.py       Config/Profile/Lighting, load/save, defaults
  devmap.py       physical control ids, factory evdev code -> control map (from spike)
  dpad.py         D-pad resolution (4-way / 8-way)
  engine.py       RemapEngine: pure state machine over an Emitter
  record.py       RecordCapture: pure key-capture logic
  lighting.py     Razer report builder + effect -> reports (pure)
  linux/ioctl.py  _IOC helpers and constants
  linux/evdev.py  open/read/grab input nodes, device name/caps
  linux/uinput.py VirtualKeyboard, VirtualMouse (implement Emitter)
  linux/discovery.py  find Tartarus event + hidraw nodes via sysfs
  linux/hidraw.py send_feature()
  service.py      asyncio orchestration: connect/reconnect, resume, record, lighting
tests/            unittest, one file per pure module
src/
  index.tsx       definePlugin, route registration, steam_action listener
  api.ts          typed callables + event names
  steamActions.ts open menus (spike-chosen mechanism)
  Panel.tsx       Quick Access panel
  editor/Editor.tsx, editor/Keypad.tsx, editor/BindingPicker.tsx, editor/quickPicks.ts
scripts/deploy.sh, scripts/package.sh
```

Run Python tests from the repo root: `python3 -m unittest discover -s tests -t .`. Tests import `py_modules.tartarus...` after a `sys.path` insert in `tests/__init__.py` that adds `py_modules`, so modules import as `tartarus.x`. That matches how Decky puts `py_modules` on the path.

---

## M0: Spike (throwaway; hard gate)

Spike code lives on the branch `spike` under `spike/` and is never merged. Only `docs/superpowers/spike-findings.md` lands on `master`. Scripts are stdlib Python copied to `~/spike/` on the Deck. Root scripts write their results to `~/spike/<name>.log`, so the main session can read them over SSH.

### Task S1: Deck access, dev loop, and default key map (Q4)

**Files:** Create `spike/keydump.py` (branch `spike`).

- [ ] **Step 1: Get access details.** Ask the user for the Deck IP and username, and ask them to paste the key tester's default keys if they have them. Add a `Host deck` entry to `~/.ssh/config` only with their OK. Verify: `ssh deck 'uname -r; python3 --version; ls ~/homebrew/plugins'` prints a kernel, a Python ≥3.11 and the plugin list.
- [ ] **Step 2: Settle root access.** Ask the user how root commands should run: they type `ssh -t deck sudo …` in their own terminal (default), or another way they choose. Don't edit sudoers yourself. Record the choice in the findings.
- [ ] **Step 3: Settle the plugin reload method.** Find out (Decky docs or test) whether Decky live-reloads a changed `~/homebrew/plugins/<name>/` or needs `sudo systemctl restart plugin_loader`. Also check whether the plugin folder can be made owned by `deck`, so rsync needs no sudo. Record the exact deploy command that works.
- [ ] **Step 4: Write `keydump.py`.** It lists every `/dev/input/event*` whose sysfs `device/id/vendor`/`product` is `1532`/`0244`. For each it prints the node, `EVIOCGNAME`, USB interface number (from the resolved sysfs path, `…:1.N`), the EV types and KEY/REL capability bits. Then it reads all of those nodes (no grab) and logs `node type code value` lines to `~/spike/keydump.log`.
- [ ] **Step 5: Map every control.** The user runs it as root and presses keys 01-20, the thumb key, scroll up, scroll down, wheel click, then D-pad up, right, down, left and each diagonal, one at a time, in that order, pausing between controls. Expected: one table row per control: control id, node, interface, event type, code name, plus what a diagonal sends (two codes or one). Also list the `/dev/hidraw*` nodes for the device with their interface numbers.

### Task S2: Grab + uinput through Moonlight (Q1) — HARD GATE

**Files:** Create `spike/passthrough.py`.

- [ ] **Step 1: Write `passthrough.py`.** It `EVIOCGRAB`s every Tartarus node from S1. It creates uinput devices `Decky Tartarus Keyboard` (all KEY codes from S1) and `Decky Tartarus Mouse` (BTN_LEFT/RIGHT/MIDDLE/SIDE/EXTRA, REL_X, REL_Y, REL_WHEEL). It forwards keys unchanged, except key 01 → `KEY_ESC` and wheel click → `BTN_RIGHT`. It logs read→write latency per event (`time.monotonic_ns`), and it ungrabs and destroys on SIGTERM/SIGINT.
- [ ] **Step 2: Test in Game Mode.** The user switches to Game Mode, starts the script over SSH as root, opens Moonlight → Arc Raiders, and checks: key 01 acts as Esc in-game, wheel click acts as RMB, movement keys feel unchanged. Expected: the user confirms each, and the log shows p99 processing latency < 1 ms.
- [ ] **Step 3: Test the release path.** `kill -9` the script mid-game. Expected: keypad keys still work (factory map) without replugging. Then run it again and stop it with SIGTERM. Expected: same result.
- [ ] **Step 4: Gate.** If Step 2 or 3 fails, **stop the plan** and redesign with the user (spec: "The spike is a hard gate"). Don't continue to S3.

### Task S3: Steam menu mechanism (Q2)

**Files:** Create a throwaway plugin under `spike/menuplugin/` from `decky-plugin-template`.

- [ ] **Step 1: Build the throwaway plugin.** Clone the template into `spike/menuplugin`, set `flags: ["root"]`, and remove the template's example code. Backend `_main` runs the S2 passthrough logic in an asyncio task. Key 02 calls `decky.emit("steam_action", "menu")`, key 03 emits `"qam"`, key 04 types Ctrl+1 and key 05 types Ctrl+2 through the virtual keyboard. The frontend, in `definePlugin`, subscribes with `addEventListener("steam_action", …)` and calls `Navigation.OpenSideMenu(SideMenu.Main)` / `Navigation.OpenQuickAccessMenu()` from `@decky/ui`, plus `console.log` of each call.
- [ ] **Step 2: Deploy with the S1 deploy command and test.** Test each of keys 02-05 twice: in the Steam UI, and with Moonlight fullscreen in Arc Raiders. Expected: a 4×2 results table (opened / not opened / went to the PC).
- [ ] **Step 3: Choose the mechanism.** Use the first that works under fullscreen Moonlight: `api`, else `keys`, else `disabled` (then tell the user and ask about alternatives, e.g. a virtual controller's Guide button). Also note whether the API route closes again correctly when the button is pressed twice.

### Task S4: Lighting over hidraw (Q3)

**Files:** Create `spike/light.py`.

- [ ] **Step 1: Pull the facts from OpenRazer source** (`driver/razerkbd_driver.c`, `driver/razerchromacommon.c`, `driver/razercommon.c/.h`, `daemon/openrazer_daemon/hardware/keyboards.py`). Use a sonnet subagent with a narrow brief: write the facts to `spike/openrazer-facts.md` and return a short summary. Facts wanted for `1532:0244`: transaction ID; which USB interface / report index the control messages go to; whether it uses standard or extended-matrix commands and their LED/varstore IDs; command class/id/args for static, breathing (single/dual/random), spectrum, wave, reactive, starlight, ripple, brightness; which of those the daemon renders in software (frame streaming); the 90-byte report layout and CRC rule.
- [ ] **Step 2: Write `light.py`.** It builds one report (static green, brightness 255) from those facts. It sends it with `HIDIOCSFEATURE` on the hidraw node for the interface found in Step 1, with report ID 0 prefixed (91 bytes). It reads the response back with `HIDIOCGFEATURE` and logs the status byte.
- [ ] **Step 3: Run it.** Expected: the keypad turns green and the status byte is `0x02` (success). Then try one firmware effect (spectrum). If nothing changes, try no other commands. Record the failure; the spec then says ship remapping without lighting.

### Task S5: Findings and plan amendment

**Files:** Create `docs/superpowers/spike-findings.md` on `master`. Modify this plan.

- [ ] **Step 1: Write the findings.** Sections: access and deploy loop (exact commands), control → evdev table (S1), D-pad behaviour, hidraw node/interface, Q1 result and latency, chosen `STEAM_ACTION_MODE` (`api`|`keys`|`disabled`) with the S3 table, lighting facts (transaction ID, interface, per-effect class/id/args as hex bytes, which effects ship), and anything that contradicts this plan.
- [ ] **Step 2: Amend this plan** where findings change it. Typical changes: D-pad handling in Task 3 if diagonals arrive as their own codes, Task 10's effect list, and Task 9's mechanism. Mark each change `(amended from spike)`.
- [ ] **Step 3: Commit on master and stop.**

```bash
git add docs/superpowers/spike-findings.md docs/superpowers/plans/2026-10-25-tartarus-decky-plugin.md
git commit -m "docs: spike findings and plan amendments"
```

Tell the user: M0 done. `/clear`, then `/model sonnet`, then start M1 from this file.

---

## M1: Backend core (pure Python, tested on the Mac)

### Task 1: Scaffold, key-name table, binding model

**Files:**
- Create from template: `plugin.json`, `package.json`, `main.py` (stub `Plugin` with `_main`/`_unload`), `src/index.tsx` (empty panel), `tsconfig.json`, `rollup.config.js`, `LICENSE` (MIT, crediting KEYZER and OpenTartarus as references), `.gitignore`
- Create: `py_modules/tartarus/__init__.py`, `py_modules/tartarus/codes.py`, `py_modules/tartarus/bindings.py`, `tests/__init__.py`, `tests/test_bindings.py`

**Interfaces:**
- Produces (`codes.py`): `KEYS: dict[str, int]` (canonical name → evdev code). `code_for(name: str) -> int` (case-insensitive, raises `KeyError`). `name_for(code: int) -> str | None`. `category(name) -> Literal["key","modifier","mouse","media"]`. Modifiers are `Shift, Ctrl, Alt, Super, RShift, RCtrl, RAlt` (left variants are the plain names). Mouse: `LMB, RMB, MMB, Mouse4, Mouse5, WheelUp, WheelDown` (wheel names have pseudo-codes `-1`/`-2`, see engine). Media: `Vol+, Vol-, Mute, Play, Next, Prev`. Keys: `A-Z, 0-9, F1-F24, Esc, Tab, CapsLock, Space, Enter, Backspace, Delete, Insert, Home, End, PageUp, PageDown, Up, Down, Left, Right, Minus, Equal, LeftBracket, RightBracket, Backslash, Semicolon, Apostrophe, Grave, Comma, Period, Slash, PrintScreen, Pause, ScrollLock, NumLock, KP0-KP9, KPEnter, KPPlus, KPMinus, KPAsterisk, KPSlash, KPDot`.
- Produces (`bindings.py`): `BINDING_TYPES = ("key","shortcut","combo","modifier","macro","mouse","media","disable","steam")`. `STEAM_ACTIONS = ("menu","qam")`.
  `@dataclass(frozen=True) class Binding: type: str; keys: tuple[str, ...] = (); steps: tuple[tuple[str, ...], ...] = (); action: str = ""`.
  `class BindingError(ValueError)`. `binding_from_dict(d: dict) -> Binding`, `binding_to_dict(b: Binding) -> dict` (JSON shape `{"type":…, "keys":[…]}` / `{"type":"macro","steps":[[…],…]}` / `{"type":"steam","action":"menu"}` / `{"type":"disable"}`). `parse_binding_text(text: str) -> Binding`. `binding_label(b: Binding) -> str`.
- Text grammar (also the editor's **Type** field): `disable` → disable. `steam:menu` / `steam:qam` → steam. `hold:W+A` → combo. A comma-separated list of ≥2 combos → macro. `X+Y` → shortcut. A single name goes to key/modifier/mouse/media according to `category`. Names are canonicalised and whitespace is ignored.
- Labels: key/modifier/mouse/media → the name. Shortcut → `Ctrl+C`. Combo → `W+A (hold)`. Macro → steps joined by `, `. Disable → `—`. Steam → `Steam menu` / `Quick Access`.

- [ ] **Step 1: Scaffold from the template.** Copy the template files. Set `plugin.json` name `Decky Tartarus`, `flags: ["root"]`, `api_version: 1`. Set `package.json` name `decky-tartarus`. Verify: `pnpm i && pnpm build` produces `dist/index.js`.
- [ ] **Step 2: Write failing tests** in `tests/test_bindings.py`:

```python
def test_parse_single_key(self):      assert parse_binding_text("esc") == Binding("key", ("Esc",))
def test_parse_modifier(self):        assert parse_binding_text("Shift") == Binding("modifier", ("Shift",))
def test_parse_shortcut(self):        assert parse_binding_text("ctrl + c") == Binding("shortcut", ("Ctrl","C"))
def test_parse_combo(self):           assert parse_binding_text("hold:W+A") == Binding("combo", ("W","A"))
def test_parse_macro(self):           assert parse_binding_text("Ctrl+C, Ctrl+V") == Binding("macro", steps=(("Ctrl","C"),("Ctrl","V")))
def test_parse_mouse_media(self):     assert parse_binding_text("LMB").type == "mouse"; assert parse_binding_text("Vol+").type == "media"
def test_parse_steam_disable(self):   assert parse_binding_text("steam:qam") == Binding("steam", action="qam"); assert parse_binding_text("disable") == Binding("disable")
def test_parse_errors(self):          for bad in ["", "Ctrl+", "Foo", "steam:x", "hold:"]: self.assertRaises(BindingError, parse_binding_text, bad)
def test_dict_round_trip(self):       for t in ["F5","Ctrl+Alt+Delete","hold:W+A","A, B","steam:menu","disable","RMB"]: b=parse_binding_text(t); assert binding_from_dict(binding_to_dict(b)) == b
def test_from_dict_rejects_unknown(self): self.assertRaises(BindingError, binding_from_dict, {"type":"key","keys":["Nope"]})
def test_labels(self):                assert binding_label(parse_binding_text("hold:W+A")) == "W+A (hold)"; assert binding_label(Binding("steam", action="menu")) == "Steam menu"
```

(Write them as proper `unittest.TestCase` methods with `assertEqual`. The lines above fix the inputs and expected values.)
- [ ] **Step 3: Run** `python3 -m unittest tests.test_bindings -v`. Expected: FAIL (ImportError).
- [ ] **Step 4: Implement** `codes.py` with `linux/input-event-codes.h` values typed as a literal dict, then `bindings.py`.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat: scaffold plugin, key table and binding model`.

### Task 2: Config load/save with defaults

**Files:** Create `py_modules/tartarus/devmap.py`, `py_modules/tartarus/config.py`, `tests/test_config.py`.

**Interfaces:**
- Consumes: `Binding`, `binding_from_dict`, `binding_to_dict`, `parse_binding_text`.
- Produces (`devmap.py`): `KEY_CONTROLS = ("k01", …, "k20", "thumb", "wheel_click")`, `WHEEL_CONTROLS = ("wheel_up", "wheel_down")`, `DPAD_CARDINALS = ("dpad_up","dpad_right","dpad_down","dpad_left")`, `DPAD_DIAGONALS = ("dpad_up_right","dpad_down_right","dpad_down_left","dpad_up_left")`, `ALL_CONTROLS` (all of the above in that order). `FACTORY_CODES: dict[int, str]` (evdev KEY code → control id, from spike-findings S1). `FACTORY_OUTPUT: dict[str, str]` (control id → the key name it sends from the factory; diagonals map to the union of their cardinals, written as `hold:Up+Right` text).
- Produces (`config.py`): `@dataclass class Lighting: effect: str = "spectrum"; color: str = "#00ff00"; brightness: int = 100`. `@dataclass class Profile: id: str; name: str; dpad_mode: str  # "4way"|"8way"; bindings: dict[str, Binding]`. `@dataclass class Config: version: int; active_profile: str; profiles: list[Profile]; lighting: Lighting`. `SCHEMA_VERSION = 1`. `default_config() -> Config` (one profile `id="default", name="Default", dpad_mode="4way"`, bindings = `FACTORY_OUTPUT` parsed). `active_profile(c: Config) -> Profile`. `load_config(path: Path) -> Config`. `save_config(path: Path, c: Config) -> None` (write `path.with_suffix(".tmp")`, then `os.replace`).
- Rules: a control missing from the stored bindings gets its factory binding. Stored bindings for unknown control ids are dropped. An invalid binding entry falls back to factory for that control only. A wrong `version` or unparseable JSON makes the file be renamed to `settings.json.corrupt-<int(time.time())>` and defaults returned.

- [ ] **Step 1: Write failing tests:** `test_missing_file_gives_defaults` (the active profile has all `ALL_CONTROLS`, `dpad_mode == "4way"`). `test_round_trip` (set `k01` to `Esc`, save, load, equal). `test_missing_control_filled_from_factory`. `test_bad_binding_falls_back_per_control` (`k02: {"type":"key","keys":["Nope"]}` → factory, `k01` keeps its stored value). `test_corrupt_file_backed_up` (write `"{nope"`, load → defaults, exactly one `settings.json.corrupt-*` exists, the original path no longer exists). `test_wrong_version_backed_up` (`"version": 99` → same). `test_save_is_atomic` (no `.tmp` left after save).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_config -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `devmap.py` (constants from spike findings) and `config.py`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: settings file with defaults and recovery`.

### Task 3: D-pad resolution

**Files:** Create `py_modules/tartarus/dpad.py`, `tests/test_dpad.py`.

**Interfaces:**
- Produces: `resolve_dpad(pressed: frozenset[str], mode: str) -> frozenset[str]`. `pressed` holds cardinal control ids. The result is the set of D-pad control ids whose bindings should be active.
- 4-way: the result is `pressed` (diagonals = union, per spec). 8-way: two adjacent cardinals → their diagonal id only. One cardinal → itself. Opposite or ≥3 cardinals → the cardinals minus the opposing pairs (up+down cancel).
- If spike findings show diagonals arrive as their own codes, `(amended from spike)` this task to map them.

- [ ] **Step 1: Write failing tests:** `test_4way_union` (`{up,right}` → `{up,right}`). `test_8way_diagonal` (`{up,right}` → `{dpad_up_right}`). `test_8way_single` (`{left}` → `{left}`). `test_8way_opposites_cancel` (`{up,down}` → `{}`; `{up,down,left}` → `{left}`). `test_empty` (both modes → `{}`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_dpad -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: d-pad 4-way and 8-way resolution`.

### Task 4: Remap engine

**Files:** Create `py_modules/tartarus/engine.py`, `tests/test_engine.py`.

**Interfaces:**
- Consumes: `Profile`, `Binding`, `code_for`, `category`, `FACTORY_CODES`, `DPAD_CARDINALS`, `resolve_dpad`.
- Produces:

```python
class Emitter(Protocol):
    def key(self, code: int, down: bool) -> None   # keyboard key or mouse button; implementation routes by code
    def wheel(self, delta: int) -> None             # +1 up, -1 down
    def sync(self) -> None
    def steam_action(self, action: str) -> None     # "menu" | "qam"

class RemapEngine:
    def __init__(self, emitter: Emitter, profile: Profile,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 steam_mode: str = "api") -> None
    def handle_key(self, code: int, value: int) -> None   # raw EV_KEY from the keypad; value 0/1/2
    def handle_wheel(self, value: int) -> None            # raw REL_WHEEL from the keypad
    def set_profile(self, profile: Profile) -> None       # release_all() first
    def release_all(self) -> None
    passthrough: bool   # when True, handle_* forward the raw event unchanged (used by Record)
```

- Behaviour: `value == 2` is ignored. A code not in `FACTORY_CODES` is forwarded unchanged. key/modifier/mouse/media/combo → outputs down on press, up on release. Shortcut → all down in order, then up in reverse, on press only. Macro → each step a shortcut tap, 15 ms between down and up, 15 ms between steps, run as an `asyncio` task. Pressing a trigger whose macro is still running is ignored. Disable → nothing. Steam → `emitter.steam_action(action)` on press when `steam_mode == "api"`; when `"keys"`, a tap of `Ctrl+1` (menu) / `Ctrl+2` (qam); when `"disabled"`, nothing. `WheelUp`/`WheelDown` as outputs → `emitter.wheel(±1)` on press. A wheel tick on input is press+release of `wheel_up`/`wheel_down`. Outputs are refcounted per code: a code goes up only when its count reaches 0. Taps don't release a code another binding holds. D-pad cardinal codes update a pressed set, and the engine diffs `resolve_dpad` before/after, releasing removed controls and then pressing added ones. `sync()` after each handled input event.

- [ ] **Step 1: Write failing tests** with a `FakeEmitter` that records `("key", code, down)`, `("wheel", d)` and `("steam", a)` and ignores syncs. Use `unittest.IsolatedAsyncioTestCase` with a fake `sleep` that only yields.
  - `test_key_binding_holds`: `k01`=`Esc`. Press → `[("key",KEY_ESC,True)]`. Release adds `("key",KEY_ESC,False)`.
  - `test_shortcut_taps_once`: `k01`=`Ctrl+C`. Press → Ctrl↓ C↓ C↑ Ctrl↑. Release adds nothing.
  - `test_repeat_events_ignored`: shortcut, then `handle_key(code, 2)` ×3 → still one tap.
  - `test_combo_holds_all`: `hold:W+A` → W↓ A↓ on press, A↑ W↑ on release.
  - `test_shared_output_refcounted`: `k01`=`k02`=`Shift`. Press k01, press k02, release k01 → no Shift↑. Release k02 → Shift↑.
  - `test_set_profile_releases_held`: hold `k01`=`Esc`, `set_profile(other)` → `Esc↑` emitted. Then releasing k01 emits nothing.
  - `test_release_all`: hold a combo and a mouse button → all released.
  - `test_macro_runs_steps_and_ignores_retrigger`: `A, B`. Press, press again while running → exactly A↓A↑B↓B↑.
  - `test_unknown_code_passthrough`: a code not in `FACTORY_CODES` → forwarded with the same value.
  - `test_disable`: nothing emitted.
  - `test_steam_api_and_keys_modes`: api → `("steam","menu")`. keys → Ctrl↓ 1↓ 1↑ Ctrl↑.
  - `test_wheel_input_and_output`: `wheel_up`=`F5` → F5↓F5↑ per tick. `k01`=`WheelDown` → `("wheel",-1)`.
  - `test_dpad_8way_transition`: 8-way, `dpad_up`=`W`, `dpad_up_right`=`E`. Press up → W↓. Press right → W↑ then E↓. Release up → E↑ then (right binding)↓.
  - `test_passthrough_mode`: `passthrough=True` → raw codes forwarded, bindings ignored.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_engine -v`. Expected: FAIL.
- [ ] **Step 3: Implement `RemapEngine`.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: remap engine`.

### Task 5: Record capture

**Files:** Create `py_modules/tartarus/record.py`, `tests/test_record.py`.

**Interfaces:**
- Consumes: `Binding`, `category`.
- Produces: `class RecordCapture: def feed(self, name: str, down: bool) -> Binding | None`. It collects key names in press order while any are down. When all are released it returns the result: one name → `key`/`modifier`/`mouse`/`media` by category; ≥2 → `shortcut` with modifiers first (Ctrl, Shift, Alt, Super order), then the others in press order. Before anything is pressed, releases return `None`.

- [ ] **Step 1: Write failing tests:** `test_single_key` (`F5`↓↑ → key F5). `test_combo_orders_modifiers` (`C`↓ `Ctrl`↓ `C`↑ `Ctrl`↑ → shortcut `("Ctrl","C")`). `test_modifier_alone` (`Shift` → modifier). `test_stray_release_ignored` (`A`↑ first → `None`, then `B`↓↑ → key B).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_record -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite** `python3 -m unittest discover -s tests -t .`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat: record capture` and **stop**: M1 done. Tell the user `/clear`, `/model sonnet`, start M2.

---

## M2: Remapping on the Deck

### Task 6: ioctl constants, evdev and uinput wrappers

**Files:** Create `py_modules/tartarus/linux/__init__.py`, `linux/ioctl.py`, `linux/evdev.py`, `linux/uinput.py`, `tests/test_ioctl.py`.

**Interfaces:**
- Produces (`ioctl.py`): `IOC(dir, type_char, nr, size) -> int`, `IOW`, `IOR`, `IOWR`. Constants: `EVIOCGRAB`, `UI_SET_EVBIT`, `UI_SET_KEYBIT`, `UI_SET_RELBIT`, `UI_DEV_SETUP`, `UI_DEV_CREATE`, `UI_DEV_DESTROY`. Functions: `EVIOCGNAME(n)`, `EVIOCGBIT(ev, n)`, `HIDIOCSFEATURE(n)`, `HIDIOCGFEATURE(n)`.
- Produces (`evdev.py`): `INPUT_EVENT = struct.Struct("llHHi")` (24 bytes). `class InputDevice: path; name; fd; def __init__(self, path: str); def grab(self) -> None; def ungrab(self) -> None; def read_events(self) -> list[tuple[int,int,int]]  # (type, code, value), non-blocking, raises OSError(ENODEV) on unplug; def close(self) -> None; def has_key(self, code) -> bool`.
- Produces (`uinput.py`): `class VirtualKeyboard`, `class VirtualMouse` (each `__init__(name: str)`, `emit(type, code, value)`, `syn()`, `close()` → `UI_DEV_DESTROY` + close). `class UinputEmitter(Emitter)` composes both: BTN_* codes go to the mouse, everything else to the keyboard. `wheel` → `REL_WHEEL` on the mouse. `steam_action` calls a callback passed to `__init__(on_steam: Callable[[str], None])`. Keyboard enables `EV_KEY` for every code in `KEYS` (no `EV_REP`). Mouse enables BTN_LEFT/RIGHT/MIDDLE/SIDE/EXTRA and REL_X/REL_Y/REL_WHEEL. Both use `BUS_VIRTUAL`, vendor 0, product 0.

- [ ] **Step 1: Write failing tests** pinning ioctl numbers: `EVIOCGRAB == 0x40044590`, `UI_SET_EVBIT == 0x40045564`, `UI_SET_KEYBIT == 0x40045565`, `UI_DEV_SETUP == 0x405C5503`, `UI_DEV_CREATE == 0x5501`, `HIDIOCSFEATURE(91) == 0xC05B4806`, `EVIOCGNAME(256) == 0x81004506`. Plus `INPUT_EVENT.size == 24`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_ioctl -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the three modules. `uinput_setup` is packed as `struct.pack("HHHH80sI", BUS_VIRTUAL, 0, 0, 0, name, 0)` (92 bytes).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Device smoke test.** Use the spike's root-command method to run a one-off `python3 -c` on the Deck that creates `VirtualKeyboard("Decky Tartarus Keyboard")`, types `KEY_A`, and destroys it. Expected: `grep "Decky Tartarus" /proc/bus/input/devices` matches while the device is alive and not after destroy.
- [ ] **Step 6: Commit** `feat: evdev, uinput and ioctl wrappers`.

### Task 7: Device discovery

**Files:** Create `py_modules/tartarus/linux/discovery.py`, `tests/test_discovery.py`.

**Interfaces:**
- Produces: `@dataclass class TartarusNodes: event: list[str]; hidraw: str | None`. `find_tartarus(sys_root: str = "/sys") -> TartarusNodes | None`. It scans `sys_root/class/input/event*/device/id/{vendor,product}` and `sys_root/class/hidraw/hidraw*/device/uevent` (`HID_ID=0003:00001532:00000244`). It picks the hidraw whose interface number (from the resolved path's `:1.N` suffix) matches the spike's lighting interface, mapped to `/dev/<name>`. `LIGHTING_INTERFACE` is a constant from spike findings. `list_keyboards(sys_root="/sys") -> list[str]` returns non-Tartarus event nodes with `KEY_A` capability (from `device/capabilities/key`) whose name doesn't start with `Decky Tartarus`.

- [ ] **Step 1: Write failing tests** against a fake sysfs tree built in a `tempfile.TemporaryDirectory`, with symlinks shaped like the paths recorded in spike findings. Tests: `test_finds_all_event_nodes`, `test_picks_lighting_hidraw`, `test_absent_returns_none`, `test_list_keyboards_excludes_tartarus_and_virtual`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_discovery -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: find tartarus nodes in sysfs`.

### Task 8: Service and plugin lifecycle

**Files:** Create `py_modules/tartarus/service.py`, `tests/test_service.py`, `scripts/deploy.sh`. Modify `main.py`.

**Interfaces:**
- Consumes: everything above.
- Produces (`service.py`): `class ResumeDetector: def check(self, boottime: float, monotonic: float) -> bool`. It returns True when `boottime - monotonic` has grown by > 2 s since the last call, meaning the Deck slept. `class TartarusService: def __init__(self, settings_path: Path, emit: Callable[[str, ...], Awaitable[None]]); async def start(self); async def stop(self); def state(self) -> dict; def set_binding(self, control: str, b: Binding) -> None; def set_dpad_mode(self, mode: str) -> None`.
- Behaviour: `start` loads the config, creates the virtual devices once, and runs a supervisor task. While disconnected it calls `find_tartarus` every 2 s. On connect it opens and grabs all event nodes, registers `loop.add_reader` per fd, and emits `state_changed`. On `ENODEV`/`OSError` from a read it calls `engine.release_all()`, removes readers, closes nodes, emits `state_changed`, and goes back to polling. Every 5 s it calls `ResumeDetector.check(time.clock_gettime(time.CLOCK_BOOTTIME), time.monotonic())`; on True it reconnects (and, from M3, reapplies lighting). Setters update the config, `save_config`, and `engine.set_profile`. `stop` releases all, ungrabs, closes nodes, and destroys the virtual devices. The `state()` dict: `{"connected": bool, "dpad_mode": str, "steam_mode": str, "bindings": {control: {"binding": dict, "label": str}}}`.
- `main.py` `Plugin`: `_main` builds `TartarusService(Path(decky.DECKY_PLUGIN_SETTINGS_DIR)/"settings.json", decky.emit)` and starts it. `_unload` awaits `stop()`. Callables: `get_state() -> dict`, `set_binding(control: str, binding: dict) -> dict`, `set_binding_text(control: str, text: str) -> dict` (returns `{"ok": bool, "error": str | None, "state": dict}`), `set_dpad_mode(mode: str) -> dict`. Unknown control ids or modes raise `ValueError` and return `{"ok": False, …}` for the text variant.
- `scripts/deploy.sh <host>`: `pnpm build`, then rsync `dist/ main.py plugin.json package.json py_modules/ LICENSE` to `~/homebrew/plugins/decky-tartarus/` on the host, then the reload command from spike findings.

- [ ] **Step 1: Write failing tests:** `test_resume_detector` (first call False; same offset False; offset +3 s True). `test_state_shape` (construct the service with a temp settings path and fake emit, without `start`; `state()` has all `ALL_CONTROLS` and `connected False`). `test_set_binding_persists` (`set_binding("k01", Esc)` → reload file → `Esc`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service -v`. Expected: FAIL.
- [ ] **Step 3: Implement `service.py`, `main.py`, `deploy.sh`.** Log through `decky.logger` in `main.py`. Service methods take a `logging.Logger`, defaulting to `logging.getLogger("tartarus")`.
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Deck check (user runs, checklist).** Deploy. Hand-edit `settings.json` so `k01` = `Esc`, `k02` = `hold:W+A`, then reload the plugin. In Moonlight → Arc Raiders, check: k01 is Esc, k02 moves diagonally. Unplug and replug while holding k02: the character stops when unplugged and the mapping works after replug. Sleep and wake the Deck: the mapping still works. Disable the plugin in Decky: the factory keys work.
- [ ] **Step 6: Commit** `feat: background remapping service`.

### Task 9: Steam menu actions and record backend

**Files:** Create `src/api.ts`, `src/steamActions.ts`, `tests/test_service_record.py`. Modify `py_modules/tartarus/service.py`, `main.py`, `src/index.tsx`.

**Interfaces:**
- Produces (backend): `STEAM_ACTION_MODE` constant in `service.py` from spike findings (`api`|`keys`|`disabled`), passed to `RemapEngine`. In `api` mode, `UinputEmitter.on_steam` schedules `emit("steam_action", action)`. `TartarusService.record_start() -> None`: sets `engine.passthrough = True`, maps each Tartarus key code to its control (`FACTORY_CODES`) and then to that control's factory key name (`FACTORY_OUTPUT`), and feeds that name into a `RecordCapture`, and opens `list_keyboards()` nodes read-only (no grab) feeding the same capture. On the first result it emits `record_result` with `binding_to_dict(b)`, then stops recording. `record_cancel()` stops. Both stop paths restore `passthrough = False` and close the extra nodes. There's a 10 s timeout that emits `record_result` with `null`. Callables in `main.py`: `record_start`, `record_cancel`.
- Produces (`src/api.ts`): types `BindingDict`, `ControlState = {binding: BindingDict; label: string}`, `State = {connected: boolean; dpad_mode: "4way"|"8way"; steam_mode: string; bindings: Record<string, ControlState>; lighting?: LightingState; effects?: string[]}`. Callables via `callable<…>()` from `@decky/api`: `getState`, `setBinding`, `setBindingText`, `setDpadMode`, `recordStart`, `recordCancel`. Event name constants `EV_STEAM_ACTION = "steam_action"`, `EV_STATE = "state_changed"`, `EV_RECORD = "record_result"`.
- Produces (`src/steamActions.ts`): `openSteamAction(action: "menu" | "qam"): void`, using the mechanism the spike confirmed (`Navigation.OpenSideMenu(SideMenu.Main)` / `Navigation.OpenQuickAccessMenu()`).
- `src/index.tsx` registers `addEventListener(EV_STEAM_ACTION, openSteamAction)` in `definePlugin` and removes it in `onDismount`.

- [ ] **Step 1: Write a failing test** `test_record_restores_passthrough`. With a fake engine and no real devices, `record_start()` then `record_cancel()` → `engine.passthrough is False`. Also, feeding a capture result emits `record_result` once.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service_record -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the backend parts, then `api.ts`, `steamActions.ts`, `index.tsx`. Verify `pnpm build` passes with no type errors.
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Deck check.** Bind `k03` = `steam:menu` and `k04` = `steam:qam` in `settings.json`. With Moonlight fullscreen, each opens its menu, and pressing again closes it (matches the S3 result).
- [ ] **Step 6: Commit** `feat: steam menu actions and record backend` and **stop**: M2 done. `/clear`, `/model sonnet`, start M3.

---

## M3: Lighting

### Task 10: Razer report builder and effects

**Files:** Create `py_modules/tartarus/lighting.py`, `tests/test_lighting.py`.

**Interfaces:**
- Produces: `TRANSACTION_ID: int` (from spike findings). `build_report(command_class: int, command_id: int, args: bytes) -> bytes`. It returns 90 bytes: `[0]=0x00 status, [1]=TRANSACTION_ID, [2:4]=0x0000 remaining, [4]=0x00 protocol, [5]=len(args), [6]=class, [7]=id, [8:88]=args zero-padded, [88]=CRC (XOR of bytes 2..87), [89]=0x00`. `EFFECTS: tuple[str, ...]`: the subset of `("static","breathing","spectrum","wave","reactive","starlight","ripple")` that spike findings mark firmware-native, in that order. `effect_reports(effect: str, color: str, brightness: int) -> list[bytes]`: the effect report followed by the brightness report. Colour is `#rrggbb`. Brightness 0-100 maps to 0-255 with `round(b * 255 / 100)`. Unknown effect or bad colour raises `ValueError`.

- [ ] **Step 1: Write failing tests.** `test_report_layout_and_crc`: the length is 90 and the CRC equals the XOR of bytes 2-87. Use one hex example copied from spike findings as the expected full report. `test_effect_bytes_match_findings`: for each shipped effect, the class/id/args bytes equal the findings table. `test_brightness_scaling` (100 → 255, 0 → 0, 50 → 128). `test_rejects_bad_input` (`"#zzzzzz"`, `"ripple"` if not shipped, brightness 101).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_lighting -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: razer lighting reports`.

### Task 11: hidraw sender and lighting in the service

**Files:** Create `py_modules/tartarus/linux/hidraw.py`, `tests/test_service_lighting.py`. Modify `service.py`, `main.py`, `src/api.ts`.

**Interfaces:**
- Produces: `send_feature(path: str, report: bytes) -> int`. It opens `O_RDWR`, sends `b"\x00" + report` with `HIDIOCSFEATURE(91)`, waits 1 ms, reads back with `HIDIOCGFEATURE(91)`, and returns the status byte. `TartarusService.set_lighting(effect: str, color: str, brightness: int) -> None` validates through `effect_reports`, saves to config and applies if connected. Lighting is applied on every connect and on resume. A non-`0x02` status is logged, not raised. `state()` gains `"lighting": {"effect","color","brightness"}` and `"effects": list(EFFECTS)`. The `set_lighting` callable is in `main.py`. `api.ts` gains `LightingState` and `setLighting`.
- If spike S4 failed: skip `send_feature` wiring, set `EFFECTS = ()`, and `state()["effects"] == []` so the panel hides lighting. `(amended from spike)` as needed.

- [ ] **Step 1: Write failing tests.** With a patched `send_feature`: `test_set_lighting_persists_and_applies` (connected → the patched sender receives the effect reports in order). `test_lighting_reapplied_on_connect`. `test_bad_lighting_rejected` (raises `ValueError`, config unchanged).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service_lighting -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Deck check.** Deploy, then call `set_lighting` for each effect. The quickest route is a temporary call from the frontend dev console, or a `python3 -c` with the service stopped. Each effect is visible, and brightness 20 vs 100 is visibly different. Replug → the last effect comes back. Sleep/wake → same.
- [ ] **Step 6: Commit** `feat: lighting via hidraw` and **stop**: M3 done. `/clear`, `/model sonnet`, start M4.

---

## M4: UI and packaging

### Task 12: Quick Access panel

**Files:** Create `src/Panel.tsx`. Modify `src/index.tsx`.

**Interfaces:**
- Consumes: `api.ts` (`getState`, `setLighting`, `EV_STATE`).
- Produces: `Panel(): JSX.Element`, with a `PanelSection` "Keypad" showing `Connected` / `Not connected` (live via `EV_STATE`). The "Lighting" section, hidden when `effects` is empty, has a `Dropdown` of effects, a colour `TextField` (`#rrggbb`) and a `SliderField` for brightness 0-100 (step 5). Changes call `setLighting` debounced by 250 ms. An "Edit keys" `ButtonItem` calls `Navigation.Navigate("/decky-tartarus/editor")`, then `Navigation.CloseSideMenus()`. Hide the colour field for effects that ignore colour (spectrum, wave per findings).

- [ ] **Step 1: Implement**, wire it as `content` in `definePlugin` with title `Tartarus` and an icon from `react-icons` (as the template does).
- [ ] **Step 2: Verify** `pnpm build` (no type errors). Deploy and open the QAM: status follows plug/unplug within ~2 s, and lighting changes apply.
- [ ] **Step 3: Commit** `feat: quick access panel`.

### Task 13: Keypad picture and editor route

**Files:** Create `src/editor/Keypad.tsx`, `src/editor/Editor.tsx`. Modify `src/index.tsx`.

**Interfaces:**
- Consumes: `State`, `getState`, `setDpadMode`, `EV_STATE`.
- Produces: `Keypad(props: {state: State; selected: string | null; onSelect(control: string): void}): JSX.Element`. It's an SVG of our own drawing in KEYZER's style: 4 staggered rows (01-05, 06-10, 11-15, 16-20), the thumb key, the scroll wheel (up, click and down as three hit areas), and the D-pad (4 cardinal areas; plus 4 diagonal areas only when `dpad_mode === "8way"`). Each key shows its control number small and `label` large, truncated with an ellipsis. The selected key is highlighted. Every area is clickable with the mouse and touch (`onClick`) and gamepad-focusable (`Focusable` with `onActivate`). `Editor(): JSX.Element` has a two-column layout: `Keypad` on the left, and `BindingPicker` for the selected control on the right (Task 14; a placeholder until then). A `ToggleField` "8-way D-pad" calls `setDpadMode`. It's registered with `routerHook.addRoute("/decky-tartarus/editor", Editor)` and removed in `onDismount`.

- [ ] **Step 1: Implement.** Keep the layout coordinates in one `const LAYOUT: Record<string, {x:number;y:number;w:number;h:number}>` table in `Keypad.tsx`.
- [ ] **Step 2: Verify** `pnpm build`. On the Deck, "Edit keys" opens the editor. All controls render with their current labels, and toggling 8-way shows/hides the diagonals.
- [ ] **Step 3: Commit** `feat: editor route with keypad picture`.

### Task 14: Binding picker (quick picks, Record, Type)

**Files:** Create `src/editor/BindingPicker.tsx`, `src/editor/quickPicks.ts`. Modify `src/editor/Editor.tsx`.

**Interfaces:**
- Consumes: `setBinding`, `setBindingText`, `recordStart`, `recordCancel`, `EV_RECORD`.
- Produces: `QUICK_PICKS: {label: string; text: string}[]`, in this order: `Esc`→`Esc`, `Steam menu`→`steam:menu`, `Quick Access`→`steam:qam`, `Tab`, `Space`, `Enter`, `Shift`, `Ctrl`, `Alt`, `F1`-`F12` (collapsed under "More keys"), `LMB`, `RMB`, `MMB`, `Vol+`, `Vol-`, `Mute`, `Play`, `Disable`→`disable`, and `Factory default` (sends the control's factory text, from `state` via a `factory` field). Add `"factory": str` per control to `state()["bindings"]` in `service.py` (text form of `FACTORY_OUTPUT`). Hide the Steam picks when `steam_mode === "disabled"` and show the note "Steam menu shortcuts don't work while streaming on this setup". `BindingPicker(props: {control: string; state: State; onChanged(s: State): void})` contains:
  - the quick-pick list → `setBindingText(control, text)`
  - **Record** button → `recordStart()`. Shows "Press a key or combo…" with a Cancel button (→ `recordCancel()`). On `EV_RECORD` with a binding → `setBinding`. On `null` → "Nothing recorded". Recording is cancelled on unmount.
  - **Type** `TextField` + Apply → `setBindingText`. A short help line shows the grammar (`Ctrl+C`, `hold:W+A`, `A, B, C`, `steam:menu`, `disable`). `error` from the response appears under the field in red.
  - Changes apply immediately, and `onChanged` refreshes the keypad labels.

- [ ] **Step 1: Add the `factory` field** in `service.py` and extend `test_state_shape` to assert `state()["bindings"]["k01"]["factory"]` is a non-empty string. Run the full suite. Expected: PASS.
- [ ] **Step 2: Implement** `quickPicks.ts`, `BindingPicker.tsx`, and wire them into `Editor`.
- [ ] **Step 3: Verify** `pnpm build`. Then run one `sonnet` subagent / user checklist on the Deck covering:
  - a quick-pick changes the label and the in-game behaviour
  - Record of `Ctrl+C` from a USB/BT keyboard and from the Tartarus itself
  - Record timeout
  - Type `hold:W+A` works and `Ctrl+` shows an error
  - Steam picks open the menus under Moonlight
- [ ] **Step 4: Commit** `feat: binding picker with record and type`.

### Task 15: Packaging, README, final review

**Files:** Create `scripts/package.sh`, `README.md`.

**Interfaces:**
- `scripts/package.sh` makes `out/decky-tartarus.zip` with a top-level `decky-tartarus/` folder containing `dist/index.js`, `main.py`, `plugin.json`, `package.json`, `py_modules/` (no `__pycache__`), `LICENSE`, `README.md`.
- README: what it does, install via Decky Developer Mode → Install from zip / URL or by copying into `~/homebrew/plugins`, the binding text grammar, where settings live, the Steam-menu caveat from findings, the uninstall guarantee, and credits (KEYZER, OpenTartarus, OpenRazer as the protocol reference).

- [ ] **Step 1: Write `package.sh` and `README.md`.** Run `scripts/package.sh` and check that `unzip -l out/decky-tartarus.zip` lists exactly those paths.
- [ ] **Step 2: Clean-install check (user).** Uninstall the dev copy, install the zip through Developer Mode, reboot the Deck. Bindings and lighting persist from `settings.json`. Uninstall the plugin: the keypad works with factory keys.
- [ ] **Step 3: Idle check.** With the keypad connected and idle for 60 s, run `top -b -n 3 -d 5 -p <backend pid>` on the Deck. Expected: ~0.0% CPU.
- [ ] **Step 4: Commit** `chore: packaging and readme`.
- [ ] **Step 5: Final whole-branch review** with one `opus` reviewer (superpowers:requesting-code-review) against the spec and the Review Focus list. Fix confirmed findings, then use superpowers:finishing-a-development-branch. **Stop.**
