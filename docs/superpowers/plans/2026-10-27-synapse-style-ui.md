# Synapse-style Editor and Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the M5 editor UI (Tasks 16-18 of the analog plan) with a Steam-Settings-style editor (Customize / Actuation / Lighting / Profiles) that fits the Deck's 1280×800 screen with no scrolling, and reorder the Quick Access panel.

**Architecture:** The editor route becomes a `SidebarNavigation` with four pages. Customize and Actuation share the existing `Keypad` drawing (resized to the page height) with a card on the right; Choose…, Deep press and Lights open as in-page sub-pages (or a modal for Lights). The backend gains `lighting.enabled` with `set_lighting_enabled`, and `set_actuation_keys` built on `_apply_actuation`. Lighting controls and the status-light drawing become shared components used by both the panel and the editor.

**Tech Stack:** Python 3 stdlib (`unittest`, `asyncio`), TypeScript + React with `@decky/ui` 4.11 / `@decky/api` (pnpm, rollup).

**Spec:** `docs/superpowers/specs/2026-10-27-synapse-style-ui-design.md`. Mockups: `.superpowers/brainstorm/84389-1793111837/content/editor-v2.html` (git-ignored). Read both before any task. The spec's *Builder's call* lines are settled; don't reopen them.

## Milestones

| Milestone | Tasks | Done when |
|---|---|---|
| M5a Layout spike | 1 | FE check clean; user measures it on the Deck (Deck check M5a). **Stop.** |
| M5b Backend lighting switch + Quick Access panel | 2-4 | Suite green; FE check clean; Deck check M5b. **Stop.** |
| M5c Customize page | 5-7 | FE check clean; Deck check M5c. **Stop.** |
| M5d Actuation, Lighting and Profiles pages | 8-11 | Suite green; FE check clean; Deck check M5d. **Stop.** |
| M5e Rewritten M5 Deck check + final review | — | Deck check M5e passes; final whole-branch review (Opus). **Stop.** |

At each stop: commit, write the ledger line, tell the user to `/clear` and start the next milestone from this file.

**Model:** Opus for everything, including subagents (pass `model: "opus"` explicitly). This is the user's instruction for this plan and overrides the Sonnet default in their CLAUDE.md.

**Workspace:** run in place on branch `synapse-captures` (no worktree), as the analog plan was. Ledger: `.superpowers/sdd/2026-10-27-synapse-style-ui/progress.md`, with `plan-path` beside it holding this plan's path (`.superpowers/` is excluded in `.git/info/exclude`). Ledger lines: `Task N: complete (commits a..b, tests: <cmd> → OK)`, `Task N: Ruling: <what> — <why> — cost if wrong: <…>`, `Deck check M5x: pass|fail (user, date): <notes>`. Before Task 1, create the ledger and copy in this carried-over ruling from `.superpowers/sdd/2026-10-27-analog-and-profile-leds/progress.md`:
`Carried over (analog Task 17): Ruling: single recorder — the picker that started recording last owns the record_result; any other one waiting goes idle.`

**Commands.**
- Suite: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3` → ends in `OK` (211 tests at the start).
- FE check: `pnpm build 2>&1 | grep -iE "error|\(!\)"; pnpm exec tsc --noEmit -p . 2>&1 | grep -c "^src/"` → no lines from the first, `0` from the second.
- Deploy: `scripts/deploy.sh <host>`, then the user runs the printed `sudo cp`. Claude can read the log over ssh: `ssh <host> 'tail -n 200 ~/homebrew/logs/decky-tartarus/*.log'`.

**Hardware checks.** Every Deck check is a checklist the user runs. No step in this plan adds a new kind of send: lighting off is the existing effect + brightness reports with brightness 0 (the brightness slider already reaches 0).

## Global Constraints

- UI copy: "actuation", "Deep press" (control id stays `kNN.b`; code keeps the existing `secondary` names). Never "analog" or "Hypershift" in the UI.
- No page needs scrolling or puts anything behind the footer on 1280×800. The only allowed scrolling is the Profiles list inside its card.
- Every control works with the D-pad and A/B: groups are `Focusable` with `flow-children`, as the current editor does.
- If space runs short: shrink the drawing first (labels ≥ 11 px on screen), then hide the sidebar page title (`hideTitle`), and only then consider dropping `SidebarNavigation` (user decision at a stop).
- `SidebarNavigation` (4.11) has no slot under the menu, so the "Editing" dropdown and the "Keypad uses … now" line sit in a slim row at the top of Customize and Actuation only.
- Status lights are drawn in their real colours: top `#ffb02e` (orange), middle `#5cff3b` (green), bottom `#2ec5ff` (blue), unlit `#2a3038`. These are the colours already in `Keypad.tsx`'s drawing.
- Settings stay `SCHEMA_VERSION = 2`; `lighting.enabled` is optional, default `true`. Writes stay atomic via `save_config`. Every active-profile change still goes through `engine.set_profile`.
- Actuation: k01-k20 only, 1.5-3.6 mm in 0.1 steps; values compared in tenths; a deep press is at least 0.5 mm deeper than its key.
- Single-recorder rule (carried over): only the picker that started a recording takes the result.
- Values come from backend state; a backend refusal shows its message in red (`#e05050`) where the action was taken.

## Spec notes (for the user to confirm)

1. **`set_lighting` while off.** The spec says `set_lighting` "is only reached while on". A debounced Mode/colour/brightness change sent just before the user switches Lighting off still arrives after the switch. Proposed fix (implemented in Task 2): while off, `set_lighting` stores the new effect, colour and brightness but the keypad stays dark (it sends the new effect at brightness 0). On sends the stored settings.
2. **Actuation slider start value.** "Starts at the selected keys' value, or the first selected key's value when they differ" doesn't say what happens when keys are added after the slider was moved. Proposed rule (Task 9): the slider resets to the first selected key's value when the selection goes from empty to non-empty and when the edited profile changes; adding or removing keys from a non-empty selection leaves the slider where it is.

## Review Focus

1. **A Lighting change still in its debounce when the user switches Lighting off.** The keypad must stay dark and the change must be kept for when Lighting comes back on. Test in Task 2 (`test_set_lighting_while_off_stays_dark`).
2. **Lighting is off while the keypad is unplugged, asleep or the plugin restarts.** On connect and resume it must come back dark with the profile LEDs lit, and a restart must still show it off. Test in Task 2 (`test_lighting_off_survives_reconnect_resume_and_restart`).
3. **Apply to selected where one key's deep press can't move.** Nothing changes for any key and the message is shown; bad control lists from the frontend (`[]`, `"k01"`, `["top_button"]`, `["k21"]`) are refused without a write. Tests in Task 8 (`test_set_actuation_keys_is_atomic`, `test_set_actuation_keys_rejects_bad_input`).
4. **Steam remounts the Quick Access panel whenever one of its dropdowns opens.** The Lighting section's expanded state and the lighting draft must survive the remount (module-level, like today's draft). Deck check M5b step e.
5. **Record started on the card, then the user opens Choose… or Deep press and records there.** The first recording is cancelled on unmount and only the new picker takes the result. Deck check M5c step f.

---

## M5a: Layout spike

### Task 1: Editor shell, resized drawing and the Customize card layout

The real shell that later tasks fill in, not a throwaway. Card rows are laid out with their real labels; only Choose… is wired (to a stub sub-page) so B-handling can be checked. Until M5c/M5d the editor can't edit bindings, actuation or profiles; the panel is unchanged.

**Files:**
- Create: `src/editor/layout.ts`, `src/editor/Card.tsx`, `src/editor/SubPage.tsx`, `src/editor/EditingRow.tsx`, `src/editor/CustomizePage.tsx`
- Modify: `src/editor/Editor.tsx` (rewrite), `src/editor/Keypad.tsx`

**Interfaces:**
- Produces:
  - `layout.ts`: `export const PAGE_HEIGHT: string` — the CSS height of a page's content area (start at `"calc(100vh - 190px)"`; the spike tunes it). `export const ERROR = "#e05050"`.
  - `Card({ title, children }: { title?: ReactNode; children: ReactNode })` — background `#14181d`, radius 6, padding `12px 14px`, title in `#5bd14a`, uppercase, 12 px (as the mockup's `.card`).
  - `SubPage({ title, onBack, children }: { title: string; onBack(): void; children: ReactNode })` — a `Focusable` filling the page with a "‹ Back" `DialogButton` and the title on top; `onCancel={(e) => { e.stopPropagation(); onBack(); }}` so B returns to the card instead of the sidebar.
  - `EditingRow({ state, profile, onView }: { state: State; profile: ProfileState; onView(id: string): void })` — one row: "Editing" + `Dropdown` of profiles (min width 200) + a line: "Keypad uses <active name> now" when `profile.id !== state.active_profile`, or "Not connected: changes apply when it's plugged in." when `!state.connected`.
  - `controlTitle(control: string): string` in `Keypad.tsx` — `"Key 05"`, `"Key 20"`, `"Wheel up"`, `"Wheel click"`, `"Wheel down"`, `"Top button"`, `"Thumbpad up"`, `"Thumbpad up-right"` … (`dpad_` → "Thumbpad", `_` → space/hyphen).
  - `Keypad(props: { profile: ProfileState; view: "bindings" | "actuation"; selected: readonly string[]; defaultMm: number; onSelect(control: string): void })`.
  - `CustomizePage(props: { state: State; profile: ProfileState; selected: string; onSelect(c: string): void; onView(id: string): void; onDpad(eight: boolean): void; onChanged(s: State): void })` — `onDpad` is the editor's `toggleDpad`.
  - `Editor` keeps `viewing` (edited profile id), `selected` (control, default `"k01"`) and `page` (`"customize" | "actuation" | "lighting" | "profiles"`).

- [ ] **Step 1: `Keypad.tsx`.** The outer box becomes `{ position: "relative", height: "100%", aspectRatio: "600 / 630", maxWidth: "100%", flexShrink: 0 }` (drop the `100vh - 200px` cap). Corner label font 11 px, binding label 13 px. `view: "bindings"`: every control focusable as today, corner shows the number and `2×` for a key with a deep press (no mm). `view: "actuation"`: only k01-k20 are `Focusable`; the wheel, top button and thumbpad boxes render as plain dimmed `div`s; each key shows its number and `(profile.actuation[c] ?? defaultMm).toFixed(1)` + `" mm"` as the big label. Selected look: `bindings` keeps the blue look; `actuation` uses border `2px solid #44b030`, background `rgba(46, 92, 30, 0.92)`. `selected` is an array so Actuation can select many.
- [ ] **Step 2: `Editor.tsx`.** Root `<div style={{ height: "100%", padding: "40px 0", boxSizing: "border-box" }}>` (header and footer are ~40 px each) holding `<SidebarNavigation title="Tartarus" showTitle pages={…} page={page} onPageRequested={setPage} />` with four pages, identifiers `customize`, `actuation`, `lighting`, `profiles`, titles "Customize", "Actuation", "Lighting", "Profiles", `padding: "compact"`. Customize's content is `CustomizePage`; the others are empty for now. Keep today's state loading, `EV_STATE` listener, `viewedProfile` fallback and the 4-way diagonal fallback in `switchView`/`toggleDpad`.
- [ ] **Step 3: `CustomizePage.tsx`.** A column of height `PAGE_HEIGHT`: `EditingRow`, then a row with the drawing (height = the rest) and a `Card` (`flex: 1, minWidth: 300`). The card: `controlTitle(selected)`, the binding label at 22 px bold, then `Field` rows with their real labels: "Binding" → `Choose…`, "Record from a key" → `Record`, `Factory default (<factory>)` → `Reset` (when `factory` is set), "Deep press" → `<label> · <x.x> mm ›` or `Off ›` (k01-k20 only), and `ToggleField` "8-way D-pad" (when `selected` starts with `dpad_`). In this task only `Choose…` does anything: it opens `SubPage` titled "Choose a binding for <controlTitle>" holding the text "Stub", and Back/B returns to the card. Other buttons are no-ops.
- [ ] **Step 4: FE check clean.**
- [ ] **Step 5: Commit** `feat: editor layout spike with sidebar and resized drawing`

### Deck check M5a (user runs, then STOP)

Deploy, open the editor with the panel's "Edit keys" button. Then:
- a. Customize: the whole drawing shows (top row 01-05 and key 20 included), nothing sits behind the footer, and D-pad down from the card's last row doesn't scroll the page.
- b. Take a Steam screenshot (STEAM + R1) and send it (or tell Claude to fetch it over ssh). Claude measures: drawing height in px, corner-number height, card width, sidebar width, free space under the card.
- c. D-pad: sidebar → content → every key row, the wheel, top button, thumbpad and key 20 → right into the card rows → back.
- d. `Choose…` opens the stub; B returns to the card (not to the sidebar, not out of the editor). B on the card goes to the sidebar; B on the sidebar leaves the editor.
- e. Actuation, Lighting and Profiles show as empty pages and are reachable with the D-pad.

Record the numbers in the ledger. Decisions at this stop, in the spec's order: if it doesn't fit, lower `PAGE_HEIGHT` (labels ≥ 11 px); then `hideTitle: true` on the pages; only if both fail, ask the user about dropping `SidebarNavigation`. If B in step d leaves the sub-page wrongly, Choose… and Deep press become full-screen modals (`showModal` + `ModalRoot`, B closes them) — write that as a Ruling. **Stop; the user `/clear`s before M5b.**

---

## M5b: Backend lighting switch and Quick Access panel

### Task 2: `lighting.enabled` and `set_lighting_enabled` (TDD)

**Files:**
- Modify: `py_modules/tartarus/config.py` (`Lighting`, `_dump`, `_parse_lighting`), `py_modules/tartarus/service.py` (`_lighting_reports`, `_apply_lighting` log line, `state`, `set_lighting`, new `set_lighting_enabled`), `main.py`
- Test: `tests/test_config.py`, `tests/test_service_lighting.py`

**Interfaces:**
- Produces: `Lighting.enabled: bool = True`; `TartarusService.set_lighting_enabled(enabled: bool) -> None`; `state()["lighting"]` gains `"enabled": bool`; `Plugin.set_lighting_enabled(self, enabled: bool) -> dict` (returns state).

- [ ] **Step 1: Write the failing tests.** In `tests/test_config.py` (use the file's existing v2-file helpers):

```python
def test_lighting_enabled_defaults_true_for_old_file(self):
    # a v2 file whose "lighting" has no "enabled"
    self.assertIs(load_config(path).lighting.enabled, True)

def test_lighting_enabled_round_trip(self):
    c = default_config(); c.lighting.enabled = False; save_config(path, c)
    self.assertIs(json.loads(path.read_text())["lighting"]["enabled"], False)
    self.assertIs(load_config(path).lighting.enabled, False)

def test_lighting_enabled_not_bool_means_true(self):
    # "lighting": {..., "enabled": "no"} → True; effect/colour/brightness still parsed
```

In `tests/test_service_lighting.py` (same `Rig`/`FakeSender`/`TWO_NODES`/`until` pattern as `test_set_lighting_persists_and_applies`); `HID = "/dev/hidraw8"`:

```python
def test_lighting_off_sends_brightness_zero_and_keeps_brightness(self):
    # connected; set_lighting("static", "#ff0000", 40); sender.sent.clear()
    svc.set_lighting_enabled(False)
    self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#ff0000", 0) + [leds_report(NO_LEDS)]])
    self.assertEqual(svc.state()["lighting"], {"effect": "static", "color": "#ff0000", "brightness": 40, "enabled": False})
    lighting = load_config(self.path).lighting
    self.assertEqual((lighting.brightness, lighting.enabled), (40, False))

def test_lighting_on_resends_stored(self):
    # continuing from off: sender.sent.clear(); svc.set_lighting_enabled(True)
    self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#ff0000", 40) + [leds_report(NO_LEDS)]])

def test_set_lighting_while_off_stays_dark(self):
    # connected, set_lighting_enabled(False), clear; set_lighting("wave", "#00ff00", 70)
    self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("wave", "#00ff00", 0) + [leds_report(NO_LEDS)]])
    self.assertEqual(svc.state()["lighting"], {"effect": "wave", "color": "#00ff00", "brightness": 70, "enabled": False})

def test_lighting_off_survives_reconnect_resume_and_restart(self):
    # set_lighting_enabled(False) while disconnected → sender.sent == []
    # start + connect → sent == effect_reports("spectrum", "#00ff00", 0) + [leds_report(NO_LEDS)]
    # resume (rig.service._resume.check = lambda boottime, monotonic: True) → the same three reports again
    # stop; a new Rig on the same path → state()["lighting"]["enabled"] is False

def test_set_lighting_enabled_rejects_non_bool(self):
    # set_lighting_enabled("yes") and (1) → ValueError; settings file bytes unchanged; nothing sent
```

Update `test_state_has_lighting`'s expected dict to include `"enabled": True` (the state legitimately grew).

- [ ] **Step 2: Run them, expect failures** (`AttributeError: 'Lighting' object has no attribute 'enabled'` / no `set_lighting_enabled`).
Run: `python3 -m unittest tests.test_config tests.test_service_lighting 2>&1 | tail -3`
- [ ] **Step 3: Implement.** `_parse_lighting`: `enabled` is the stored value if it's a bool, else `True`. `_dump` writes `"enabled"`. `_lighting_reports` sends `brightness if enabled else 0`. `set_lighting` keeps the current `enabled` when it builds the new `Lighting`. `set_lighting_enabled` checks `isinstance(enabled, bool)` (else `ValueError("enabled must be true or false")`), stores, `save_config`, `_apply_lighting()`, `_notify()`. `_apply_lighting`'s info line says `off` instead of the brightness while disabled. `main.py` gets the `set_lighting_enabled` callable returning `self.service.state()`.
- [ ] **Step 4: Suite green.**
- [ ] **Step 5: Commit** `feat: lighting on/off switch in the backend`

### Task 3: Shared lighting controls and status lights

**Files:**
- Create: `src/lighting.ts`, `src/LightingControls.tsx`, `src/StatusLights.tsx`
- Modify: `src/api.ts`, `src/Panel.tsx`, `src/editor/Keypad.tsx`, every file importing `errorText` from `../Panel`

**Interfaces:**
- Consumes: Task 2's `set_lighting_enabled` and `lighting.enabled`.
- Produces:
  - `api.ts`: `LightingState` gains `enabled: boolean`; `setLightingEnabled = callable<[enabled: boolean], State>("set_lighting_enabled")`; `errorText(e: unknown): string` moves here from `Panel.tsx` (same body).
  - `StatusLights.tsx`: `export const LED_COLOURS = ["#ffb02e", "#5cff3b", "#2ec5ff"]`, `export const LED_UNLIT = "#2a3038"`, `StatusLights({ leds, size = 8 }: { leds: readonly boolean[]; size?: number })` — three dots in a column, top first, gap `size / 3`. `Keypad.tsx`'s drawing uses `LED_COLOURS` instead of its inline array.
  - `lighting.ts`: the module-level store moved out of `Panel.tsx` (draft, error, debounce 250 ms, `writing` counter, listeners), plus `expanded` (starts `false`). Exports `syncLighting(s: State): void` (takes `s.lighting` unless a write is pending or in flight), `useLighting(): { draft: LightingState | null; error: string | null; expanded: boolean; change(patch: Partial<Omit<LightingState, "enabled">>): void; setEnabled(on: boolean): void; setExpanded(open: boolean): void }`. `setEnabled` updates the draft at once and calls `setLightingEnabled`; on error it shows the message and restores `enabled` from the returned/next state.
  - `LightingControls({ effects, collapsible }: { effects: string[]; collapsible: boolean })` — rows (`PanelSectionRow`): `ToggleField` "Lighting"; when on and `collapsible`, a `ButtonItem layout="inline"` whose label is `<Mode> · <brightness>%` and whose button shows `FaChevronDown`/`FaChevronUp`, toggling `expanded`; when on and (expanded or not collapsible): `DropdownItem` "Mode" (effects capitalised), the swatches for colour modes (`COLOURLESS = spectrum, wave`, as today), `SliderField` "Brightness" 0-100 step 5 `%`; the error line "Not applied: …". When off, nothing below the toggle.

- [ ] **Step 1: Implement** the files above. `Panel.tsx` keeps its current rows for now but renders its Lighting `PanelSection` as `<LightingControls effects={state.effects} collapsible />` (hidden while `effects` is empty, as today), and calls `syncLighting` on `getState()` and on every `EV_STATE`.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: shared lighting controls with an on/off switch`

### Task 4: Quick Access panel order and gear title

**Files:**
- Modify: `src/index.tsx`, `src/Panel.tsx`

**Interfaces:**
- Consumes: Task 3's `StatusLights`, `LightingControls`, `syncLighting`.
- Produces: `openEditor(): void` exported from `Panel.tsx` (`Navigation.Navigate(EDITOR_ROUTE)` then `Navigation.CloseSideMenus()`).

- [ ] **Step 1: Implement.**
  - `index.tsx` `titleView`: `<div className={staticClasses.Title} style={{ display: "flex", alignItems: "center", width: "100%" }}>Tartarus` + a `DialogButton` (`marginLeft: "auto"`, 28×28, `minWidth: 0`, `padding: 0`) with `FaCog` calling `openEditor`.
  - `Panel.tsx`, one `PanelSection` with no title, in this order: connection (unchanged text and USB ID); profile — with a running game a `DropdownItem` "<game> uses:" whose option labels are `<span style={{ display: "flex", alignItems: "center", gap: 8 }}><StatusLights leds={p.leds} size={6} />{name}</span>` (Default keeps "(default)"), otherwise a row "Keypad uses <name>" with its `StatusLights`; then `LightingControls collapsible`. Remove the "Layout:" line, the Adjustable actuation switch (moves to the Actuation page in Task 9) and the "Edit keys" button.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: Quick Access panel in the new order with a settings icon`

### Deck check M5b (user runs, then STOP)

Deploy. Then:
- a. Panel from the top: "Tartarus" with the gear; connection with USB ID; with no game running "Keypad uses Default" with its (unlit) lights; Lighting toggle. No Adjustable actuation switch, no Edit keys button.
- b. The gear opens the editor and closes the side menu.
- c. Start a game: "<game> uses:" dropdown; each option shows its lights in colour; picking one changes the keypad's status lights.
- d. Lighting off → backlight dark, status lights stay as they were; on → the previous mode and brightness return. Off again, then suspend/resume, replug, and reload the plugin → still dark, toggle still off; turn it back on.
- e. Expand the arrow, open "Mode" and pick another mode → the section stays expanded (panel remount); swatches only for modes with a colour; brightness works.

Ledger line, then **stop; the user `/clear`s before M5c.**

---

## M5c: Customize page

### Task 5: Record button and Choose page (replacing BindingPicker)

**Files:**
- Create: `src/editor/RecordButton.tsx`, `src/editor/ChoosePage.tsx`
- Modify: `src/editor/CustomizePage.tsx`, `src/editor/quickPicks.ts` (only if grouping needs a helper)
- Delete: `src/editor/BindingPicker.tsx`

**Interfaces:**
- Consumes: Task 1's `SubPage`, `Card`, `controlTitle`.
- Produces:
  - `RecordButton({ control, profile, onChanged, onError }: { control: string; profile: ProfileState; onChanged(s: State): void; onError(msg: string | null): void })` — the recording half of today's `BindingPicker`, unchanged in behaviour: module-level `recordOwner`/`nextPickerId` (single-recorder rule), "Press a key or combo…" + Cancel while recording, "Nothing recorded" after a timeout, `recordCancel()` on unmount and on control/profile change.
  - `ChoosePage({ control, state, profile, onChanged, onDone }: { control: string; state: State; profile: ProfileState; onChanged(s: State): void; onDone(): void })` — inside a `SubPage` titled `Binding for <controlTitle(control)>` (for `kNN.b`: `Deep press for Key NN`). Sections: "Keys" (quick picks that are neither F-keys nor `steam:`), a "More keys…"/"Fewer keys" toggle showing the F-keys, "Steam" (the `steam:` picks; hidden with today's note when `steam_mode === "disabled"`), and "Type a binding" (`TextField`, the examples line, `Apply` disabled while `text.trim() === ""`). A pick or a successful Apply calls `setBindingText`, then `onChanged` and `onDone()`; a refusal stays on the page with the message in red.

- [ ] **Step 1: Implement**, and wire the card: `Choose…` opens `ChoosePage` for `selected` (replacing the stub), "Record from a key" uses `RecordButton`, `Reset` calls `setBindingText(profile.id, selected, factory)`. Card errors show in red under the rows.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: Choose page and Record in the Customize card`

### Task 6: Deep press page

**Files:**
- Create: `src/editor/useDebounce.ts`, `src/editor/DeepPressPage.tsx`
- Modify: `src/editor/CustomizePage.tsx`
- Delete: `src/editor/ActuationSettings.tsx`

**Interfaces:**
- Consumes: Task 5's `RecordButton`, `ChoosePage`.
- Produces:
  - `useDebounce(ms: number): { schedule(run: () => void): void; flush(): void; isPending(): boolean }` — moved from `ActuationSettings.tsx` unchanged except for the `ms` parameter.
  - `DeepPressPage({ control, state, profile, onChanged, onBack }: { control: string; state: State; profile: ProfileState; onChanged(s: State): void; onBack(): void })` — a `SubPage` titled `Deep press · <controlTitle(control)>`.

- [ ] **Step 1: Implement.** The page: `ToggleField` "Deep press" (on → `setSecondary(profile.id, control, state.actuation.max_mm)`, off → `setSecondary(…, null)`); when on, a `Field` "Binding: <label>" with `Choose…` (opens `ChoosePage` for `control + ".b"`; its Done/B returns to this page, not the card) and `RecordButton` for `control + ".b"`; `SliderField` `Depth: x.x mm`, min `min(A + min_gap_mm, max_mm)` where A is `profile.actuation[control] ?? default_mm`, max `max_mm`, step 0.1, debounced 300 ms, flushed on unmount and on control/profile change (today's `ActuationSettings` draft logic). While `state.actuation.status !== "on"`: the note "Applies only with Adjustable actuation on." (still editable). Backend refusals in red on this page. The card's "Deep press" row opens it and gets the same note as its `Field` description.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: Deep press page`

### Task 7: Card finish: 8-way toggle, editing switch, fit

**Files:**
- Modify: `src/editor/CustomizePage.tsx`, `src/editor/Editor.tsx`

- [ ] **Step 1: Implement.** The "8-way D-pad" `ToggleField` calls `onDpad` (the editor's `toggleDpad`) (diagonal → `dpad_up` fallback kept). Switching the edited profile in `EditingRow` closes any open sub-page (its flush runs on unmount). Check against M5a's measurements that the card's tallest case (a key with factory, Deep press and an error line) stays inside `PAGE_HEIGHT`; if not, shrink row padding, not fonts.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: finish the Customize card`

### Deck check M5c (user runs, then STOP)

Deploy. Using only the D-pad and A/B, on Customize:
- a. Key 05: card shows "Key 05" and its binding. `Choose…` → `Apply` is disabled while the text is empty; type `Ctrl+C`, Apply → back on the card, drawing label updated. `Choose…` → "Tab" → back. B on the Choose page → card.
- b. Record → press a keypad key → bound. Record → Cancel → idle. Record and wait → "Nothing recorded".
- c. `Reset` → factory binding.
- d. `Deep press ›` → toggle on → row reads `<label> · 3.6 mm`, drawing shows `2×`. Choose and Record the deep press. Set depth 3.4 and press B at once → row shows 3.4 (flush).
- e. Select a thumbpad direction → 8-way toggle; on → diagonals selectable; select one; switch Editing to a 4-way profile → selection falls back to "Thumbpad up".
- f. Start Record on the card, then open `Deep press ›` and press Record there, press a key → only the deep press gets it; the key's binding is unchanged.
- g. Editing dropdown: another profile → "Keypad uses <name> now". The page never scrolls and every row is reachable.

Ledger line, then **stop; the user `/clear`s before M5d.**

---

## M5d: Actuation, Lighting and Profiles pages

### Task 8: `set_actuation_keys` (TDD)

**Files:**
- Modify: `py_modules/tartarus/service.py`, `main.py`, `src/api.ts`
- Test: `tests/test_service_actuation.py`

**Interfaces:**
- Consumes: `_apply_actuation(profile, controls, mm)` (unchanged), `ACTUATION_KEYS`.
- Produces: `TartarusService.set_actuation_keys(profile_id: str, controls: Sequence[str], mm: float) -> None`; `Plugin.set_actuation_keys(self, profile_id: str, controls: list, mm: float) -> dict`; `api.ts`: `setActuationKeys = callable<[profileId: string, controls: string[], mm: number], State>("set_actuation_keys")`. `set_all_actuation` stays in the backend; `setAllActuation` is removed from `api.ts` (no caller after Task 6).

- [ ] **Step 1: Write the failing tests** (inside the existing actuation test class, using `self.connected()`):

```python
def test_set_actuation_keys(self):
    svc.set_actuation_keys("default", ["k01", "k07"], 2.0)
    self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"], {"k01": 2.0, "k07": 2.0})
    svc.set_actuation_keys("default", ["k01"], 1.5)
    self.assertEqual(svc.state()["profiles"][0]["actuation"], {"k07": 2.0})

def test_set_actuation_keys_moves_b(self):
    svc.set_secondary("default", "k05", 2.5)
    svc.set_actuation_keys("default", ["k05", "k06"], 2.3)
    p = svc.state()["profiles"][0]
    self.assertEqual((p["actuation"]["k05"], p["secondary"]["k05"]["actuation"]), (2.3, 2.8))

def test_set_actuation_keys_is_atomic(self):
    svc.set_secondary("default", "k05", 3.6)
    before = self.path.read_bytes()
    with self.assertRaisesRegex(ValueError, "k05's secondary function would pass 3.6 mm"):
        svc.set_actuation_keys("default", ["k04", "k05"], 3.2)
    self.assertEqual(self.path.read_bytes(), before)
    self.assertEqual(svc.state()["profiles"][0]["actuation"], {})

def test_set_actuation_keys_compares_tenths(self):
    svc.set_secondary("default", "k05", 3.1)
    svc.set_actuation_keys("default", ["k05"], 2.6000000000000005)
    p = svc.state()["profiles"][0]
    self.assertEqual((p["actuation"]["k05"], p["secondary"]["k05"]["actuation"]), (2.6, 3.1))

def test_set_actuation_keys_rejects_bad_input(self):
    before = self.path.read_bytes()
    for args in (("default", [], 2.0), ("default", "k01", 2.0), ("default", ["k21"], 2.0),
                 ("default", ["top_button"], 2.0), ("default", [1], 2.0), ("default", ["k01"], 3.7),
                 ("default", ["k01"], 2.55), ("default", ["k01"], True), ("nope", ["k01"], 2.0)):
        with self.assertRaises(ValueError, msg=args):
            svc.set_actuation_keys(*args)
    self.assertEqual(self.path.read_bytes(), before)
```

- [ ] **Step 2: Run them, expect** `AttributeError: … 'set_actuation_keys'`.
Run: `python3 -m unittest tests.test_service_actuation 2>&1 | tail -3`
- [ ] **Step 3: Implement.** Resolve the profile, then require `controls` to be a non-empty list or tuple of strings all in `ACTUATION_KEYS` (else `ValueError("controls must be keys 01-20")`), then `_apply_actuation(profile, tuple(controls), mm)`. Add the `main.py` callable and the `api.ts` export.
- [ ] **Step 4: Suite green; FE check clean.**
- [ ] **Step 5: Commit** `feat: set actuation for selected keys`

### Task 9: Actuation page

**Files:**
- Create: `src/editor/ActuationPage.tsx`
- Modify: `src/editor/Editor.tsx`

**Interfaces:**
- Consumes: Task 8's `setActuationKeys`; Task 1's `Keypad` (`view: "actuation"`), `EditingRow`, `Card`; `setAdjustableActuation`.
- Produces: `ActuationPage({ state, profile, onView, onChanged }: { state: State; profile: ProfileState; onView(id: string): void; onChanged(s: State): void })`.

- [ ] **Step 1: Implement.** Layout as `CustomizePage`. Selection is an ordered `string[]` of keys; pressing a key toggles it. Card titled `Actuation · N keys selected` (`1 key`), the line "Press depth that triggers the key.", `SliderField` `Depth: x.x mm` 1.5-3.6 step 0.1 (`tenth()` the value), with the start rule from Spec note 2. A `Focusable flow-children="row"` with `Select all` (k01-k20 in order), `Clear`, and `Apply to selected` (disabled while nothing is selected) → `setActuationKeys(profile.id, selection, value)`; selection stays after Apply; refusal in red. Then `ToggleField` "Adjustable actuation" (moved from the panel with its `ACTUATION_NOTES` descriptions and error line) and, while `state.actuation.status !== "on"`, "Applies only with Adjustable actuation on."
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: Actuation page with key selection`

### Task 10: Lighting page

**Files:**
- Modify: `src/editor/Editor.tsx`

- [ ] **Step 1: Implement.** The Lighting page is a `Card` titled "Lighting" holding `<LightingControls effects={state.effects} collapsible={false} />`. The editor calls `syncLighting` on `getState()` and each `EV_STATE`, as the panel does.
- [ ] **Step 2: FE check clean.**
- [ ] **Step 3: Commit** `feat: Lighting page in the editor`

### Task 11: Profiles page and Lights picker

**Files:**
- Create: `src/editor/ProfilesPage.tsx`, `src/editor/LightsModal.tsx`
- Modify: `src/editor/Editor.tsx`
- Delete: `src/editor/ProfileBar.tsx` (its New/Rename/Delete flows move here; `NameModal.tsx` stays)

**Interfaces:**
- Consumes: Task 3's `StatusLights`; `createProfile`, `renameProfile`, `deleteProfile`, `setLeds`; `NameModal`.
- Produces:
  - `ProfilesPage({ state, viewing, onEdit, onView, onChanged }: { state: State; viewing: string; onEdit(id: string): void; onView(id: string): void; onChanged(s: State): void })`. `onEdit` in `Editor` sets `viewing` and `page = "customize"`.
  - `LightsModal({ state, profile, onChanged, closeModal }: { state: State; profile: ProfileState; onChanged(s: State): void; closeModal?(): void })`.

- [ ] **Step 1: Implement.** A `Card` titled "Profiles" with one `Focusable flow-children="row"` row per profile: `StatusLights size={9}`, the name with a green "in use" pill when `p.id === state.active_profile`, a second line with the games joined by ", " ("Every game without its own profile" for Default, "No games" otherwise), and a `⋯` `DialogButton` that calls `showContextMenu(<Menu label={p.name}>…</Menu>, e.currentTarget)` with `MenuItem`s Edit keys, Lights (not Default), Rename, Delete (not Default). Rename and Delete keep `ProfileBar`'s modals and messages; after a delete the editor falls back as today. Below the list, `New profile` (disabled at `max_profiles`) with today's flow: copies the edited profile, then `onView(new id)`. The list gets `overflowY: "auto"` inside the card as the only scroll. `LightsModal`: a `ModalRoot` titled `Lights for <name>` with every `state.led_patterns` pattern as a `Focusable` tile drawing `StatusLights size={14}`; the profile's own pattern is marked "Current"; a pattern another profile uses shows that profile's name and is disabled (not focusable-activatable); picking a free one calls `setLeds`, then `onChanged` and `closeModal`; a refusal shows in red.
- [ ] **Step 2: FE check clean** (and no file still imports `ProfileBar`, `BindingPicker` or `ActuationSettings`).
- [ ] **Step 3: Commit** `feat: Profiles page with status-light picker`

### Deck check M5d (user runs, then STOP)

Deploy. Using only the D-pad and A/B:
- a. Actuation: every key shows its mm; the wheel, top button and thumbpad can't be selected. Select 05, 07, 08 → they turn green, slider at 05's value. 2.0, Apply → labels read 2.0 mm. `Select all` / `Clear`; Apply is disabled with nothing selected.
- b. Give key 05 a deep press at 3.6 (Customize). On Actuation select 04 and 05, set 3.2, Apply → red message, neither key changed.
- c. Adjustable actuation off → the note on Actuation, on Customize's Deep press row and on the Deep press page; back on.
- d. Lighting page: same controls as the panel, no arrow; off hides Mode, colour and brightness; a change here shows in the panel.
- e. Profiles: lights in colour, "in use", games. `⋯` on Default offers only Edit keys and Rename. Edit keys on another profile → Customize editing it. Lights → patterns in colour, used ones named and not pickable; pick one → status lights change if that profile is active. Rename; New profile until the limit (8) → the list fits or scrolls only inside its card; Delete with its confirm.
- f. Every page: no scrolling, nothing behind the footer, every control reachable.

Ledger line, then **stop; the user `/clear`s before M5e.**

---

## M5e: Rewritten M5 Deck check and final review

This replaces "Deck check M5" in `docs/superpowers/plans/2026-10-27-analog-and-profile-leds.md`. First edit that section to one line: `Superseded by Deck check M5e in docs/superpowers/plans/2026-10-27-synapse-style-ui.md.` and commit it (`docs: point the M5 Deck check at the new UI`).

### Deck check M5e (user runs; Claude asks before deploying)

Deploy. Using only the D-pad and A/B:
- a. **Key 05 actuation.** Actuation page: select only 05, set 2.5, Apply → 05 shows 2.5 mm. A press shallower than 2.5 mm does nothing; past it the key fires.
- b. **Key 05 deep press.** Customize → key 05 → `Deep press ›` → on, bind it with Record, depth 3.4 → the row reads `<label> · 3.4 mm` and the drawing shows `2×`. On the keypad a full press gives the deep press.
- c. **All/selected keys.** Set the deep press depth to its minimum (3.0). Actuation: `Select all`, 3.0, Apply → every key 3.0 mm and key 05's deep press moved to 3.5 (Customize row shows 3.5). Then select only 05, 3.2, Apply → refused with the message, nothing changed. Set all keys back to 1.5.
- d. **LED patterns.** Profiles → `⋯` → Lights on a non-Default profile → pick a free pattern → the keypad's status lights change when that profile is in use; patterns other profiles use are named and not pickable; the panel's "<game> uses:" options show the same colours.
- e. **Adjustable actuation off** (Actuation page) → the note shows on Actuation, the Deep press row and page; keys fire at the fixed hardware point and the deep press doesn't fire. Turn it back on.
- f. **M4's unconfirmed row e.** Key 12 = `C`, deep press `Z` at 3.6 (set in the UI). Half press → `C` held; full press → `C` released, `Z` held; back to half → `Z` released, no `C`; **release fully, then half press → `C`.**
- g. Every editor page fits with no scrolling and nothing behind the footer; every control is reachable.

On pass: ledger line, then the final whole-branch review with an `opus` subagent over `master..synapse-captures` against both specs. **Stop.**
