# Hypershift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A held Hypershift key per profile that switches the other controls to a second layer of bindings (with their own actuation and secondary functions), edited with a Standard / Hypershift switch, plus optional Hypershift lights.

**Architecture:** The Hypershift key is marked by a new binding type `hypershift` on the key's standard binding, so "giving it another binding turns Hypershift off" needs no extra code. Each profile gains a `Hypershift` block holding only the controls that have an entry (bindings, actuation, secondary). The engine records the layer each press started in and looks bindings and depth points up in that layer; layer entries are addressed through the API with a `.h` suffix (`k05.h`, `k05.h.b`) next to the existing `.b`. Hypershift lights hang off an engine `on_layer` callback in the service.

**Tech Stack:** Python 3 stdlib (`unittest`, `asyncio`), TypeScript + React with `@decky/ui` / `@decky/api` (pnpm, rollup).

**Spec:** `docs/superpowers/specs/2026-10-27-hypershift-design.md`. Read it before any task. Its *My call* lines and the decisions below are settled; don't reopen them.

## Milestones

| Milestone | Tasks | Done when |
|---|---|---|
| H1 Engine, config and service | 1-5 | Suite green; Deck check H1. **Stop.** |
| H2 Editor | 6-8 | Suite green; FE check clean; Deck check H2. **Stop.** |
| H3 Hypershift lights | 9-11 | Frame check recorded (Task 9); suite green; FE check clean; Deck check H3; final whole-branch review (Opus). **Stop.** |

At each stop: commit, write the ledger line, tell the user to `/clear` and start the next milestone from this file with `/model sonnet`.

**Model:** subagents run on `sonnet` (pass `model` explicitly); `haiku` for mechanical lookups; `opus` only for the final whole-branch review after H3.

**Workspace:** before Task 1, `git switch -c hypershift` from `hypershift-spec` (no worktree). Ledger: `.superpowers/sdd/2026-10-27-hypershift/progress.md`, with `plan-path` beside it holding this plan's path (`.superpowers/` is excluded in `.git/info/exclude`). Ledger lines: `Task N: complete (commits a..b, tests: <cmd> → OK)`, `Task N: Ruling: <what> — <why> — cost if wrong: <…>`, `Deck check Hx: pass|fail (date): <notes>`.

**Commands.**
- Suite: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3` → ends in `OK`.
- One file: `python3 -m unittest tests.test_engine_hypershift 2>&1 | tail -3`.
- FE check: `pnpm build 2>&1 | grep -iE "error|\(!\)"; pnpm exec tsc --noEmit -p . 2>&1 | grep -c "^src/"` → no lines from the first, `0` from the second.
- Deploy: `scripts/deploy.sh <host>`, then the user runs the printed `sudo cp`. Plugin log: `ssh <host> 'tail -n 200 ~/homebrew/logs/decky-tartarus/*.log'`.

**Deck checks.** One per milestone, batched. Claude has no sudo on the Deck, so the hands-on steps are a checklist the user runs; the measurable part goes to **one `sonnet` subagent** with a narrow brief: deploy prep, the CEF layout probe (see memory "deck-cef-layout-probe": `http://127.0.0.1:8080/json` over `ssh deck@steamdeck.local`, 534 CSS px tall at 1.5× zoom), and a log scan. It writes findings to `.superpowers/sdd/2026-10-27-hypershift/deck-Hx.md` and returns pass/fail plus a short list. The main thread records the result in the ledger.

## Global Constraints

- Names: *Hypershift* and *secondary function* never mix. Code, state, API and UI say `hypershift` / "Hypershift" for the layer and key, and keep `secondary` / "Secondary function" for the deeper binding in one press. A layer key's secondary function is "the Hypershift entry's secondary function", never "Hypershift secondary" as a type or field name.
- Hypershift keys: `k01`-`k20` and `top_button` only (`HYPERSHIFT_KEYS`). Never the wheel or the D-pad.
- At most one Hypershift key and one layer per profile. No latch/toggle mode.
- Config stays `SCHEMA_VERSION = 2`. The per-profile `hypershift` block and the lighting fields are optional; absent means no entries and lights off. Files saved before this change load unchanged and behave as today.
- Actuation: `k01`-`k20` only, 1.5-3.6 mm in 0.1 steps, compared in tenths; a secondary function sits at least 0.5 mm deeper than its key's point *in the same layer*.
- No stuck key: every output code released goes through the existing refcounts (`_held`, `_counts`), never re-derived from the current layer.
- Every active-profile change, Record and passthrough still go through `release_all`, which also returns the layer to standard.
- Editor pages fit 1280×800 with no scrolling and work with the D-pad and A/B (`Focusable` + `flow-children`). CSS Loader look; existing `Card` / `Row` components; refusals in red `#e05050` where the action was taken.
- Hypershift accent colour: `#ff6000` (the orange swatch). Hypershift lights default colour: `#ff6000`; faint keys: `#262626` (about 15 % white).
- No Hypershift view in the Quick Access panel.

## Decisions (left to the builder by the spec)

1. **Marking the key:** binding type `hypershift` (`Binding("hypershift")`, text `hypershift`, label `Hypershift`). The profile's Hypershift key is the one control whose standard binding has that type. The type is valid only on a standard, non-secondary binding of a `HYPERSHIFT_KEYS` control.
2. **Config shape:** `Profile.hypershift: Hypershift` with `bindings: Dict[str, Binding]` (controls with an entry), `actuation: Dict[str, float]` (entry keys away from `DEFAULT_MM`), `secondary: Dict[str, Secondary]` (entry keys only). On disk: `"hypershift": {"bindings": {...}, "actuation": {...}, "secondary": {...}}` per profile.
3. **API addressing:** `X.h` is control X's Hypershift entry, `kNN.h.b` that entry's secondary function. The existing callables take these; one new callable, `clear_hypershift_entry`.
4. **New entry defaults:** a key's new entry starts at the key's standard depth (copied when it isn't `DEFAULT_MM`) and with no secondary function.
5. **Engine:** the layer is decided at press start and stored per press; depth keys re-target their tracker to the active layer only while idle.
6. **Choose…:** a "Hypershift" category just above "Disable", shown only on the standard layer for `HYPERSHIFT_KEYS`.
7. **Hypershift key on the Hypershift layer:** shown locked (orange, not focusable) in the drawing. If it is the selected control when you switch layers, the card says "Key 19 is the Hypershift key. Hold it to use this layer." with nothing to edit.

## Review Focus

1. **Hypershift key released before a layer key** (hold 19, press E→F1, let go of 19, then E): F1 stays down until E comes up, then goes up; nothing else stays down. → Task 3 `test_layer_binding_released_after_hypershift_up`.
2. **Hypershift key pressed while a depth key is between its standard and Hypershift points**: the key's current press keeps its standard thresholds and secondary function; only its next press uses the layer's. → Task 4 `test_depth_press_keeps_its_layer_points`.
3. **Editing the active profile while the Hypershift key is held** (`_edited` → `set_profile` → `release_all`): everything goes up, the layer is standard, and the still-held Hypershift key does not re-arm until it's released (tracker blocked). → Task 4 `test_set_profile_while_hypershift_held`.
4. **A hand-edited or older settings file with two `hypershift` bindings, or one on the wheel**: first valid key in `ALL_CONTROLS` order wins, the others get their factory binding; the file still loads. → Task 2 `test_parse_extra_hypershift_keys_reset`.
5. **Copying a profile then editing the copy's layer**: the source's layer is unchanged (no shared dicts). → Task 5 `test_create_profile_copies_hypershift_deeply`.

---

## H1: Engine, config and service

### Task 1: Control addressing and the `hypershift` binding type

**Files:**
- Create: `py_modules/tartarus/layers.py`
- Modify: `py_modules/tartarus/bindings.py` (BINDING_TYPES, `parse_binding_text`, `binding_to_dict`, `binding_from_dict`, `binding_label`)
- Modify: `py_modules/tartarus/devmap.py` (add `HYPERSHIFT_KEYS`)
- Modify: `py_modules/tartarus/engine.py` (import `B_SUFFIX` from `layers` instead of defining it, so `from .engine import B_SUFFIX` keeps working)
- Test: `tests/test_layers.py`, `tests/test_bindings.py`

**Interfaces:**
- Produces:
  - `devmap.HYPERSHIFT_KEYS: Tuple[str, ...] = ACTUATION_KEYS + ("top_button",)`
  - `layers.B_SUFFIX = ".b"`, `layers.H_SUFFIX = ".h"`, `layers.STANDARD = "standard"`, `layers.HYPERSHIFT = "hypershift"`
  - `layers.ControlRef` — frozen dataclass `(base: str, layer: str, slot: str)`, slot `"a"` or `"b"`
  - `layers.parse_control(control: str) -> ControlRef` — raises `ValueError(f"unknown control {control!r}")`. Accepts `X` and `X.h` for X in `ALL_CONTROLS`; `kNN.b` and `kNN.h.b` for `ACTUATION_KEYS`. Nothing else (`k05.b.h`, `wheel_up.b`, `k05.h.h`).
  - `Binding("hypershift")`: text `hypershift` (any case), dict `{"type": "hypershift"}`, label `"Hypershift"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_layers.py
class ParseControlTest(unittest.TestCase):
    def test_standard_and_layer_forms(self):
        self.assertEqual(parse_control("k05"), ControlRef("k05", STANDARD, "a"))
        self.assertEqual(parse_control("k05.b"), ControlRef("k05", STANDARD, "b"))
        self.assertEqual(parse_control("k05.h"), ControlRef("k05", HYPERSHIFT, "a"))
        self.assertEqual(parse_control("k05.h.b"), ControlRef("k05", HYPERSHIFT, "b"))
        self.assertEqual(parse_control("dpad_up.h"), ControlRef("dpad_up", HYPERSHIFT, "a"))

    def test_rejects(self):
        for bad in ("k21", "k05.b.h", "k05.h.h", "wheel_up.b", "dpad_up.h.b", "top_button.b", ""):
            with self.assertRaises(ValueError):
                parse_control(bad)

# tests/test_bindings.py
    def test_hypershift_binding(self):
        b = parse_binding_text(" HyperShift ")
        self.assertEqual(b, Binding("hypershift"))
        self.assertEqual(binding_to_dict(b), {"type": "hypershift"})
        self.assertEqual(binding_from_dict({"type": "hypershift"}), b)
        self.assertEqual(binding_label(b), "Hypershift")
```

- [ ] **Step 2: Run them; they fail** — `python3 -m unittest tests.test_layers tests.test_bindings 2>&1 | tail -3` → errors (no module `tartarus.layers`, BindingError for `hypershift`).
- [ ] **Step 3: Implement** the interfaces above. `parse_binding_text` checks `lower == "hypershift"` next to `disable`.
- [ ] **Step 4: Suite** → `OK`.
- [ ] **Step 5: Commit** — `feat: hypershift binding type and layer control addressing`

### Task 2: The Hypershift block in the profile

**Files:**
- Modify: `py_modules/tartarus/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Task 1's `HYPERSHIFT_KEYS`, `Binding("hypershift")`.
- Produces:
  - `config.Hypershift` dataclass: `bindings: Dict[str, Binding]`, `actuation: Dict[str, float]`, `secondary: Dict[str, Secondary]` (all `default_factory=dict`), and `copy(self) -> Hypershift` (new dicts; `Binding` and `Secondary` are frozen so values are shared safely).
  - `Profile.hypershift: Hypershift = field(default_factory=Hypershift)`
  - `config.hypershift_key(p: Profile) -> Optional[str]` — the control whose standard binding type is `"hypershift"`, else `None`.
  - `_dump` writes `"hypershift": {"bindings", "actuation", "secondary"}` in the same shapes as the profile's own fields.
  - `_parse_profile` runs, in order: bindings → hypershift-key fix-up → actuation → secondary (which drops the key's secondary) → `_parse_hypershift(raw.get("hypershift"), key)`.

Parse rules (each drop logs a warning, as the existing parsers do):
- Hypershift-key fix-up: of the controls whose parsed binding is `hypershift`, keep the first in `ALL_CONTROLS` order that is in `HYPERSHIFT_KEYS`; every other one gets its factory binding.
- The key's standard `secondary` entry is dropped.
- Layer bindings: control in `ALL_CONTROLS`, not the key, parses, and type is not `hypershift`.
- Layer actuation: control has a layer binding, is in `ACTUATION_KEYS`, `valid_mm`; stored rounded, only away from `DEFAULT_MM` (reuse `_parse_actuation`'s rules).
- Layer secondary: control has a layer binding, as `_parse_secondary` against the *layer's* actuation, and binding type not `hypershift`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_hypershift_round_trip(self):
        c = default_config()
        p = c.profiles[0]
        p.bindings["k19"] = Binding("hypershift")
        p.hypershift.bindings.update({"k05": parse_binding_text("F1"), "dpad_up": parse_binding_text("F2")})
        p.hypershift.actuation["k05"] = 2.0
        p.hypershift.secondary["k05"] = Secondary(parse_binding_text("F3"), 3.0)
        save_config(self.path, c)
        q = load_config(self.path).profiles[0]
        self.assertEqual(hypershift_key(q), "k19")
        self.assertEqual(q.hypershift, p.hypershift)

    def test_file_without_hypershift_loads_empty(self):
        # a v2 file written before this change: no "hypershift" key anywhere
        ...
        self.assertEqual(q.hypershift, Hypershift())
        self.assertIsNone(hypershift_key(q))

    def test_parse_extra_hypershift_keys_reset(self):
        # bindings: wheel_up, k03 and k07 all {"type": "hypershift"}
        self.assertEqual(hypershift_key(q), "k03")
        self.assertEqual(q.bindings["k07"], parse_binding_text("Q"))
        self.assertEqual(q.bindings["wheel_up"], parse_binding_text("WheelUp"))

    def test_parse_drops_bad_layer_entries(self):
        # key k19; layer bindings for k19 (the key), k02 {"type": "hypershift"}, "k99";
        # layer actuation for k06 (no entry) and k05 at 1.55; layer secondary for k05 0.2 mm deeper than its layer point
        self.assertEqual(set(q.hypershift.bindings), {"k05"})
        self.assertEqual(q.hypershift.actuation, {})
        self.assertEqual(q.hypershift.secondary, {})

    def test_hypershift_key_loses_its_secondary(self):
        # k19 bound to hypershift with a standard secondary entry in the file
        self.assertNotIn("k19", q.secondary)

    def test_hypershift_copy_is_independent(self):
        h = Hypershift(bindings={"k05": parse_binding_text("F1")})
        h2 = h.copy()
        h2.bindings["k06"] = parse_binding_text("F2")
        self.assertEqual(set(h.bindings), {"k05"})
```

Write the `...` fixtures as JSON dicts in the style of the existing config tests.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_config 2>&1 | tail -3` → fails (`Hypershift` not defined).
- [ ] **Step 3: Implement** the interfaces and rules above.
- [ ] **Step 4: Suite** → `OK`.
- [ ] **Step 5: Commit** — `feat: hypershift layer in the profile config`

### Task 3: Engine layer switching (key, wheel and D-pad events)

**Files:**
- Modify: `py_modules/tartarus/engine.py`
- Test: `tests/test_engine_hypershift.py` (new; import `FakeEmitter`, `profile`, `down`, `up` and the key codes from `tests.test_engine`)

**Interfaces:**
- Consumes: `layers.STANDARD/HYPERSHIFT`, `parse_control`, `Profile.hypershift`.
- Produces (engine internals Task 4 and Task 10 build on):
  - `self._hypershift_down: bool`, `self._hypershift_control: Optional[str]`
  - `_active_layer(self) -> str`
  - `self._pressed: Dict[str, str]` — control → layer its press started in (was a `Set`)
  - `_trigger(self, control: str, is_down: bool, layer: Optional[str] = None)` — on down, `layer or self._active_layer()` is recorded in `_pressed`
  - `_binding_for(self, control: str, layer: str) -> Optional[Binding]` — on `HYPERSHIFT`, a control with an entry uses the entry (slot b: the entry's secondary, or `None`); a control without one falls through to standard (binding and secondary).
  - `Binding("hypershift")` in `_trigger`: down sets `_hypershift_down`/`_hypershift_control`; the matching up clears them. It sends nothing.
  - `release_all` also clears `_hypershift_down`, `_hypershift_control`.

The up path keeps releasing `self._held.pop(control)`, so a press always ends with the codes it started with. Wheel steps and D-pad transitions go through `_trigger` and so use the active layer at the moment they happen.

- [ ] **Step 1: Write the failing tests.** Helper: `hs_profile(**layer_texts)` = `profile(k19="hypershift")` with `hypershift.bindings` set from the texts (control id keys, e.g. `k09="F1"`, `wheel_up="F5"`, `dpad_up="F2"`). Codes: k19 sends `C` (46), k09 `E`, k08 `W`. Every test ends by asserting `e._counts == {}` after all physical keys are up.

```python
    async def test_layer_binding_while_held(self):          # 19↓ E↓ E↑ 19↑ → F1↓ F1↑, nothing for 19
    async def test_fall_through_uses_standard(self):        # 19↓ W↓ W↑ → W↓ W↑
    async def test_disable_entry_does_nothing(self):        # k09.h = disable: 19↓ E↓ E↑ → []
    async def test_standard_press_survives_hypershift_down(self):   # E↓ 19↓ E↑ 19↑ → E↓ E↑
    async def test_layer_binding_released_after_hypershift_up(self): # 19↓ E↓ 19↑ E↑ → F1↓ F1↑, and a second E↓ gives E↓
    async def test_every_order_of_two_presses(self):
        # all 6 interleavings of (19↓,19↑) with (E↓,E↑) keeping each key's ↓ before its ↑:
        # E's output is F1 iff 19↓ came before E↓ and 19↑ came after E↓; every down has its up; counts empty
    async def test_macro_entry_runs_and_finishes(self):    # k09.h = "A, B": 19↓ E↓ 19↑ E↑, settle → A↓A↑B↓B↑
    async def test_wheel_uses_layer_at_step(self):          # wheel_up.h=F5: step, 19↓, step, 19↑, step → WheelUp, F5 tap, WheelUp
    async def test_dpad_direction_entry_and_press_rule(self):  # dpad_up.h=F2: Up↓ 19↓ Up↑ → Up↓ Up↑; 19 still held: Up↓ Up↑ → F2↓ F2↑
    async def test_dpad_8way_diagonal_uses_new_layer(self): # 8way, dpad_up_right.h=F3: 19↓ Up↓ Right↓ → Up↓ (dpad_up falls through), Up↑, F3↓
    async def test_release_all_resets_layer(self):          # 19↓ E↓, release_all → F1↑; E↓ (19 is still physically down) → E↓ (standard)
    async def test_no_hypershift_key_no_layer(self):        # entries but no hypershift binding: E↓ → E↓
    async def test_top_button_as_hypershift_key(self):      # profile(top_button="hypershift"): Alt↓ E↓ → F1↓, no Alt output
```

Write each test body from its comment (events in, `self.out.events` out).

- [ ] **Step 2: Run** `python3 -m unittest tests.test_engine_hypershift 2>&1 | tail -3` → fails.
- [ ] **Step 3: Implement** the interfaces above in `engine.py`.
- [ ] **Step 4: Suite** → `OK` (the existing `tests/test_engine.py` must pass unchanged).
- [ ] **Step 5: Commit** — `feat: engine switches to the hypershift layer while its key is held`

### Task 4: Per-layer actuation and secondary function from depth

**Files:**
- Modify: `py_modules/tartarus/actuation.py` (`KeyTracker.idle`)
- Modify: `py_modules/tartarus/engine.py` (`handle_depth`, `_points`)
- Test: `tests/test_actuation.py`, `tests/test_engine_hypershift.py`

**Interfaces:**
- Consumes: Task 3's `_active_layer`, `_trigger(..., layer)`, `_binding_for(control, layer)`.
- Produces:
  - `KeyTracker.idle -> bool` (property): nothing held, not latched, not blocked.
  - `RemapEngine._points(self, control: str, layer: str) -> Tuple[int, Optional[int]]` — `(fire_a, fire_b)` from the layer's actuation and secondary when the key has an entry on `HYPERSHIFT`, else from the standard ones.
  - `self._key_layer: Dict[str, str]` — the layer each depth key's current press belongs to; cleared by `release_all`.

`handle_depth`, per key with a changed depth: if `tracker.idle`, set `tracker.fire_a, tracker.fire_b = self._points(control, layer)` for `layer = self._active_layer()` and store it in `_key_layer`; then feed and pass `layer=self._key_layer[control]` to `_trigger` for both slots. `_build_trackers` keeps building from the standard layer.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_actuation.py
    def test_idle(self):
        t = KeyTracker(16, 120)
        self.assertTrue(t.idle)
        t.feed(20);  self.assertFalse(t.idle)        # A held
        t.feed(130); t.feed(100); self.assertFalse(t.idle)  # latched after B
        t.feed(0);   self.assertTrue(t.idle)
        t.feed(200); t.reset(); self.assertFalse(t.idle)    # blocked
        t.feed(0);   self.assertTrue(t.idle)

# tests/test_engine_hypershift.py — depth = self.depths(...) as in test_engine; 19 at depth 200 is "held"
    async def test_layer_actuation_point(self):        # k09.h=F1 at 2.5 mm (depth 120): 19 held, k09 to 60 → nothing; to 130 → F1↓
    async def test_layer_secondary_function(self):     # k09.h entry with secondary F3 at 3.6 mm: k09 to 255 → F1↓ F1↑ F3↓
    async def test_fall_through_keeps_standard_secondary(self):  # k09 standard secondary Z at 3.6, no entry: 19 held, k09 255 → E↓ E↑ Z↓
    async def test_entry_without_secondary_has_none(self):       # standard secondary on k09, entry without one: 19 held, k09 255 → F1↓ only
    async def test_depth_press_keeps_its_layer_points(self):
        # standard k09 at 2.5 mm, entry at 1.5 mm. k09 to 60 (standard idle, below 120) → nothing;
        # 19 down while k09 sits at 60 → k09 still has no press; k09 to 61 → tracker idle so it re-targets → F1↓ (layer point 16)
        # second case: k09 standard press held at 130 (E↓), 19 down, 19 up, k09 to 0 → E↑, never F1
    async def test_set_profile_while_hypershift_held(self):
        # 19 to 200, k09 to 200 (F1↓); set_profile(same profile) → F1↑; k09 to 210 → nothing (blocked); 19 to 0, then 200 again → layer active again (k09 to 0, then 200 → F1↓)
```

- [ ] **Step 2: Run** both files → fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Suite** → `OK`.
- [ ] **Step 5: Commit** — `feat: hypershift layer depths and secondary functions`

### Task 5: Service setters, state and profile copy

**Files:**
- Modify: `py_modules/tartarus/service.py` (`set_binding`, `set_actuation`, `set_actuation_keys`, `set_secondary`, `_apply_actuation`, `create_profile`, `state`; new `clear_hypershift_entry`)
- Modify: `main.py` (new callable `clear_hypershift_entry`)
- Test: `tests/test_service_hypershift.py` (new; reuse `Rig` from `tests.test_service`)

**Interfaces:**
- Consumes: `parse_control`, `ControlRef`, `HYPERSHIFT_KEYS`, `Hypershift.copy`, `hypershift_key`.
- Produces:
  - `set_binding(profile_id, control, b)` accepts every `parse_control` form:
    - `b.type == "hypershift"`: only for `ControlRef(X, STANDARD, "a")` with X in `HYPERSHIFT_KEYS`, else `ValueError("Only keys 01-20 and the top button can be the Hypershift key")`. Makes X the key: the previous key (if another) gets its factory binding (`parse_binding_text(FACTORY_OUTPUT[old])`); X's standard secondary and X's layer entry (all three maps) are removed. X's standard actuation stays.
    - standard `a`: as today (overwriting the key's binding turns Hypershift off; the layer is kept).
    - standard `b`: as today, but `ValueError` on the Hypershift key.
    - hypershift `a`: `ValueError("The Hypershift key has no Hypershift binding")` for the key; otherwise creates or replaces the entry. On creation for an actuation key, copy the standard mm into `hypershift.actuation` when it isn't `DEFAULT_MM`.
    - hypershift `b`: needs the entry and its secondary, like standard `b`.
  - `set_actuation(profile_id, "kNN.h", mm)` and `set_actuation_keys(profile_id, ["kNN.h", ...], mm)`: layer depth; every control needs an entry (`ValueError(f"{base} has no Hypershift binding")`); all controls in one call share a layer. `_apply_actuation(profile, controls, mm, layer)` works on the layer's actuation and secondary maps, with the same move-B-deeper rule.
  - `set_secondary(profile_id, "kNN.h", mm | None)`: as today against the entry's maps; needs the entry. `set_secondary` on the Hypershift key itself → `ValueError("The Hypershift key has no secondary function")`.
  - `clear_hypershift_entry(profile_id: str, control: str) -> None` — control is `X.h`; removes X from all three layer maps; no error if absent.
  - `create_profile` copies `hypershift=source.hypershift.copy()`.
  - `state()` per profile adds `"hypershift": {"key": hypershift_key(p), "bindings": {c: {"binding", "label"}}, "actuation": {...}, "secondary": {c: {"binding", "label", "actuation"}}}`.
  - `main.py`: `async def clear_hypershift_entry(self, profile_id: str, control: str) -> dict`, returning `self.service.state()` like the others.

- [ ] **Step 1: Write the failing tests**

```python
    def test_choose_hypershift_key(self):            # set_binding k19 hypershift → state key "k19", label "Hypershift"
    def test_moving_the_key_resets_the_old_one(self):  # k19 then k05 → key k05; k19 binding "C" (factory)
    def test_key_loses_secondary_and_entry(self):    # k05 with secondary and layer entry (3 maps), make k05 key → all gone
    def test_other_binding_turns_hypershift_off_keeps_layer(self):  # key k19, entry k05.h; set_binding_text k19 "C" → key None, k05 entry kept
    def test_hypershift_type_rejected_elsewhere(self):  # on "k05.h", "k05.b", "wheel_up", "dpad_up" → ValueError
    def test_entry_on_key_rejected(self):             # key k19: set_binding "k19.h" → ValueError
    def test_new_entry_copies_standard_depth(self):   # k05 standard 2.4 → set_binding k05.h → hypershift.actuation["k05"] == 2.4; secondary empty
    def test_layer_actuation_needs_entry(self):       # set_actuation "k06.h" without entry → ValueError; set_actuation_keys mixing "k05.h","k06" → ValueError
    def test_layer_actuation_moves_layer_secondary(self):  # entry k05 secondary at 2.5; set_actuation k05.h 2.4 → secondary 2.9; standard maps untouched
    def test_layer_secondary_and_its_binding(self):   # set_secondary k05.h 3.0; set_binding k05.h.b F3 → state secondary F3 at 3.0
    def test_clear_entry(self):                       # clear_hypershift_entry k05.h → gone from all three maps; clearing again is fine
    def test_create_profile_copies_hypershift_deeply(self):  # copy, add entry on the copy → source unchanged
    def test_layer_edit_reaches_engine(self):          # active profile: set_binding k09.h F1, then 19↓ E↓ on the rig → F1 out
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_service_hypershift 2>&1 | tail -3` → fails.
- [ ] **Step 3: Implement.** Use one helper `_layer_maps(profile, layer) -> Tuple[Dict[str, float], Dict[str, Secondary]]` for the actuation/secondary paths instead of branching in each setter.
- [ ] **Step 4: Suite** → `OK`.
- [ ] **Step 5: Commit** — `feat: hypershift setters, state and profile copy`

### Deck check H1 (no editor yet)

1. Main thread: deploy (`scripts/deploy.sh <host>`); the user runs the `sudo cp` and restarts the plugin.
2. The user, in the editor on the FPS profile: Key 19 → Choose… → Type a binding → `hypershift` → Apply. Card shows "Binding: Hypershift".
3. One `sonnet` subagent, brief: "Over `ssh deck@steamdeck.local`, back up `~/homebrew/settings/decky-tartarus/settings.json` (confirm the path from the log) to `settings.json.pre-h1`, then add to the FPS profile `"hypershift": {"bindings": {"k07": {"type":"key","keys":["F1"]}, "k10": {"type":"macro","steps":[["A"],["B"]]}, "dpad_up": {"type":"key","keys":["F2"]}}}`. Do nothing else. Report the diff." The user restarts the plugin.
4. The user, in a text field on the Deck (or `evtest` if they prefer), with FPS active:
   - Hold 19: Q gives F1, key 10 types `ab`, thumbpad up gives F2; W/A/S/D give w/a/s/d.
   - Let go of 19: Q gives q again.
   - Odd orders: Q↓ 19↓ Q↑ 19↑; 19↓ Q↓ 19↑ Q↑; 19↓ W↓ 19↑ W↑ — nothing stays down (watch for auto-repeat).
   - Switch to another game/profile while holding 19 + Q: nothing stays down.
5. The same subagent scans the plugin log for tracebacks since the restart and writes `deck-H1.md`.

Pass: every item above. Ledger line, commit, **stop**: tell the user to `/clear` and start H2 with `/model sonnet`.

---

## H2: Editor

### Task 6: API types, layer helpers, the switch and the drawing

**Files:**
- Modify: `src/api.ts`
- Create: `src/editor/layers.ts`, `src/editor/LayerSwitch.tsx`
- Modify: `src/editor/Keypad.tsx`

**Interfaces:**
- Consumes: Task 5's state and callables.
- Produces:
  - `api.ts`: `HypershiftEntry = { binding: BindingDict; label: string }`; `HypershiftState = { key: string | null; bindings: Record<string, HypershiftEntry>; actuation: Record<string, number>; secondary: Record<string, SecondaryState> }`; `ProfileState.hypershift: HypershiftState`; `clearHypershiftEntry = callable<[profileId: string, control: string], State>("clear_hypershift_entry")`.
  - `layers.ts`: `type Layer = "standard" | "hypershift"`; `HYPERSHIFT_ACCENT = "#ff6000"`; `HYPERSHIFT_KEYS: string[]` (k01-k20, top_button); `onLayer(control: string, layer: Layer): string` (adds `.h`); `baseControl(control: string): string` (strips `.h` / `.b`); `bindingOf(p: ProfileState, control: string): BindingDict | undefined` for all four forms; `hasEntry(p, control): boolean`; `layerMm(p, key, layer, defaultMm): number` (an entry's mm, else the standard mm); `layerSecondary(p, key, layer): SecondaryState | undefined` (entry's on hypershift, standard's otherwise).
  - `LayerSwitch({ layer, onChange }: { layer: Layer; onChange(l: Layer): void })`: a `Focusable flow-children="row"` with two compact `DialogButton`s, "Standard" and "Hypershift"; the active one is filled (Standard `#3d8b2f` as in ChoosePage, Hypershift `HYPERSHIFT_ACCENT`).
  - `Keypad` gains `layer: Layer`. On `"hypershift"`:
    - bindings view: an entry shows its label; a control without one shows the standard label at `opacity: 0.45`; the `2×` badge follows `layerSecondary`; the Hypershift key is a plain `div` (not focusable) with an orange border and fill, label "Hypershift"; selection uses `HYPERSHIFT_ACCENT` for border and glow.
    - actuation view: keys with an entry show `layerMm` and can be selected; other keys render like non-keys (dimmed, not focusable).
    - On `"standard"` the drawing is unchanged (the key's label is its binding label, "Hypershift").

- [ ] **Step 1: Implement** the above.
- [ ] **Step 2: FE check** → clean (callers don't pass `layer` yet: make it required and fix the two call sites with `layer="standard"` in this task).
- [ ] **Step 3: Commit** — `feat(editor): layer helpers, Standard/Hypershift switch and layered drawing`

### Task 7: Customize, Choose… and Secondary function on both layers

**Files:**
- Modify: `src/editor/Editor.tsx` (`layer` state, default `"standard"`, passed to Customize and Actuation; not stored anywhere else, so it resets each time the editor opens)
- Modify: `src/editor/CustomizePage.tsx`, `src/editor/ChoosePage.tsx`, `src/editor/SecondaryPage.tsx`, `src/editor/categories.ts`

**Interfaces:**
- Consumes: Task 6's `layers.ts`, `LayerSwitch`, `Keypad layer`, `clearHypershiftEntry`.
- Produces: `CustomizePage` and `ActuationPage` props gain `layer: Layer; onLayer(l: Layer): void`. `ChoosePage` and `SecondaryPage` take any control form (`k05.h`, `k05.h.b`) and read through `bindingOf` / `layerSecondary`.

Behaviour (copy is fixed; layout is the builder's within the page height):
- Right column order: `EditingRow`, `LayerSwitch`, card. Changing layer closes a sub-page and clears the card error (add `layer` to the reset effect's deps).
- **Standard layer card**: as today, except on the Hypershift key the Secondary function row is hidden.
- **Hypershift layer card**:
  - Profile without a key: first line of the card, dimmed: "No Hypershift key yet. On Standard, pick a key's Choose… → Hypershift." Editing still works.
  - Selected control is the Hypershift key: only "Key 19 is the Hypershift key. Hold it to use this layer." (use `controlTitle`).
  - No entry: "Binding: **Same as Standard** (<standard label>)" with Choose… and Record (`control = selected + ".h"`).
  - Entry: "Binding: **<entry label>**" with Choose… and Record; a row "Hypershift binding" with a **Clear** button (`clearHypershiftEntry(profile.id, selected + ".h")`) in place of Factory default; for keys, the actuation slider writing `setActuation(profile.id, selected + ".h", mm)` and showing `layerMm`; the Secondary function row opening `SecondaryPage` with `control = selected + ".h"`.
  - D-pad: the 8-way toggle shows on both layers (profile setting).
- **ChoosePage**: `current = bindingOf(profile, control)`. Titles: "Binding for Key 05", "Hypershift binding for Key 05", "Secondary function for Key 05", "Secondary function for Key 05 (Hypershift)". New category `{ id: "hypershift", label: "Hypershift", modifiers: false, picks: [] }` just above `disable`, listed only when `control` (no suffix) is in `HYPERSHIFT_KEYS`. Its body: "Hold Key 05 to switch the other controls to their Hypershift bindings." plus, when another key is the Hypershift key, "Key 19 goes back to its factory default (C)." and an **Apply** button that sends `"hypershift"`. `choiceFor` maps a `hypershift` binding to this category. On the Hypershift layer the Disable text reads "Key 05 does nothing while Hypershift is held."
- **SecondaryPage**: reads `layerSecondary(profile, baseControl(control), layer)` and the slider minimum from `layerMm`; title "Secondary function · Key 05" or "Secondary function · Key 05 · Hypershift".

- [ ] **Step 1: Implement.**
- [ ] **Step 2: FE check** → clean.
- [ ] **Step 3: Commit** — `feat(editor): edit the hypershift layer on Customize`

### Task 8: Actuation on both layers, README

**Files:**
- Modify: `src/editor/ActuationPage.tsx`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 6-7.

Behaviour:
- `LayerSwitch` under `EditingRow`, as on Customize. Switching layer clears the selection and error.
- Hypershift layer: selectable keys are those with an entry; **Select all** selects only those; **Apply to selected** calls `setActuationKeys(profile.id, selection.map((c) => c + ".h"), value)`; `keyMm` reads `layerMm`. With no entries the card says "No keys have a Hypershift binding yet." and the buttons are disabled.
- README: replace the roadmap's "keys 02-20" Hypershift line (it is now built: any key 01-20 or the top button); add Hypershift to Features and to the Editor section (switch, Same as Standard, Clear, locked key); keep "Secondary function" a separate bullet and say they differ in one sentence.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: FE check** → clean; suite → `OK`.
- [ ] **Step 3: Commit** — `feat(editor): hypershift actuation; docs: README for Hypershift`

### Deck check H2

1. Main thread: restore `settings.json.pre-h1` only if the user asks; deploy.
2. The user, on FPS: set up Hypershift entirely in the editor — 19 as Hypershift key; entries for Q (F1), E (macro), thumbpad up (F2), one key with its own depth and secondary function; one key set to Disable; Clear one entry. Move the Hypershift key to 18 and back; check 18 returns to X. Create a profile from FPS and check its layer is there; edit the copy, check FPS is unchanged. Play-test as in H1 step 4.
3. One `sonnet` subagent, brief: "Using the CEF probe (memory `deck-cef-layout-probe`), on the open editor measure for Customize and Actuation on each layer, and for the Choose… page with the Hypershift category: any element whose bottom exceeds the page area (534 − 40 CSS px), any horizontal overflow, and whether the LayerSwitch buttons are focusable. Then scan the plugin log for tracebacks. Write `deck-H2.md`; return pass/fail and at most 10 lines." The user drives the pages it asks for (it can't press buttons).

Pass: all of step 2 works, no page overflows. Ledger line, commit, **stop**: `/clear`, start H3 with `/model sonnet`.

---

## H3: Hypershift lights

### Task 9: Deck check — per-key custom frame (before any lights code)

**Files:**
- Modify: `scripts/deck-probe.py` (two commands)
- Modify: `docs/superpowers/spike-findings.md` (new section "Hypershift lights: custom frame")

New probe commands (same `report()`/`send()` helpers and status printing as `led`):
- `frame RRGGBB [INDEX]`: send `0F/02` args `00 00 08 00 00 00`, then `0F/03` args `00 00 00 00 14` + 21 triplets: all `RRGGBB`, or with INDEX given, triplet INDEX `RRGGBB` and the rest `26 26 26`. Print both statuses.
- `frametime N`: N times, send the static effect + brightness reports (`effect_reports("static", "#00ff00", 100)` copied as bytes, the probe stays stdlib-only) and then the two frame reports; print mean and max milliseconds for each switch, measured around the sends including their replies.

- [ ] **Step 1: Add the commands**; run `python3 -c "import ast,sys; ast.parse(open('scripts/deck-probe.py').read())"` → no output. Commit — `chore: deck-probe custom frame commands`.
- [ ] **Step 2: The user runs, plugin stopped** (Claude asks first: this is a new kind of send): `sudo python3 deck-probe.py setmode 03`, then `frame FF6000`, then `frame FF0000 0` … `frame FF0000 20`, noting which key lights for each index (and whether the thumb key and top button ever do), then `frametime 20`, then `setmode 00`.
- [ ] **Step 3: Record** in `spike-findings.md`: statuses, the index → control table, thumb key / top button LEDs, the timing (mean/max), and the verdict: **per-key** if both statuses are `0x02`, keys light individually and the switch takes under ~50 ms; otherwise **fallback** (whole backlight static). Ledger: `Task 9: Ruling: per-key|fallback — <why>`. Commit — `docs: custom frame findings for Hypershift lights`.

### Task 10: Hypershift lights in the backend

**Files:**
- Modify: `py_modules/tartarus/lighting.py`, `py_modules/tartarus/config.py` (`Lighting`), `py_modules/tartarus/engine.py` (`on_layer`), `py_modules/tartarus/service.py`, `main.py`
- Test: `tests/test_lighting.py`, `tests/test_config.py`, `tests/test_engine_hypershift.py`, `tests/test_service_lighting.py`

**Interfaces:**
- Consumes: Task 9's verdict and index table; Task 3's `_hypershift_down`.
- Produces:
  - `Lighting.hypershift: bool = False`, `Lighting.hypershift_color: str = "#ff6000"`; dumped as `"hypershift": {"enabled": bool, "color": str}` inside `"lighting"`; parsed leniently (bad values → defaults). `set_lighting` must keep them (build with `dataclasses.replace`).
  - `RemapEngine(..., on_layer: Callable[[bool], None] = lambda active: None)` — called with `True` when the Hypershift key goes down, `False` when it comes up, and `False` from `release_all` only if the layer was active.
  - Per-key verdict: `lighting.FRAME_INDEX: Dict[str, int]` (from Task 9), `lighting.FAINT = "#262626"`, `custom_frame_reports(colors: Sequence[str]) -> List[bytes]` (21 `#rrggbb` colours → `[select, frame]`: `build_report(0x0F, 0x02, bytes([0,0,8,0,0,0]))` and `build_report(0x0F, 0x03, bytes([0,0,0,0,0x14]) + 63 RGB bytes)`; `ValueError` unless exactly 21 valid colours), `hypershift_frame(lit: Iterable[str], color: str) -> List[str]` (lit controls in `color`, every other index `FAINT`).
  - Fallback verdict: no frame code; the active send is `effect_reports("static", color, brightness)`.
  - `TartarusService.set_hypershift_lights(enabled: bool, color: str) -> None` — validates (`bool`; colour via `lighting._rgb`), saves, notifies. `main.py` callable `set_hypershift_lights(enabled, color) -> dict`.
  - `TartarusService._on_layer(active: bool)`, passed to `RemapEngine`: when `active` and `lighting.enabled` and `lighting.hypershift`, send the Hypershift lights for the *active* profile (lit = its `hypershift.bindings` keys plus its Hypershift key) and set `self._hypershift_lit = True`; when not active and `_hypershift_lit`, send `self._lighting_reports()` and clear the flag. Sends use `_send_command(..., quiet=True)`; failures are logged, never raised.
  - `state()["lighting"]["hypershift"] = {"enabled": ..., "color": ...}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lighting.py (per-key verdict only)
    def test_custom_frame_reports(self):
        select, frame = custom_frame_reports(["#ff6000"] * 21)
        self.assertEqual(select[6:14], bytes([0x0F, 0x02, 0, 0, 8, 0, 0, 0]))
        self.assertEqual(frame[5], 68)
        self.assertEqual(frame[6:13], bytes([0x0F, 0x03, 0, 0, 0, 0, 0x14]))
        self.assertEqual(frame[13:16], bytes([0xFF, 0x60, 0x00]))
    def test_custom_frame_needs_21_colours(self):      # 20 colours, or "red" → ValueError
    def test_hypershift_frame(self):                   # lit {"k19","k07"} → those indices #ff6000, the rest FAINT

# tests/test_config.py
    def test_hypershift_lights_round_trip_and_defaults(self):  # absent → (False, "#ff6000"); saved values come back

# tests/test_engine_hypershift.py
    async def test_on_layer_callback(self):  # 19↓ → [True]; 19↑ → [True, False]; 19↓, release_all → [..., True, False]; release_all again → no call

# tests/test_service_lighting.py
    def test_hypershift_lights_sent_and_restored(self):   # lights on: 19↓ → frame (or static) reports sent; 19↑ → effect + brightness reports
    def test_hypershift_lights_off_or_lighting_off_send_nothing(self):
    def test_set_lighting_keeps_hypershift_lights(self):
    def test_set_hypershift_lights_validates(self):       # enabled "yes", colour "#ff60" → ValueError, nothing saved
```

- [ ] **Step 2: Run** the four files → fail.
- [ ] **Step 3: Implement** the branch the Task 9 verdict picked.
- [ ] **Step 4: Suite** → `OK`.
- [ ] **Step 5: Commit** — `feat: hypershift lights`

### Task 11: Hypershift lights on the Lighting tab, README

**Files:**
- Modify: `src/api.ts` (`LightingState.hypershift: { enabled: boolean; color: string }`, `setHypershiftLights = callable<[enabled: boolean, color: string], State>("set_hypershift_lights")`)
- Modify: `src/LightingControls.tsx` (export `SWATCHES`)
- Create: `src/editor/HypershiftLights.tsx`
- Modify: `src/editor/Editor.tsx` (Lighting tab: `HypershiftLights` under `LightingControls` in the same card), `README.md`

**Interfaces:**
- `HypershiftLights({ state, onChanged }: { state: State; onChanged(s: State): void })`: a `ToggleField` "Hypershift lights", description "Light the keys with a Hypershift binding while the Hypershift key is held."; when on, a swatch row (same look as `LightingControls`) choosing the colour. Writes go straight to `setHypershiftLights` (no debounce); a refusal shows in red under the row. When lighting is off, add the dimmed line "Lighting is off, so Hypershift lights stay off."

- [ ] **Step 1: Implement**; README Features line gains Hypershift lights (and the fallback wording if Task 9 chose it).
- [ ] **Step 2: FE check** → clean; suite → `OK`.
- [ ] **Step 3: Commit** — `feat(editor): Hypershift lights on the Lighting tab`

### Deck check H3

1. Deploy. The user, on FPS with lighting on (try spectrum and static): Hypershift lights on, orange. Hold 19: the entry keys and 19 light orange, the rest faint white; let go: the effect comes back (spectrum restarts). Tap 19 quickly 10 times: the lights follow. Pick another colour. Turn lighting off: holding 19 lights nothing. Switch to MMO: its own layer lights.
2. One `sonnet` subagent: CEF probe of the Lighting tab with Hypershift lights on (overflow, focusable swatches) + log scan for tracebacks and failed lighting sends; writes `deck-H3.md`.
3. Then the final whole-branch review on `opus` (one subagent), against the spec and this plan.

Pass: all of step 1, no overflow, review findings fixed or ruled. Ledger, commit, **stop**: the branch is ready for superpowers:finishing-a-development-branch.
