# Starter Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fresh install starts with Default plus three editable starter profiles (`FPS – WASD`, `FPS – D-pad`, `MMO`); "New profile" can copy any starter; the repo documents each starter with a table and a generated picture.

**Architecture:** A data-only module `starters.py` holds the three definitions as binding text. `config.py` turns a definition into a `Profile` (`profile_from_starter`) and builds a first-run config from them (`first_run_config`), used only when there is no readable settings file. `service.create_profile` accepts `starter:<slug>` ids as `copy_from_id`; `state()` lists the starters for the editor. A new `NewProfileModal` replaces the name-only modal and shows the "copy from" list. `scripts/render_layouts.py` draws SVGs from the same data.

**Tech Stack:** Python 3 stdlib (`unittest`, `xml.etree`), TypeScript + React with `@decky/ui` / `@decky/api` (pnpm, rollup).

**Spec:** `docs/superpowers/specs/2026-10-28-starter-profiles-design.md`. Read it before any task. Its *my call* lines and the decisions below are settled; don't reopen them.

## Global Constraints

- Names are exactly `FPS – WASD`, `FPS – D-pad`, `MMO` (en dash U+2013) and fit `NAME_MAX` (24).
- Starter ids: `starter:fps-wasd`, `starter:fps-dpad`, `starter:mmo`. Profiles a fresh install creates get ordinary ids from `new_profile_id` (`p2`, `p3`, `p4`) and LED patterns from `next_leds`.
- Starters are added only at first creation: a missing or corrupt settings file. An existing file, including a v1-migrated one, is never touched; a deleted starter stays deleted.
- No Hypershift in the FPS starters. D-pad mode `4way` everywhere. `k01` is `Esc` at 2.5 mm in all three.
- Settings schema stays at `SCHEMA_VERSION = 2`; existing files load unchanged.
- Editor keeps the CSS Loader look and the existing row/card components; no inline `DialogButton` backgrounds; fits 1280×800 and works with D-pad and A/B.
- Key names in code are `Minus`, `Equal`, `PageUp`, `PageDown`, `NumLock`; docs use `-`, `=`, Page Up, Page Down, Num Lock.
- `docs/starter-profiles.md` opens with a "Made for" line per starter and says the profiles are starting points, not tested per game, and the MMO has not been tested in a game at all.

## Review Focus

1. A settings file that already exists (valid, or v1) gets no starters, now or on any later start. Pinned in Task 2.
2. A starter the user deleted does not come back after a save/load round trip or a restart. Pinned in Task 2.
3. Editing a copy never changes the starter (shared dicts); copying with 8 profiles already, a taken name, or an unknown `starter:` id raises `ValueError` and changes nothing. Pinned in Task 4.
4. A copy of `MMO` keeps its Hypershift key, layer and `k18` secondary, and the secondary passes `gap_ok`. Pinned in Task 4.
5. A corrupt settings file is moved aside as today and the recovered install also gets the starters. Pinned in Task 2.

## Milestones

| Milestone | Tasks | Done when |
|---|---|---|
| S1 Definitions and fresh install | 1-3 | Suite green; Deck check S1. **Stop.** |
| S2 Copy from | 4-6 | Suite green; FE check clean; Deck check S2. **Stop.** |
| S3 Pictures and docs | 7-9 | Suite green (includes the drift check). **Stop.** |
| S4 Screenshot list | 10 | List given to the user. **Stop.** |

At each stop: commit, tell the user to `/clear` and start the next milestone from this file with `/model sonnet`.

**Model:** subagents run on `sonnet` (pass `model` explicitly); `haiku` for mechanical lookups; `opus` only for a final whole-branch review after S3 if the user asks.

**Workspace:** before Task 1, `git switch -c starter-profiles` from `starter-profiles-spec` (no worktree).

**Commands.**
- Suite: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3` → ends in `OK`.
- One file: `python3 -m unittest tests.test_starters 2>&1 | tail -3`.
- FE check: `pnpm build 2>&1 | grep -iE "error|\(!\)"; pnpm exec tsc --noEmit -p . 2>&1 | grep -c "^src/"` → no lines from the first, `0` from the second.

**Deck check (once per milestone S1, S2; one `sonnet` subagent each).** Brief: deploy with `scripts/deploy.sh` (host `192.168.0.245`; `steamdeck.local` may not resolve), measure the live UI over `127.0.0.1:8080` as in the deck-cef-layout-probe memory, report pass/fail per item plus findings, and write long output to a file. **Settings safety:** the user's real settings are on the Deck. Before the check, copy `settings.json` to `settings.json.bak-pre-starters` (never delete it); to see a fresh install move the live file aside, and move it back at the end. Report that the restore was done.

---

### Task 1: Starter definitions

**Files:**
- Create: `py_modules/tartarus/starters.py`
- Test: `tests/test_starters.py`

**Interfaces:**
- Produces:
  - `STARTER_PREFIX = "starter:"`
  - `@dataclass(frozen=True) class Starter: id: str; name: str; bindings: Mapping[str, str]; actuation: Mapping[str, float]; secondary: Mapping[str, Tuple[str, float]]; hypershift: Mapping[str, str]` — `bindings` holds only controls that differ from the factory key (binding text, as `STEAMOS_DEFAULT` does); `secondary` maps control → (binding text, mm).
  - `STARTERS: Tuple[Starter, ...]` in the order FPS – WASD, FPS – D-pad, MMO.
  - `find_starter(starter_id: str) -> Optional[Starter]`.
- This module imports nothing from `config.py` (config imports it).

- [ ] **Step 1: Write the failing tests** in `tests/test_starters.py`, class `StarterDefinitionsTest`:
  - `test_ids_and_names`: ids and names equal the Global Constraints values, in order; every name `len <= NAME_MAX`; `find_starter("starter:mmo").name == "MMO"`; `find_starter("p2")` and `find_starter("starter:nope")` are `None`.
  - `test_every_binding_parses`: for each starter, each text in `bindings`, `secondary` and `hypershift` goes through `parse_binding_text` without error; every control key is in `ALL_CONTROLS`; every actuation/secondary control is in `ACTUATION_KEYS`; every `actuation` mm and secondary mm passes `valid_mm`; each secondary passes `gap_ok(actuation.get(c, DEFAULT_MM), mm)`.
  - `test_fps_wasd_table`: `bindings["k08"] == "W"`, `["k12"] == "A"`, `["k13"] == "S"`, `["k14"] == "D"`, `["k11"] == "Shift"`, `["top_button"] == "Alt"`, `["dpad_up"] == "3"`, `["dpad_left"] == "6"`, `["wheel_click"] == "N"`; `actuation == {"k01": 2.5}`; `hypershift == {}` and no binding text equals `"Hypershift"`.
  - `test_fps_dpad_table`: `dpad_up/right/down/left` are `W/D/S/A`; `k02..k05` are `1..4`; `k08 == "5"`, `k12 == "6"`, `k13 == "F"`, `k14 == "T"`, `k15 == "G"`, `k18 == "X"`; no `Y` anywhere; `hypershift == {}`.
  - `test_mmo_table`: `k19 == "Hypershift"`; `k11 == "Shift"`, `k16 == "Ctrl"`, `k20 == "Alt"`, `top_button == "Space"`, `k18 == "M"`, `secondary == {"k18": ("B", 3.0)}`, `wheel_up/down/click` are `PageUp/PageDown/NumLock`; `hypershift` holds exactly k02-k05, k07-k10, k12-k15 mapped to `Ctrl+1 … Ctrl+4, Ctrl+5 … Ctrl+8, Ctrl+9, Ctrl+0, Ctrl+Minus, Ctrl+Equal`; `k19` and `k18` are not in `hypershift` (they fall through).

- [ ] **Step 2: Run** `python3 -m unittest tests.test_starters 2>&1 | tail -3` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `starters.py`** with the dataclass and these definitions, written as plain dict literals (wrap `Mapping` fields in `types.MappingProxyType` or keep dicts and copy at use; the builder in Task 2 copies):

  Shared: `k01: "Esc"` and `actuation {"k01": 2.5}` in all three.

  | Control | FPS – WASD | FPS – D-pad | MMO |
  |---|---|---|---|
  | k02, k03, k04, k05 | `1`, `2`, `T`, `F` | `1`, `2`, `3`, `4` | `1`, `2`, `3`, `4` |
  | k06 | `Tab` | `Tab` | `Tab` |
  | k07, k08, k09, k10 | `Q`, `W`, `E`, `R` | `Q`, `5`, `E`, `R` | `5`, `6`, `7`, `8` |
  | k11 | `Shift` | `Shift` | `Shift` |
  | k12, k13, k14, k15 | `A`, `S`, `D`, `Y` | `6`, `F`, `T`, `G` | `9`, `0`, `Minus`, `Equal` |
  | k16, k17, k18, k19 | `M`, `Z`, `G`, `C` | `M`, `Z`, `X`, `C` | `Ctrl`, `C`, `M` (secondary `B` at 3.0 mm), `Hypershift` |
  | k20 | `Space` | `Space` | `Alt` |
  | top_button | `Alt` | `Alt` | `Space` |
  | dpad up, right, down, left | `3`, `4`, `5`, `6` | `W`, `D`, `S`, `A` | `W`, `D`, `S`, `A` |
  | wheel up, down, click | `H`, `V`, `N` | `H`, `V`, `N` | `PageUp`, `PageDown`, `NumLock` |

  The table is the whole definition; the spec's "Layouts" section is the source if a cell is unclear. Unlisted controls (diagonals, anything not above) are left out of `bindings` and keep the factory key.

- [ ] **Step 4: Run** `python3 -m unittest tests.test_starters 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit** `git add py_modules/tartarus/starters.py tests/test_starters.py && git commit -m "feat: starter profile definitions"`

---

### Task 2: Build profiles from starters; first-run config

**Files:**
- Modify: `py_modules/tartarus/config.py` (`default_config` area ~line 132, `load_config` ~line 187)
- Test: `tests/test_config.py`, `tests/test_starters.py`

**Interfaces:**
- Consumes: `STARTERS`, `Starter` from Task 1; `next_leds`, `new_profile_id`, `factory_bindings`.
- Produces:
  - `profile_from_starter(s: Starter, profile_id: str, name: str, leds: Tuple[bool, bool, bool]) -> Profile` — fresh dicts every call (never aliases the starter), `dpad_mode="4way"`, bindings = `factory_bindings()` updated from `s.bindings`, `actuation`, `secondary` (as `Secondary(binding, mm)`) and `hypershift` (a `Hypershift` with `bindings` only) filled.
  - `first_run_config() -> Config` — `default_config()` plus one profile per starter, in order, id from `new_profile_id`, name `s.name`, leds from `next_leds`, built one at a time so each call sees the previous.
- `default_config()` stays the one-profile config: many tests use it as a base. `load_config` returns `first_run_config()` for the missing-file and corrupt-file cases only.

- [ ] **Step 1: Write the failing tests.**
  In `tests/test_starters.py`, class `BuildProfileTest`:
  - `test_profile_from_starter_mmo`: result has `bindings["k19"].type == "hypershift"`, `hypershift_key(p) == "k19"`, `p.hypershift.bindings["k02"] == parse_binding_text("Ctrl+1")`, `p.secondary["k18"] == Secondary(parse_binding_text("B"), 3.0)`, `p.actuation == {"k01": 2.5}`, an unlisted control (`dpad_up_right`) equals the factory binding, and every control in `ALL_CONTROLS` is present.
  - `test_copy_does_not_alias`: build twice; mutate the first's `bindings`, `actuation`, `hypershift.bindings` and `secondary`; the second and `find_starter("starter:mmo")` are unchanged.
  - `test_round_trips_through_the_settings_file`: `save_config`/`load_config` of a config holding all three built profiles returns equal profiles (guards that the definitions survive `_parse`'s validation, e.g. a dropped secondary).
  In `tests/test_config.py` (class with `self.path`, `_write`, `_backups`):
  - `test_missing_file_gives_the_starters`: `load_config(missing)` names are `["Default", "FPS – WASD", "FPS – D-pad", "MMO"]`, ids `["default", "p2", "p3", "p4"]`, four distinct LED patterns with Default `NO_LEDS`, and `c == first_run_config()`.
  - `test_corrupt_file_is_moved_aside_and_gets_the_starters`: write `"{nope"`; load; one backup exists; names as above.
  - `test_existing_file_gets_no_starters`: save `default_config()` (one profile); load; still only `["Default"]`; loading again after `save_config` still only Default.
  - `test_v1_file_gets_no_starters`: reuse the existing v1 fixture in this file; migrated config has one profile.
  - `test_deleted_starter_stays_deleted`: `first_run_config()`, remove "MMO", `save_config`, `load_config` → names are the other three; no `MMO` back.
  - Update the existing `test_missing_file_gives_defaults` (`self.assertEqual(c, default_config())`) to compare with `first_run_config()`.

- [ ] **Step 2: Run** both files → FAIL (`ImportError: first_run_config`).

- [ ] **Step 3: Implement** the two functions in `config.py` (import `STARTERS` from `.starters`; `first_run_config` appends and returns), and change the two `return default_config()` lines in `load_config` (missing file, corrupt branch) to `first_run_config()`. Leave `_migrate_v1_file` alone.

- [ ] **Step 4: Run the suite.** Other tests that load a missing/corrupt file through `TartarusService` (grep `tests/` for services started without writing settings, and `test_service.py` profile-count expectations) may now see four profiles; fix each by writing settings first with `save_config(path, default_config())` or by updating the expected count. Do not change production code to satisfy them. Expected: ends in `OK`.

- [ ] **Step 5: Commit** `git add -A py_modules tests && git commit -m "feat: a fresh install starts with the three starter profiles"`

---

### Task 3: Engine pins for the MMO layer

**Files:**
- Test: `tests/test_engine_hypershift.py` (reuse its rig/helpers; read the file first)

**Interfaces:**
- Consumes: `profile_from_starter`, `find_starter`.

- [ ] **Step 1: Write the tests** (they should pass at once; they pin behaviour the spec asks the builder to confirm). With the MMO profile loaded into the engine as the other tests there do:
  - `test_mmo_hypershift_layer_sends_ctrl_number`: hold `k19`, press `k02` → output `Ctrl+1` (Ctrl down, `1` down/up, Ctrl up per that file's helper); release `k19`, press `k02` → plain `1`.
  - `test_mmo_k18_secondary_falls_through_on_the_layer`: with `k19` held, a press of `k18` to 1.5 mm gives `M` and a deep press (≥ 3.0 mm depth) gives `B`, same as without Hypershift.
  - `test_mmo_k19_has_no_secondary`: `"k19" not in profile.secondary`.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_engine_hypershift 2>&1 | tail -3` → `OK`. If a case fails, the cause is the definition (Task 1) or an engine fact the spec got wrong; fix the definition, or stop and tell the user if the engine must change.

- [ ] **Step 3: Run the suite**, then commit `git add tests && git commit -m "test: pin the MMO Hypershift layer and k18 fall-through"`.

**Milestone S1 end.** Deck check S1 (sonnet subagent, brief above): with the live settings moved aside, start Decky/the plugin; report (1) Profiles page lists Default, FPS – WASD, FPS – D-pad, MMO with four different LED patterns and no overflow; (2) Edit keys on MMO shows k19 as Hypershift and the Hypershift switch shows Ctrl+1… on k02; (3) the en dash renders in the row and the card title (if not, report; the fallback is a plain hyphen in `starters.py` names, spec "Open points"); (4) live settings restored. Then **stop**: commit, `/clear`, `/model sonnet`.

---

### Task 4: Create a profile from a starter

**Files:**
- Modify: `py_modules/tartarus/service.py` (`create_profile` ~line 770, `state()` ~line 538)
- Test: `tests/test_service_profiles.py`

**Interfaces:**
- Consumes: `find_starter`, `STARTER_PREFIX`, `profile_from_starter`, `clean_name`, `next_leds`, `new_profile_id`.
- Produces: `create_profile(name: str, copy_from_id: str) -> str` accepts either a profile id or a `starter:<slug>` id. `state()` gains `"starters": [{"id": str, "name": str}, ...]` in `STARTERS` order. `main.py` needs no change (it passes the id through); confirm that by reading it.

- [ ] **Step 1: Write the failing tests** in `ProfileSwitchTest`-style classes in `test_service_profiles.py` (reuse `write_settings`, `Rig`, `until`):
  - `test_create_from_starter_copies_it`: `svc.create_profile("My MMO", "starter:mmo")` returns an id; that profile's `bindings["k19"].type == "hypershift"`, `hypershift.bindings["k02"] == parse_binding_text("Ctrl+1")`, `secondary["k18"].actuation == 3.0`; `leds` is the next free pattern; saved file reloads with it.
  - `test_editing_the_copy_leaves_the_starter_alone`: create from `starter:fps-wasd`, `set_binding` on the copy's `k02`, then create a second copy under another name and its `k02` is still `2`... use `1` per the definition.
  - `test_starter_copy_errors_change_nothing`: at 8 profiles (`svc._config.profiles.extend(...)` as the existing limit test does) → `ValueError`; a name already taken (e.g. `"Default"`) → `ValueError`; `"starter:nope"` → `ValueError`; in each case `len(profiles)` and the saved file are unchanged.
  - `test_state_lists_the_starters`: `svc.state()["starters"] == [{"id": "starter:fps-wasd", "name": "FPS – WASD"}, {"id": "starter:fps-dpad", ...}, {"id": "starter:mmo", "name": "MMO"}]`.
  - `test_plain_copy_still_works`: existing behaviour for a profile id is unchanged (the existing tests cover it; run them).

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement.** In `create_profile`, when `copy_from_id.startswith(STARTER_PREFIX)`: look the starter up (`ValueError(f"unknown starter {copy_from_id!r}")` if missing), run the same limit and `clean_name` checks, build with `profile_from_starter(starter, new_profile_id(cfg), name, next_leds(cfg))`, append through `self._mutate` as the existing branch does. Share the limit/name checks between both branches rather than copying them. Add `"starters"` to `state()`.

- [ ] **Step 4: Run the suite** → `OK`.

- [ ] **Step 5: Commit** `git add -A py_modules tests && git commit -m "feat: create a profile from a starter"`

---

### Task 5: API types and the shared row styles

**Files:**
- Modify: `src/api.ts` (`State` ~line 57)
- Create: `src/editor/profileRows.tsx`
- Modify: `src/editor/ProfilesPage.tsx` (lines 13-35 move out)

**Interfaces:**
- Produces: in `api.ts`, `export type StarterInfo = { id: string; name: string };` and `State.starters: StarterInfo[]`. In `profileRows.tsx`, exports `ROW`, `ROW_CLASS`, `ROW_CSS`, `IN_USE` (the existing constants, moved verbatim) so `NewProfileModal` can draw rows that look like the Profiles list.

- [ ] **Step 1:** Add the type and field; move the four constants into `profileRows.tsx` and import them in `ProfilesPage.tsx`. No behaviour change.
- [ ] **Step 2:** Run the FE check → no errors, `0`.
- [ ] **Step 3: Commit** `git add -A src && git commit -m "refactor: share the profile row styles"`

---

### Task 6: New profile with "copy from"

**Files:**
- Create: `src/editor/NewProfileModal.tsx`
- Modify: `src/editor/ProfilesPage.tsx` (`create`, ~lines 46-62)

**Interfaces:**
- Consumes: `State`, `createProfile`, `errorText`, `ROW`/`ROW_CLASS`/`ROW_CSS` from `profileRows.tsx`.
- Produces: `NewProfileModal({ state, initialSourceId, onCreated, closeModal })` — `onCreated(s: State, name: string)` runs after a successful `createProfile(name, sourceId)`; the page then calls `onChanged(s)` and `onView(made.id)` as `create` does today.

- [ ] **Step 1: Implement `NewProfileModal`.** One modal (same `ModalRoot`, title, error line and Save/Cancel as `NameModal`): a `TextField` for the name, then a "Copy from" list inside a `Focusable flow-children="column"` with `maxHeight` about 260 and `overflowY: "auto"` so 8 profiles + 3 starters fit 1280×800. Rows are `DialogButton`s with `ROW` and the `ROW_CLASS`/`Tartarus_Selected` classes (colours stay in `ROW_CSS`, never inline). Order: the user's profiles (`state.profiles`), then a small non-focusable heading `Starter profiles` and the three `state.starters`. Selecting a row only sets the source; Save calls `createProfile(name, sourceId)`. The initial source is `initialSourceId` (the profile being viewed, as today). Save is disabled while busy; errors show as in `NameModal`.
- [ ] **Step 2:** In `ProfilesPage.create`, show `<NewProfileModal …/>` instead of `NameModal`; keep `NameModal` for rename. Drop the now-unused `source` variable only if nothing else uses it.
- [ ] **Step 3:** FE check → no errors, `0`.
- [ ] **Step 4: Commit** `git add -A src && git commit -m "feat: copy from a profile or a starter when creating a profile"`

**Milestone S2 end.** Deck check S2 (sonnet subagent, brief above), against the real Deck with settings backed up: (1) New profile opens, the list shows the user's profiles first and a `Starter profiles` heading with three starters, no clipping at 1280×800 even with many profiles (measure the modal's bounding box with the layout probe); (2) the list scrolls with the D-pad and A selects, B cancels; (3) creating `Test copy` from `MMO` adds a profile whose Edit keys shows k19 Hypershift and k18 with a secondary; (4) creating from a user profile still copies it; (5) at 8 profiles the New profile button is disabled; (6) the test profiles are deleted again and the live settings restored. Then **stop**: commit, `/clear`, `/model sonnet`.

---

### Task 7: Layout picture generator

**Files:**
- Create: `scripts/render_layouts.py`, `tests/test_render_layouts.py`
- Create (generated, committed): `docs/layouts/default.svg`, `fps-wasd.svg`, `fps-dpad.svg`, `mmo.svg`, `mmo-hypershift.svg`

**Interfaces:**
- Consumes: `STEAMOS_DEFAULT`, `factory_bindings`, `STARTERS`, `profile_from_starter`, the label function `binding_label` that `service.state()` uses (grep for its module).
- Produces (importable by file path; the script is not a package):
  - `labels_for(bindings: Mapping[str, Binding]) -> Dict[str, str]` — control → short label via `binding_label`.
  - `render_svg(title: str, labels: Mapping[str, str]) -> str` — one SVG: rows of 5, 5, 5, 4 keys numbered 01-19, the thumb key 20, the button above the D-pad, a D-pad cross with four direction labels, a wheel with up/down/click, a title. Every label is XML-escaped; a long label is shortened with an ellipsis to fit its key.
  - `all_pictures() -> Dict[str, str]` — filename → SVG text for the five files above; `mmo-hypershift.svg` shows the MMO's standard labels overlaid with its layer entries (the layer's `Ctrl+1` etc.), with `k19` labelled Hypershift.
  - `main(argv)`: no args writes the files into `docs/layouts/`; `--check` writes nothing and exits 1, printing the file names, if a committed file differs from `all_pictures()`.

- [ ] **Step 1: Write the failing tests** (`tests/test_render_layouts.py`, loading the script with `importlib.util.spec_from_file_location`):
  - `test_svg_is_valid_xml_and_labels_every_control`: `xml.etree.ElementTree.fromstring` parses each picture; the text of each of the 20 keys, the top button, the four D-pad directions and the three wheel controls appears in the picture for the starter (compare with `labels_for`).
  - `test_default_picture_matches_steamos_default`: for each `(control, text)` in `STEAMOS_DEFAULT`, the label of `parse_binding_text(text)` appears in `default.svg`'s text.
  - `test_labels_are_escaped`: a label `"A&B<"` yields valid XML containing `&amp;` and `&lt;`.
  - `test_committed_pictures_are_current`: for every `(name, svg)` in `all_pictures()`, the file `docs/layouts/<name>` exists and equals `svg`. This is the drift guard.
  - `test_hypershift_picture_shows_the_layer`: `mmo-hypershift.svg` contains the label of `Ctrl+1` and not as the label of a standard-layer-only picture.

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the script with stdlib only; theme colours dark card on light-neutral so it reads on GitHub's light and dark pages (give the SVG its own background rect). Then run `python3 scripts/render_layouts.py` to write the files and open one to check it by eye (render with `qlmanage -t -s 900 -o <scratchpad> docs/layouts/mmo.svg` on macOS and view the PNG).
- [ ] **Step 4: Run** the suite → `OK`.
- [ ] **Step 5: Commit** `git add -A scripts tests docs/layouts && git commit -m "feat: generate labelled layout pictures from the profile data"`

---

### Task 8: Reference doc

**Files:**
- Create: `docs/starter-profiles.md`
- Modify: `tests/test_render_layouts.py`

- [ ] **Step 1: Write the failing test** `test_reference_doc_covers_every_starter`: `docs/starter-profiles.md` contains each starter name, the picture path `layouts/<file>.svg` for each of the five files, the strings `Made for`, `starting points` and `not been tested in a game`, and for every control a starter binds, its row label (`k01`…, `top_button`, `dpad`, `wheel`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Write the doc.** Opening: one sentence on what starters are and how to get one (fresh install, or New profile → Copy from → Starter profiles), then "Made for": FPS starters → Call of Duty, Battlefield and Wardogs; MMO → World of Warcraft and RuneScape 3 (not Old School), with the spec's "Reference games" notes (C is hold-crouch in Wardogs and Battlefield, Left Ctrl in Call of Duty; Z is not shared so k17 is a spare to bind in-game; Q is ping in Battlefield; G is grenade in Call of Duty and Battlefield, bipod in Wardogs). Then, per starter, the picture and a table in the style of the README's Default layout block, columns Control / Binding / Usual use, with the usual labels (`-`, `=`, Page Up, Page Down, Num Lock). Content comes from the spec's "Layouts" tables. State in the doc: `FPS – D-pad` has no chat key; the MMO has no WoW default for the wheel (bind zoom in-game), Hypershift bar 2 needs `Ctrl+number` bound in the game, `k18`'s deep press is the one dual-stage demo and no ability should depend on it; starters are never re-applied and deleting one is permanent for that install.
- [ ] **Step 4: Run** the suite → `OK`.
- [ ] **Step 5: Commit** `git add docs/starter-profiles.md tests && git commit -m "docs: reference tables for the starter profiles"`

---

### Task 9: README

**Files:**
- Modify: `README.md` (Features ~line 9; Default layout ~line 101; Roadmap ~line 194)
- Modify: `tests/test_render_layouts.py`

- [ ] **Step 1: Write the failing test** `test_readme_links_the_pictures`: README contains `docs/layouts/default.svg` and `docs/starter-profiles.md`, and the sentence naming the games (`Call of Duty`, `Battlefield`, `Wardogs`, `World of Warcraft`, `RuneScape 3`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Edit.** Default layout: add the image above the text block (keep the block), and change "A fresh install starts with a Default profile…" to say a fresh install starts with Default plus three starter profiles. Add a "Starter profiles" section after it: one sentence on the three profiles, the "made for" games in one sentence, the Copy from flow, "never re-applied; an existing install keeps its own profiles", and the link to `docs/starter-profiles.md`. Add the Features bullet; remove any Roadmap line this finishes.
- [ ] **Step 4: Run** the suite → `OK`. Open the README preview once (`gh` or a markdown viewer) to confirm the images load.
- [ ] **Step 5: Commit** `git add README.md tests && git commit -m "docs: README section for the starter profiles"`

**Milestone S3 end.** No Deck check (docs and a generator only). Stop: commit, `/clear`, `/model sonnet`.

---

### Task 10: Screenshot shot list (user task)

This task does not take screenshots. It hands the user the list below, then waits.

- [ ] **Step 1: Print this list to the user**, with the note that each file goes under `docs/screenshots/` as `.jpg` like the existing ones, taken on the Deck on a fresh install (live settings backed up first).

  | # | Page | Must be visible | File | Goes in |
  |---|---|---|---|---|
  | a | Profiles | Default plus the three starters in the list | `starters-profiles.jpg` | README, Starter profiles section |
  | b | New profile | the Copy from list scrolled to the `Starter profiles` heading | `starters-copy-from.jpg` | README, Starter profiles section |
  | c | Customize on `FPS – WASD` | all keys, standard layer | `starter-fps-wasd.jpg` | `docs/starter-profiles.md`, FPS – WASD |
  | d | Customize on `FPS – D-pad` | all keys, standard layer | `starter-fps-dpad.jpg` | `docs/starter-profiles.md`, FPS – D-pad |
  | e | Customize on `MMO`, standard layer | all keys | `starter-mmo.jpg` | `docs/starter-profiles.md`, MMO |
  | f | Customize on `MMO`, Hypershift layer | the layer showing `Ctrl+…` | `starter-mmo-hypershift.jpg` | `docs/starter-profiles.md`, MMO |
  | g | Actuation page on `MMO` | `k18` with its secondary B | `starter-mmo-k18.jpg` | `docs/starter-profiles.md`, MMO notes |
  | h | Customize on Default | all keys | `default-customize.jpg` | README, Default layout |

- [ ] **Step 2: Describe the follow-up** (a short step for a later session, after the files exist): add each image to the file and place named in the table, check the paths resolve, run the suite, commit `docs: screenshots for the starter profiles`. Nothing in the repo is a placeholder, so there is nothing to remove unless the user adds one.
- [ ] **Step 3:** Tell the user the branch is ready for review/PR once the screenshots are in (or without them), then **stop**.

---

## Self-review notes

- Spec coverage: goals 1 → T1; 2 → T4-6; 3, 4 → T2 (+ T4 for existing installs reading starters from code); 5 → T7, T9; 6 → T8-9; 7 → T10. Reference games and "must say this" → T8-9 and the Global Constraints. Open points: ids (T1/T4), fresh-config function (T2: separate `first_run_config`, `default_config` unchanged), key names (T1/T8), D-pad has no chat key (T1/T8), k18 fall-through (T3), corrupt file (T2).
- Types: `Starter`, `profile_from_starter(s, profile_id, name, leds)`, `first_run_config()`, `StarterInfo`, `State.starters` and `NewProfileModal` props are named the same in every task that uses them.
- The Deck checks touch the user's real settings; the brief requires a backup and a restore.
