# Synapse-style editor and Quick Access panel: design

Status: approved in brainstorming on 2026-10-27. Replaces the editor UI from Tasks 16-18 of
`docs/superpowers/plans/2026-10-27-analog-and-profile-leds.md` (M5). The M5 Deck check was stopped at
step 1 because that UI can't be used on the Deck. It is rewritten for this UI and runs after it.
Mockups: `.superpowers/brainstorm/84389-1793111837/content/editor-v2.html` (git-ignored).

## Why

On the Deck's own screen (1280×800), the editor fails:
- The keypad drawing's top row is cut off.
- The profile bar (dropdown, LEDs, New, Rename, Delete and status text) fills the whole width.
- The binding picker, the text field and the actuation and secondary controls are stacked in one column. That column scrolls and runs behind the Steam footer, so the bottom row can't be read or reached.

The user wants the editor to feel like Razer Synapse's Tartarus Pro pages (Customize / Actuation /
Lighting, the device picture, settings in cards). It should be laid out like the Deck's own Settings
screen, with a menu down the left. The Quick Access panel gets a simpler, fixed order.

Success means that on the Deck's built-in screen:
- every editor page fits with no scrolling and nothing behind the footer;
- every control works with the D-pad and A/B;
- it's obvious which status-light pattern belongs to which profile.

## Goals

1. **Editor in Steam Settings style.** A menu on the left, one job per page, with the plugin's own Tartarus drawing as the
   centrepiece of the key pages.
2. **Quick Access panel in the user's order:**
   - title with a settings icon;
   - connection;
   - profile for the running game;
   - collapsible Lighting.
3. **A clear link between profiles and status lights**, drawn in the lights' real colours (top orange, middle
   green, bottom blue; unlit = dark).

## Non-goals

- Hypershift. It comes after this, as its own design.
- New keypad features, and new kinds of sends to the keypad. Everything here uses commands the plugin
  already sends.
- Changing the drawing itself. It stays our own SVG (no Razer images). Only how it's sized and labelled changes.

## Anti-goals

These make it a failure even if it works:
- Any page that needs scrolling, or has text hidden behind the footer, on the 1280×800 screen.
- A control that can't be reached with the D-pad.
- Cramming several jobs into one page again.

## Constraints

- Decky frontend: React and `@decky/ui` components, built with `pnpm build`. Backend: stdlib Python. All the
  rules from the analog spec still hold: settings stay `SCHEMA_VERSION = 2` with optional new fields,
  writes are atomic, and every active-profile change goes through `engine.set_profile`.
- Size budget: the Decky route sits under a ~40 px header and above a ~40 px footer, which leaves about
  1280×720. The drawing fits the page height (600×630 viewBox, about 640 px tall).
- *Builder's call (settled before planning):* "no scrolling" wins over drawing size. If the sidebar's
  chrome leaves too little room, the drawing scales down first (labels stay readable, at least 11 px on
  screen), and the sidebar's page title goes next. `SidebarNavigation` itself is dropped only if both of
  those still don't fit. The plan starts with a layout spike: an empty sidebar and the drawing with one
  card. The user measures it on the Deck before any page is built out.
- Naming: "actuation", "secondary function" / "deep press". Never "analog" or "Hypershift" for the deep press.
- The deep press is labelled "Deep press" in the UI. Its control id stays `kNN.b`.

## The Quick Access panel

From top to bottom:

1. **Title row:** "Tartarus" with a settings (gear) icon on the right. The icon opens the editor and
   closes the side menu. The "Edit keys" button goes away.
2. **Connection:** "Razer Tartarus Pro connected" (green) with the USB ID underneath, or "Not
   connected". Same as now.
3. **Profile for the running game.** When a game is running, a dropdown "<game> uses:" listing the
   profiles, as now, sets which profile that game uses. Each option shows the profile's three lights in
   colour next to its name. When no game is running, a line says which profile the keypad uses, with
   its lights.
4. **Lighting:**
   - A toggle "Lighting" turns the keypad backlight on or off.
   - When it's on, a row with an arrow expands and collapses the lighting settings. They start collapsed:
     - "Mode": a dropdown of the backend's effects (static, breathing, spectrum, wave, reactive, starlight);
     - colour swatches, shown only for modes that take a colour, as now;
     - brightness, as now.
   - When it's off, no arrow is shown.

The Adjustable actuation switch moves out of the panel to the editor's Actuation page ("everything can
be set from there").

**Lighting on/off.** The backend stores `lighting.enabled` (optional, default true) and keeps the
stored brightness. Off sends the current effect at brightness 0, which is an existing send. On sends the
stored settings again. Off survives reconnect, resume and restart. Off doesn't touch the profile
status lights. Whether a backlight send clears those lights is still an open question in
`synapse-capture-findings.md`. If it does, the plugin already re-sends them after lighting changes, and
that stays true.

## The editor

A full-screen route like today. It uses Steam's settings layout (`SidebarNavigation` from `@decky/ui`
is expected to fit; the builder decides). Left menu pages:

- **Customize**
- **Actuation**
- **Lighting**
- **Profiles**

An "Editing" profile dropdown, and a line when the keypad uses a different profile ("Keypad uses Default
now"). The profile you're editing applies to Customize and Actuation. *Builder's call (settled before
planning):* if `SidebarNavigation` has no slot under the menu, the dropdown and that line sit in a slim row
at the top of the Customize and Actuation pages only, not on Lighting or Profiles. No hand-built sidebar
just for this.

### Customize

- On the left, the Tartarus drawing at full page height. Each key shows its number and its binding
  label, and a key with a deep press shows `2×`. The wheel, top button and thumbpad directions can be
  selected as today, and so can the diagonals in 8-way mode.
- On the right, a card for the selected control:
  - title "Key 05" (or the wheel or thumbpad name) and the current binding in large text;
  - **Binding: Choose…** opens a full page (route or full-screen modal; the builder decides) with the
    quick picks, "More keys", Steam shortcuts and "Type a binding". Its Apply button is disabled
    while the text is empty, so the "empty binding" error can no longer happen. B goes back;
  - **Record from a key:** Record / Cancel, with "Nothing recorded" as today;
  - **Factory default (<key>): Reset**, shown only when the control has a factory binding;
  - **Deep press: <binding> · <mm> ›** (or "Off ›"), shown for keys 01-20. It opens its own page:
    - an on/off toggle;
    - the binding, with the same Choose… and Record as above, for control `kNN.b`;
    - a depth slider from A + 0.5 to 3.6 mm.

    Turning it on starts at 3.6 mm. Backend refusals show in red on that page. *Builder's call:* while
    Adjustable actuation isn't on, the page and the row show "Applies only with Adjustable actuation on."
    (a deep press needs driver mode) but stay editable;
  - **8-way D-pad** toggle (applies to the whole profile), shown when a thumbpad direction is selected.
    The builder may put it somewhere else on the page if that reads better.

### Actuation

- The same drawing. Each key 01-20 shows its actuation in mm. Selected keys turn green, as in Synapse.
  A press on a key toggles its selection. The wheel, top button and thumbpad can't be selected.
- A card with:
  - "Actuation · N keys selected";
  - one slider (1.5-3.6 mm, 0.1 steps, value shown as `x.x mm`) that starts at the selected keys' value,
    or at the first selected key's value when they differ;
  - **Select all**, **Clear**, and **Apply to selected** (disabled while nothing is selected);
  - the **Adjustable actuation** switch, with its status notes as in today's panel. When the switch
    isn't on, the note "Applies only with Adjustable actuation on." is shown.
- Apply is atomic. A new backend call, `set_actuation_keys(profile_id, controls, mm)`, uses the
  existing `_apply_actuation` rule: a deep press that ends up too close moves deeper with A, and if one
  can't move, nothing changes and the message is shown. `set_all_actuation` can stay or become this call
  with all keys; the builder decides.

### Lighting

- The same settings as the panel's Lighting section, laid out as a card: on/off, Mode, colour, brightness.
  As in the panel, Mode, colour and brightness are hidden while Lighting is off. Here they're shown
  without the collapse arrow.
- *Builder's call (settled before planning):* the on/off switch is its own backend call,
  `set_lighting_enabled(enabled)`. `set_lighting` keeps its signature, and since the controls are hidden
  while off, it is only reached while on.

### Profiles

- A list of profiles. Each row shows:
  - the three status lights drawn in colour;
  - the name, and "in use" on the profile the keypad uses now;
  - the games that use the profile ("Every game without its own profile" for Default);
  - a ⋯ button that opens Edit keys, Lights, Rename and Delete. Edit keys switches the profile you're
    editing and opens Customize. Lights isn't offered for Default, and Delete isn't either.
- **New profile** button at the bottom. Its copy source and name prompt work as today.
- **Lights** opens a picker that draws every pattern in colour. A pattern another profile uses is
  shown with that profile's name and can't be picked. This uses the existing `setLeds`.
- If there are more profiles than fit, the list may scroll inside its card. This is the only scrolling
  allowed. With the current maximum (`max_profiles`) the builder should check whether it fits.

## Left to the builder

- Exact sizes, spacing and the components used (`SidebarNavigation`, modal vs nested route for
  Choose…, Deep press and Lights). It must stay within the size budget and work with the D-pad.
- Whether shared lighting controls are one component used by both the panel and the editor.
  Recommended.
- Debounce and draft handling for sliders: keep today's behaviour of not losing the last change when
  switching key or profile.
- Keeping the single-recorder rule: only the picker that started a recording takes the result.

## Testing

- Backend: unit tests for `lighting.enabled` (stored, defaults to true for an old file, off sends
  brightness 0, on re-sends, survives reconnect) and for `set_actuation_keys` (atomic, moves B, refuses
  past 3.6, compares tenths).
- Frontend: `pnpm build` and type-check with no errors in `src/`.
- Deck check, run by the user: the rewritten M5 checklist on this UI. It also checks that every page
  fits with no scrolling and that everything is reachable with the D-pad.
