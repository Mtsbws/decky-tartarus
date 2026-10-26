# Named Profiles with Per-Game Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Up to 8 named keypad layouts, each game assigned to one, with the keypad switching automatically to the running game's layout (Default otherwise).

**Architecture:** The settings file moves to schema 2 (profiles + game assignments, migrated from v1 in `load_config`). The backend stores the running app in memory and *derives* the active profile from it plus the assignments; every switch goes through `RemapEngine.set_profile`. The frontend polls `Router.MainRunningApp` at plugin level every 2 s and reports it; the panel shows the active layout and assigns the running game; the editor gains a profile bar.

**Tech Stack:** Python 3 stdlib (`unittest`, `asyncio`), TypeScript + React with `@decky/ui` / `@decky/api` (pnpm, rollup).

**Spec:** `docs/superpowers/specs/2026-10-25-game-profiles-design.md` (builds on `docs/superpowers/specs/2026-10-25-tartarus-decky-plugin-design.md`). Read the spec before starting any task.

## Milestones

| Milestone | Tasks | Done when |
|---|---|---|
| M1 Config schema 2 + migration | 1-2 | `python3 -m unittest discover -s tests -t .` green. **Stop.** |
| M2 Backend switching + callables | 3-5 | Suite green. **Stop.** (Frontend is out of step with the backend until M3; don't deploy.) |
| M3 Detection + panel | 6-7 | `pnpm build` clean; Deck check (below). **Stop.** |
| M4 Editor profile bar | 8-9 | `pnpm build` clean; Deck check; final whole-branch review (Opus). **Stop.** |

At each stop: commit, tell the user to `/clear`, and start the next milestone from this file with `/model sonnet`. The Deck check for a milestone is done once, by the user's checklist or one `sonnet` subagent, not per task. Deploy with `scripts/deploy.sh <host>`.

Python tests run from the repo root: `python3 -m unittest discover -s tests -t .` (modules import as `tartarus.x`). Frontend check: `pnpm build` with no type errors.

## Global Constraints

- Stdlib-only Python, root backend, settings writes atomic via `save_config`'s mkstemp + `os.replace`, nothing written outside the settings folder.
- At most 8 profiles, Default included. The profile with id `default` always exists, can't be deleted, always has `leds` `[false, false, false]`.
- Profile names: trimmed, 1–24 characters, unique ignoring case. Default can be renamed.
- `games` keys: the 32-bit unsigned app ID as a decimal string. Unassigned games (and games on Default) have no entry.
- LED order for new profiles (first free wins): `(T,F,F) (F,T,F) (F,F,T) (T,T,F) (T,F,T) (F,T,T) (T,T,T)`. Stored only: never sent to the device, never shown in the UI.
- Lighting stays global. No new keypad commands.
- Every change of active profile goes through `engine.set_profile` (releases held keys, cancels macros).
- Frontend poll: every 2000 ms, first poll immediately, at plugin level; app ID `Number(app.appid) >>> 0`, name `app.display_name`; no debounce of "none".
- Confirmations use Decky's `ConfirmModal`, never `window.confirm()`.

## Review Focus

1. **The poll reports the same app every 2 s.** An unchanged report must not save the file, call `set_profile` (which would release a key the user is holding mid-game) or emit `state_changed`. Test in Task 3.
2. **A game is running when the backend (re)starts.** The next report must switch to the game's profile even though the frontend saw no change. Covered by reporting on every poll; test in Task 3 (fresh service + report → engine gets the profile).
3. **The v1 file has `active_profile` pointing at a missing id, or several profiles.** The first profile becomes Default, extras dropped with a warning, bindings identical. Test in Task 2.
4. **Deleting or reassigning the profile of the game being played, while a key is held.** The key is released and the keypad lands on Default / the new profile. Tests in Task 4.
5. **Steam remounts the QAM panel when a dropdown opens** (see the lighting comment in `src/Panel.tsx`). The "uses" dropdown must take its value from backend state, never local state, so the pick still shows. Checked on the Deck in M3.

---

## M1: Config schema 2 + migration

### Task 1: Schema 2 model, parsing and bad-entry rules

**Files:**
- Modify: `py_modules/tartarus/config.py`
- Modify: `tests/test_config.py` (rewrite `_stored` for v2; replace `active_profile` uses with `default_profile`)
- Modify: `tests/test_engine.py:7,40` (`active_profile(default_config())` → `default_profile(default_config())`)

**Interfaces:**
- Produces (all in `tartarus.config`):
  - `SCHEMA_VERSION = 2`, `MAX_PROFILES = 8`, `DEFAULT_ID = "default"`, `NAME_MAX = 24`, `LED_ORDER: Tuple[Tuple[bool, bool, bool], ...]` (the 7 lit patterns above, in order), `NO_LEDS = (False, False, False)`
  - `Profile(id: str, name: str, dpad_mode: str, bindings: Dict[str, Binding], leds: Tuple[bool, bool, bool] = NO_LEDS)`
  - `Game(name: str, profile: str)` dataclass
  - `Config(version: int, profiles: List[Profile], games: Dict[str, Game] = field(default_factory=dict), lighting: Lighting = field(default_factory=Lighting))` — `active_profile` field removed; Default is always `profiles[0]`
  - `default_profile(c: Config) -> Profile`
  - `find_profile(c: Config, profile_id: str) -> Optional[Profile]`
  - `profile_for_app(c: Config, app_id: Optional[int]) -> Profile` — the assigned profile, else Default
  - `next_leds(c: Config) -> Tuple[bool, bool, bool]` — first pattern in `LED_ORDER` not used by any profile; `ValueError` if none free
  - `clean_name(c: Config, name: str, exclude_id: Optional[str] = None) -> str` — trims; `ValueError` for empty, longer than 24, or clashing (ignoring case) with another profile than `exclude_id`
  - `new_profile_id(c: Config) -> str` — `"p<n>"` with the smallest n ≥ 2 not in use
  - The old `active_profile()` function is deleted.

- [ ] **Step 1: Write the failing tests** in `tests/test_config.py` (`ConfigTest`, using a v2 `_stored(profiles, games=None)` helper):
  - `test_v2_round_trip`: `default_config()` plus a profile `Profile("p2", "MMO", "8way", factory_bindings(), (True, False, False))` and `games={"1343400": Game("RuneScape", "p2")}`; save then load → equal.
  - `test_default_config_shape`: `default_config().profiles == [Profile("default", "Default", "4way", factory_bindings(), NO_LEDS)]`, `games == {}`, `version == 2`.
  - `test_default_parsed_first_and_kept`: file lists `p2` before `default` → loaded `profiles[0].id == "default"`; a file without `default` → Default recreated with `factory_bindings()` (warning logged).
  - `test_profiles_beyond_eight_skipped`: default + 9 others → 8 loaded, the last two dropped, `assertLogs("tartarus", "WARNING")`.
  - `test_duplicate_ids_and_names_skipped`: two `p2` entries, and `p3` named `"mmo"` when `p2` is `"MMO"` → only the first of each kept.
  - `test_bad_name_skipped_default_renamed`: a non-default profile named `""` or 25 chars is skipped; Default with name `"  "` loads as `"Default"`; names are stored trimmed (`" FPS "` → `"FPS"`).
  - `test_bad_or_duplicate_leds_reassigned`: `p2` leds `[true, false, false]`, `p3` the same, `p4` `"x"`, Default `[true, true, true]` → Default `NO_LEDS`, `p2` keeps `(T,F,F)`, `p3` gets `(F,T,F)`, `p4` gets `(F,F,T)`.
  - `test_bad_assignments_dropped`: games `{"1343400": {"name":"RS","profile":"p2"}, "12": {"name":"X","profile":"nope"}, "abc": {...p2}, "-1": {...}, "4294967296": {...}, "0": {...}, "5": {"name":"D","profile":"default"}}` → only `"1343400"` kept. A non-string `name` falls back to the key (`"1343400"`).
  - `test_profile_for_app`: assigned app → its profile; unassigned app, `None` → Default.
  - `test_next_leds_and_clean_name`: `next_leds` on default-only config → `(True, False, False)`; `clean_name(c, " Default ")` raises (clash), `clean_name(c, " default ", exclude_id="default") == "default"`, `clean_name(c, "x"*25)` raises, `clean_name(c, "  ")` raises.
  - Keep the existing tests (corrupt file, wrong version → backed up, atomic save, planted symlink, unknown control, bad binding per control), adapted to v2. `test_wrong_version_backed_up` uses `version: 3`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_config -v` → FAIL (import errors on the new names).
- [ ] **Step 3: Implement** in `config.py`. Split today's `_parse_profile` binding loop into `_parse_bindings(raw) -> Dict[str, Binding]` (reused by Task 2). Parse order: the `default` entry first (wherever it is in the list), then the rest in file order, stopping at 8; then one pass reassigning missing/invalid/duplicate/all-off `leds` via `next_leds`. A file that isn't an object, has a version other than 1 or 2, or whose `profiles` isn't a list stays on the corrupt-file path. Version 1 raises `_Corrupt` for now (Task 2 replaces that). `_dump` writes `version`, `profiles` (with `leds` as a list), `games` (`{key: {"name", "profile"}}`) and `lighting`; no `active_profile`.
- [ ] **Step 4: Run** the full suite `python3 -m unittest discover -s tests -t .`. `test_config` and `test_engine` PASS. `test_service*` may fail on `active_profile` imports; fix only the imports/calls there to `default_profile` so the suite is green (service behaviour changes in M2).
- [ ] **Step 5: Commit** `feat: settings schema 2 with profiles and game assignments`.

### Task 2: Migrate v1 files with a backup

**Files:**
- Modify: `py_modules/tartarus/config.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: `_parse_bindings`, `default_profile`, `save_config` from Task 1.
- Produces: `load_config(path)` returns a v2 `Config` for a v1 file, having written `settings.json.v1-backup` (the original bytes) and the migrated file. Private helper `_write_atomic(path: Path, text: str) -> None` (the mkstemp/fchmod 0o644/fsync/`os.replace` body of today's `save_config`, which now calls it).

- [ ] **Step 1: Write the failing tests** (v1 fixture: `{"version": 1, "active_profile": ..., "profiles": [...], "lighting": {...}}`):
  - `test_migrates_v1_active_profile`: v1 with profiles `a` (k01 `Esc`, 4way) and `b` (k01 `F1`, 8way), `active_profile: "b"` → one profile `Profile("default", "Default", "8way", <b's bindings with factory fill>, NO_LEDS)`, `games == {}`, lighting unchanged; a WARNING names the dropped extra.
  - `test_migrates_v1_missing_active_uses_first`: `active_profile: "zzz"` → `a`'s bindings.
  - `test_migration_writes_backup_and_v2_file`: after `load_config`, `settings.json.v1-backup` has the original text byte for byte; `settings.json` parses as JSON with `version == 2` and no `active_profile` key; a second `load_config` returns an equal config and leaves the backup untouched.
  - `test_migration_backup_does_not_follow_symlink`: a symlink planted at `settings.json.v1-backup` pointing to a victim file → victim unchanged, backup now a regular file.
  - `test_v1_without_profiles_is_corrupt`: v1 with `profiles: []` → moved to `.corrupt-*`, defaults returned.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_config -v` → the new tests FAIL.
- [ ] **Step 3: Implement** `_migrate_v1(data) -> Config` and call it from `load_config` for `version == 1`: write the backup with `_write_atomic(path.with_name(path.name + ".v1-backup"), original_text)`, then `save_config`. If either write raises `OSError`, log a warning and still return the migrated config (the next start retries). Log one INFO line "migrated settings to version 2".
- [ ] **Step 4: Run** the full suite → PASS (`test_service_lighting.test_stored_unknown_effect_falls_back_to_default` uses a v1 file and must still pass through migration).
- [ ] **Step 5: Commit** `feat: migrate v1 settings to schema 2 with a backup` and **stop**: M1 done. `/clear`, `/model sonnet`, start M2.

---

## M2: Backend switching + callables

### Task 3: Running app and the derived active profile

**Files:**
- Modify: `py_modules/tartarus/service.py`
- Modify: `main.py` (the three setters gain `profile_id`)
- Create: `tests/test_service_profiles.py` (reuse `Rig`, `FakeDevice`, `until`, `TWO_NODES` by importing them from `tests.test_service`)
- Modify: `tests/test_service.py` (`test_state_shape`, `test_set_binding_persists`, `test_set_dpad_mode_persists`, `test_unknown_control_or_mode_rejected` for the new shape/signatures)

**Interfaces:**
- Consumes: `profile_for_app`, `find_profile`, `default_profile`, `Game` from Task 1.
- Produces on `TartarusService`:
  - `set_running_app(app_id: Optional[int], name: Optional[str]) -> None` — `None` or `0` means none; a non-int, bool, or value outside `0..2**32-1` raises `ValueError`; a blank/missing name becomes `str(app_id)`. Identical to the stored running app → returns without saving, switching or emitting. Otherwise stores it, updates an assigned game's stored name if it differs (and saves), switches if the derived profile changed, and emits `state_changed`.
  - `set_binding(profile_id: str, control: str, b: Binding) -> None`, `set_dpad_mode(profile_id: str, mode: str) -> None` — unknown profile id raises `ValueError`; the engine is updated only when `profile_id` is the active one.
  - `_switch(before_id: str) -> None` — if the derived active profile's id differs from `before_id`: cancel a running Record capture, sending `record_result` `None` if one was running, then `engine.set_profile(active)` when the engine exists. Every operation that can change the active profile captures `before_id = self._profile().id` first and calls `_switch(before_id)` after.
  - `_profile()` returns `profile_for_app(self._config, running_app_id)`. `_connect` also calls `engine.set_profile(self._profile())`.
  - `state()` returns:
    ```
    connected, device, device_id, steam_mode, lighting, effects   (unchanged)
    active_profile: str                                            (id)
    running_app: {"app_id": int, "name": str} | None
    max_profiles: 8
    profiles: [{"id", "name", "is_default": bool, "games": [names, sorted case-insensitively],
                "dpad_mode", "bindings": {control: {"binding", "label", "factory"}}}]
    ```
    Top-level `dpad_mode` and `bindings` are removed. `leds` is not in the state.

- [ ] **Step 1: Write the failing tests** in `tests/test_service_profiles.py`. Build a settings file with Default (k01 `1`) and `p2` "MMO" (k01 `Esc`), `games {"1343400": RuneScape → p2}`:
  - `test_starts_on_default`: after `start()`, `state()["active_profile"] == "default"`, `running_app is None`.
  - `test_running_app_switches_and_back`: connect; `set_running_app(1343400, "RuneScape")` → active `p2`, pressing k01 emits `KEY_ESC`; `set_running_app(None, None)` → active `default`; an unassigned `set_running_app(42, "Other")` → `default`.
  - `test_switch_releases_held_key`: connect, k01 down under `p2` (Esc down), `set_running_app(None, None)` → emitter's last key event is `("key", KEY_ESC, False)`.
  - `test_same_report_is_a_noop` (Review Focus 1): after one report, record `path.stat().st_mtime_ns`, `len(rig.events)` and wrap `engine.set_profile` with a counter; a second identical report changes none of them.
  - `test_report_after_restart_switches` (Review Focus 2): a fresh `Rig` on the same file, `start()`, one report of 1343400 → engine profile id `p2`.
  - `test_report_without_engine_only_stores`: no `start()`; `set_running_app(1343400, "RuneScape")` doesn't raise and `state()["active_profile"] == "p2"`; after `start()` the engine's profile is `p2`.
  - `test_assigned_name_updated`: report `(1343400, "RuneScape NXT")` → reloaded file has that name; reporting an unassigned app writes no `games` entry.
  - `test_bad_app_id_rejected`: `-1`, `2**32`, `"12"`, `True` raise `ValueError`.
  - `test_switch_cancels_record`: `record_start()` then a switching report → `("record_result", None)` in `rig.events` and `engine.passthrough` is False.
  - `test_edit_non_active_profile`: active `default`; `set_binding("p2", "k01", Esc→"F1")` saves to `p2` and doesn't call `engine.set_profile`; `set_binding("default", ...)` does. `set_binding("nope", ...)` raises `ValueError`.
  - Update `test_state_shape` in `tests/test_service.py` to the key set above and assert on `state["profiles"][0]["bindings"]["k01"]`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service_profiles tests.test_service -v` → FAIL.
- [ ] **Step 3: Implement** in `service.py` per the Interfaces block. Running app lives in `self._running: Optional[Tuple[int, str]]`, never in the file.
- [ ] **Step 4: Update `main.py`** so `set_binding`, `set_binding_text` and `set_dpad_mode` take `profile_id: str` first and pass it through, and update `PluginTest.test_plugin_set_binding_text` to pass `"default"`. Run the full suite → PASS.
- [ ] **Step 5: Commit** `feat: switch profiles on the running app`.

### Task 4: Assign, create, rename, delete

**Files:**
- Modify: `py_modules/tartarus/service.py`
- Modify: `tests/test_service_profiles.py`

**Interfaces:**
- Consumes: `clean_name`, `new_profile_id`, `next_leds`, `MAX_PROFILES`, `DEFAULT_ID`, `Game` (Task 1); `_switch` (Task 3).
- Produces on `TartarusService` (each saves, calls `_switch(before_id)`, and emits `state_changed`; validation errors raise `ValueError` before anything changes, with a message fit to show the user, e.g. `"At most 8 profiles"`, `"Default can't be deleted"`, `"A profile named MMO already exists"`):
  - `assign_running_game(profile_id: str) -> None` — unknown id raises; no running app → no-op; `"default"` removes the entry; otherwise sets `Game(running_name, profile_id)`.
  - `create_profile(name: str, copy_from_id: str) -> str` — returns the new id; copies `dpad_mode` and a new `dict` of bindings (`Binding` is frozen); `leds = next_leds(c)`; appended at the end.
  - `rename_profile(profile_id: str, name: str) -> None`
  - `delete_profile(profile_id: str) -> None` — removes the profile and every `games` entry pointing at it.

- [ ] **Step 1: Write the failing tests:**
  - `test_assign_running_game`: running 1343400 on Default, connected, k01 held → `assign_running_game("p2")` releases the held key, active `p2`, file has the entry; `assign_running_game("default")` removes the entry and goes back to Default; `assign_running_game("nope")` raises; with no running app, `assign_running_game("p2")` changes nothing in the file.
  - `test_create_profile_copies_and_caps`: `create_profile(" FPS ", "p2")` → new profile named `"FPS"`, bindings and dpad equal to `p2`'s, editing it leaves `p2` untouched, `leds (False, True, False)` in the file (p2 has `(T,F,F)`); fill to 8 → the next raises `ValueError` and the file is unchanged; a clashing name (`"mmo"`), `""` and 25 chars raise; unknown `copy_from_id` raises.
  - `test_led_reuse_after_delete`: profiles get `(T,F,F)`, `(F,T,F)`, `(F,F,T)`; delete the second; next create gets `(F,T,F)`.
  - `test_rename_profile`: rename `p2` → `"Raid"` keeps assignments; rename `default` → `"Base"` allowed and Default stays the fallback; renaming to its own name in other case (`"RAID"`) allowed; to another profile's name raises.
  - `test_delete_profile` (Review Focus 4): running 1343400 on `p2`, connected, k01 held → `delete_profile("p2")` releases the key, active `default`, `games` no longer has 1343400; `delete_profile("default")` and `delete_profile("nope")` raise.
  - `test_profile_ops_emit_state`: each operation appends a `state_changed` event.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service_profiles -v` → FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run** the full suite → PASS.
- [ ] **Step 5: Commit** `feat: create, rename, delete and assign profiles`.

### Task 5: Plugin callables

**Files:**
- Modify: `main.py`
- Modify: `tests/test_service.py` (`PluginTest`)

**Interfaces:**
- Consumes: Task 3 and 4 service methods.
- Produces (Decky callables, all returning `self.service.state()` unless noted):
  - `set_running_app(app_id: int | None, name: str | None)`
  - `assign_running_game(profile_id: str)`
  - `create_profile(name: str, copy_from_id: str)` — returns the state; the frontend finds the new profile by name
  - `rename_profile(profile_id: str, name: str)`
  - `delete_profile(profile_id: str)`
  - (`set_binding`, `set_binding_text`, `set_dpad_mode` already take `profile_id` first since Task 3.)

- [ ] **Step 1: Write the failing test** `test_plugin_profile_callables`: on a fresh service, `create_profile("MMO", "default")` → `state["profiles"][1]["name"] == "MMO"`; `set_binding_text(p2_id, "k01", "Esc")` → ok and that profile's k01 label `"Esc"` while Default's stays `"1"`; `set_running_app(1343400, "RuneScape")` then `assign_running_game(p2_id)` → `active_profile == p2_id`, `running_app == {"app_id": 1343400, "name": "RuneScape"}`; `rename_profile`, then `delete_profile` → back to one profile, active `"default"`. 
- [ ] **Step 2: Run** `python3 -m unittest tests.test_service -v` → FAIL.
- [ ] **Step 3: Implement** the callables in `main.py`, following the existing ones.
- [ ] **Step 4: Run** the full suite → PASS.
- [ ] **Step 5: Commit** `feat: profile callables` and **stop**: M2 done. `/clear`, `/model sonnet`, start M3.

---

## M3: Detection + panel

### Task 6: Types, running-app poll, editor kept compiling

**Files:**
- Modify: `src/api.ts`
- Create: `src/runningApp.ts`
- Modify: `src/index.tsx`
- Modify: `src/editor/Editor.tsx`, `src/editor/Keypad.tsx`, `src/editor/BindingPicker.tsx` (minimal: read bindings/dpad from a profile)

**Interfaces:**
- Consumes: Task 5 callables, Task 3 state shape.
- Produces in `src/api.ts`:
  - `type ProfileState = { id: string; name: string; is_default: boolean; games: string[]; dpad_mode: "4way" | "8way"; bindings: Record<string, ControlState> }`
  - `type RunningApp = { app_id: number; name: string }`
  - `State` loses `dpad_mode`/`bindings`, gains `active_profile: string; running_app: RunningApp | null; max_profiles: number; profiles: ProfileState[]`
  - `profileById(state: State, id: string): ProfileState | undefined`, `activeProfile(state: State): ProfileState`
  - callables: `setRunningApp(appId: number | null, name: string | null)`, `assignRunningGame(profileId)`, `createProfile(name, copyFromId)`, `renameProfile(profileId, name)`, `deleteProfile(profileId)` (all `→ State`); `setBinding`, `setBindingText`, `setDpadMode` take `profileId` first.
- Produces in `src/runningApp.ts`: `startRunningAppPoll(): () => void` — polls immediately and every 2000 ms; reads `(Router as any).MainRunningApp`; reports `(Number(app.appid) >>> 0, app.display_name ?? null)` or `(null, null)` on every poll; a rejected call is logged with `console.warn` and the poll continues. Returns the stop function.
- `Keypad` and `BindingPicker` take `profile: ProfileState` in addition to their current props and read `bindings`/`dpad_mode` from it; `BindingPicker` passes `profile.id` to the setters.

- [ ] **Step 1: Implement** the types and callables in `api.ts`, `runningApp.ts`, and in `index.tsx` start the poll in `definePlugin` and call the stop function in `onDismount`. In `Editor.tsx`, pass `activeProfile(state)` as `profile` (Task 8 replaces this with the viewed profile).
- [ ] **Step 2: Verify** `pnpm build` → no type errors.
- [ ] **Step 3: Commit** `feat: report the running app to the backend`.

### Task 7: Panel shows the layout and assigns the game

**Files:**
- Modify: `src/Panel.tsx`

**Interfaces:**
- Consumes: `State`, `activeProfile`, `assignRunningGame`, `errorText` (Task 6 / existing).

- [ ] **Step 1: Implement** in the "Keypad" section, under the connection status row:
  - a row `Layout: <active profile name>`;
  - when `state.running_app` is set, a `DropdownItem` labelled `<running_app.name> uses:` with one option per profile (`data: id`, `label: name`, Default's label suffixed ` (default)`), `selectedOption = state.active_profile` (while a game runs, the active profile is that game's profile). `onChange` calls `assignRunningGame(o.data)` and shows a rejection in red with `errorText`. No local copy of the selection (Review Focus 5): the backend emits `state_changed`, which the mounted panel receives.
  - "Edit keys" unchanged.
- [ ] **Step 2: Verify** `pnpm build` → no type errors.
- [ ] **Step 3: Deck check (M3, once)** via `scripts/deploy.sh <host>`, then the user's checklist or one `sonnet` subagent reporting pass/fail:
  - settings migrated: the old layout is "Default", `settings.json.v1-backup` exists;
  - panel says "Layout: Default" with no game; launch a Steam game and a Moonlight shortcut: each shows its own name in the dropdown;
  - the dropdown lists only Default until M4 adds New; picking it does nothing harmful (full assigning is checked in M4);
  - with a game running, opening the Steam menu, the QAM and the editor keeps the game in the panel (if "none" shows up on overlay or suspend, report it to the user rather than adding a debounce);
  - picking in the dropdown sticks after the panel remounts.
- [ ] **Step 4: Commit** `feat: show the active layout and assign the running game` and **stop**: M3 done. `/clear`, `/model sonnet`, start M4.

---

## M4: Editor profile bar

### Task 8: Profile bar with selection and live-layout note

**Files:**
- Create: `src/editor/ProfileBar.tsx`
- Modify: `src/editor/Editor.tsx`

**Interfaces:**
- Consumes: `State`, `ProfileState`, `profileById` (Task 6).
- Produces: `ProfileBar(props: { state: State; viewing: string; onView(id: string): void; onChanged(s: State): void })`. Task 9 adds the buttons inside it.
- `Editor` keeps `viewing: string | null` state: set to `state.active_profile` on the first `getState()`; if the viewed id disappears from `state.profiles`, it falls back to `state.active_profile`; it never follows later changes of the active profile.

- [ ] **Step 1: Implement** `ProfileBar` at the top of the editor: a `Dropdown` of all profiles (`selectedOption = viewing`); beside it a status line:
  - viewing the active profile: `Editing <name>. The keypad is using it now.`
  - otherwise: `Editing <name>. The keypad is using <active name> right now.`
  - under it: `Used by: <games joined with ", ">`, `Used by: no games` when empty, and for Default `Used by every game without its own profile` (followed by its own games list if any).
  Pass the viewed profile to `Keypad`, `BindingPicker` and `setDpadMode`.
- [ ] **Step 2: Verify** `pnpm build` → no type errors.
- [ ] **Step 3: Commit** `feat: pick the profile to edit in the editor`.

### Task 9: New, Rename, Delete

**Files:**
- Create: `src/editor/NameModal.tsx`
- Modify: `src/editor/ProfileBar.tsx`

**Interfaces:**
- Consumes: `createProfile`, `renameProfile`, `deleteProfile`, `errorText` (Task 6 / existing), `ConfirmModal`, `ModalRoot`, `TextField`, `DialogButton`, `showModal` from `@decky/ui`.
- Produces: `NameModal(props: { title: string; initial: string; onSubmit(name: string): Promise<void>; closeModal?(): void })` — a `TextField` (focusing it opens Steam's on-screen keyboard) and Save/Cancel; Save awaits `onSubmit`, closes on success, shows `errorText(e)` in red and stays open on rejection.

- [ ] **Step 1: Implement** three buttons in `ProfileBar`:
  - **New** (disabled when `state.profiles.length >= state.max_profiles`): `NameModal` titled "New profile", empty initial; submit → `createProfile(name, viewing)`, then `onChanged(state)` and `onView` the profile whose name matches `name.trim()` ignoring case.
  - **Rename**: `NameModal` with the viewed name; submit → `renameProfile(viewing, name)`.
  - **Delete** (disabled for Default): `ConfirmModal` with `strTitle` `Delete <name>?` and `strDescription` `<n> game(s) will go back to Default.` (or `No games use it.` when n is 0); `onOK` → `deleteProfile(viewing)`, then view the active profile. Errors show in the bar in red.
- [ ] **Step 2: Verify** `pnpm build` → no type errors.
- [ ] **Step 3: Deck check (M4, once)**, checklist or one `sonnet` subagent:
  - New copies the viewed profile (Esc/Steam keys come along); Rename via the on-screen keyboard; a duplicate or empty name shows an error and keeps the modal open;
  - New is disabled at 8 profiles; Delete is disabled for Default and its confirmation names the game count;
  - RuneScape on the Deck: assign to an "MMO" profile with D-pad keys rebound; the keys change within ~2 s of launch and revert to Default within ~2 s of exit;
  - a Moonlight shortcut gets its own assignment independent of RuneScape;
  - editing a non-active profile shows "The keypad is using …" and doesn't change the keys in-game; the note updates if the game exits while the editor is open, and the selection stays;
  - holding a key while quitting the game leaves nothing stuck.
- [ ] **Step 4: Commit** `feat: create, rename and delete profiles in the editor`.
- [ ] **Step 5: Final whole-branch review** with one `opus` reviewer against the spec, then **stop**: M4 done. Suggest `superpowers:finishing-a-development-branch`.
