# Hypershift: design

Status: approved in brainstorming on 2026-10-27. Next on the README roadmap.
Reference: two Synapse screenshots of the Tartarus Pro's Hypershift pages (not in the repo):
the "Razer Hypershift" function in a key's side panel, and the Standard / Hypershift switch under
the device drawing.

**Terms.** *Hypershift* is a held key that switches the other controls to a second set of
bindings while it's held. The *secondary function* is the shipped, unrelated feature: a second
binding deeper in the same key's press. Keep the two names apart in code, UI and docs.

## Why

The user plays Arc Raiders on the **FPS** profile. They want to hold **key 19** and have every key
except WASD do something else while it's held, so they can keep moving and still reach more
actions. Letting go of 19 puts everything back. Another profile (MMO) has its own second layer.
It could use a different Hypershift key, though the user would probably keep the same one out
of muscle memory.

Success: on the Deck, with FPS active, holding 19 makes the keys the user set for Hypershift send
their Hypershift bindings. WASD keeps working, letting go of 19 brings everything back, and no key
ever gets stuck down. Switching to MMO gives MMO's own Hypershift key and layer.

## Goals

1. **A Hypershift key per profile.** Any key 01-20 or the top button, chosen like a binding. A
   profile without one works as it does today.
2. **A Hypershift layer per profile.** Every control except the Hypershift key itself can have a
   Hypershift entry. A key's entry is a full key: binding, actuation and secondary function, as in
   Synapse.
3. **Unset falls through.** A control with no Hypershift entry behaves exactly as on the standard
   layer while Hypershift is held (binding, actuation and secondary function).
4. **Editing like Synapse.** A Standard / Hypershift switch on Customize and Actuation changes
   which layer the drawing and card show.
5. **Optional Hypershift lights.** While the Hypershift key is held, the keys with a Hypershift
   entry light up in a chosen colour. Off by default.

## Non-goals

- More than one Hypershift key or layer per profile (no layer stacks, no toggle/latch mode).
- Hypershift lights per profile. Lighting is global today (per-game lighting is a separate
  roadmap item), so the Hypershift lights setting is global too.
- A key map or Hypershift view in the Quick Access panel (rejected for the standard layer
  already; see the memory note "no key map in panel").
- The wheel or D-pad as the Hypershift key.

## Anti-goals

- **A stuck key.** Pressing or releasing the Hypershift key while other keys are down must never
  leave an output key held.
- **Mixing up the two features.** The editor, state and code must never call Hypershift a
  "secondary" anything, or the reverse.
- **Breaking existing profiles.** Profiles saved before this change load unchanged and behave
  as today.

## Constraints

- Every page still fits 1280×800 with no scrolling and works with the D-pad and A/B (README,
  "Made for the Deck").
- The editor keeps the CSS Loader look and the existing card/row components.
- Actuation and secondary functions are host-side (driver mode depth reports, see
  `docs/superpowers/synapse-capture-findings.md`). So per-layer actuation needs no keypad command.
  When adjustable actuation is off, keys arrive as plain key events: Hypershift still swaps
  bindings, and layer depths and secondary functions have no effect, as on the standard layer
  today.
- Config is a versioned JSON file (`py_modules/tartarus/config.py`). New fields must be optional,
  and absent means "no Hypershift".

## Behaviour

### Choosing the Hypershift key

- **Choose…** gains a **Hypershift** pick (its own category, or an entry beside Disable; see
  "Left to the builder"). It is offered only on the Standard layer, and only for keys 01-20 and
  the top button.
- A profile has at most one Hypershift key. *My call:* choosing it on a second key moves it, and
  the old key goes back to its factory default.
- A key's card shows "Binding: **Hypershift**". A key 01-20 keeps its actuation slider: the depth
  at which it switches layers. The top button has no depth (it isn't in `ACTUATION_KEYS`), so it
  switches on a plain press.
- *My call:* making a key the Hypershift key removes that key's secondary function, and its
  Hypershift entry if it had one. The Secondary function row is hidden on the Hypershift key.
- Giving the Hypershift key any other binding (Choose…, Record, Factory default Reset) turns
  Hypershift off for the profile. The layer's entries are **kept**, so picking a Hypershift key
  again brings them back. *My call:* a layer without a key is never active.

### The Hypershift layer

- With the switch on **Hypershift**, the drawing shows the Hypershift layer:
  - Controls with an entry show their Hypershift binding.
  - Controls without one show their standard binding, dimmed, so you can see what falls through.
  - The Hypershift key is locked (shown as such, not selectable, as Synapse shows it red).
  - The Hypershift accent colour (orange, as in Synapse) marks the switch and the selection, so
    it's always clear which layer is being edited.
- If the profile has no Hypershift key, the Hypershift view says so and tells you how to choose
  one. *My call:* the layer can still be edited, so entries can be set up first.
- **A control's card on the Hypershift layer:**
  - With no entry: "Binding: **Same as Standard** (<standard label>)", with Choose… and Record.
  - Choose… or Record creates the entry. A key's entry then shows its own actuation slider
    (starting at the key's standard depth) and a Secondary function row. Both work exactly as on
    the standard layer, against the Hypershift entry.
  - **Clear** (in place of Factory default) removes the entry, and the control falls through
    again.
  - "Disable" is a real entry: the control does nothing while Hypershift is held. That is
    different from "Same as Standard".
  - Each D-pad direction can have its own Hypershift entry, like any control. For example, up,
    right, down and left become F1, F2, F3 and F4 while Hypershift is held. Synapse's Hypershift
    view shows the D-pad directions as editable too. The D-pad's 8-way switch is the profile's,
    shown on both layers (*my call*: the D-pad mode is not per layer).
- **Actuation tab:** the same switch. On Hypershift, the drawing shows the layer's depths.
  **Apply to selected** sets depth only on keys that have a Hypershift entry. *My call:* keys
  without an entry are shown dimmed and can't be selected there, so a depth never creates an
  entry with no binding.
- The **Editing** profile dropdown, profile copy (Create from…) and profile delete carry the
  Hypershift key and layer along with everything else.
- *My call:* the switch resets to Standard when the editor opens. It is not remembered.

### While playing

- Holding the Hypershift key (past its actuation point) makes the profile's Hypershift layer
  active. Releasing it makes the standard layer active again. The key itself sends nothing.
- **A press finishes in the layer it started in.** This covers both the binding and, for a key,
  its actuation and secondary function. If W is held when Hypershift goes down, W stays W until
  it's released. If a Hypershift binding is held when the Hypershift key comes up, it stays held
  until its own key is released. A key whose press began on one layer only uses the other
  layer's depths from its next press.
- Wheel steps and D-pad directions use the layer active when they happen. A D-pad direction held
  across a layer change follows the press rule.
- Switching profile, entering Record or turning on passthrough releases everything, as today,
  and the layer goes back to standard.

### Hypershift lights

- On the **Lighting** tab: a **Hypershift lights** switch (off by default) and a colour (the same
  swatches as the effect colour, default orange). Global, not per profile.
- While the Hypershift key is held, and lighting is on:
  - Keys with a Hypershift entry light in the chosen colour.
  - The Hypershift key lights in the same colour.
  - Every other key stays faint white (around 15%).
  - The keypad's current brightness applies.
- When the key is released, the normal effect is sent again. Animated effects (wave, spectrum,
  …) restart rather than resume.
- If lighting is off, the Hypershift lights do nothing.
- The Hypershift lights follow the *active* profile's layer, not the profile being edited.

**How:** Synapse's own captures show a per-key custom frame on this keypad: select the custom
effect (`0F/02` args `00 00 08 00 00 00`), then send the frame (`0F/03`, args
`00 00 00 00 14` + 21 RGB triplets). It has never been sent from the plugin. Before building the
lights, a Deck check must confirm:
- that the frame works from the plugin in driver mode;
- which triplet is which key (20 keys + 1 spare?), and whether the thumb key and top button have
  their own LEDs;
- that switching to and from it is fast enough to follow a tap (aim under ~50 ms).

**Fallback** if per-key frames don't work: the whole backlight turns static in the chosen colour
while held. Record the finding in `docs/superpowers/spike-findings.md` either way.

## Left to the builder

- The config shape. For example, a `hypershift` block per profile with the key, and bindings,
  actuation and secondary for its entries, mirroring the existing per-profile fields. Also the
  binding type or field that marks the Hypershift key.
- How layer entries are addressed through the API: a control suffix like the secondary's `.b`
  (for example `k05.h`, `k05.h.b`), or extra parameters. Keep the existing callables working for
  the standard layer.
- How the engine records the layer per press (the per-key `KeyTracker`s and `_binding_for` need
  it), and how a release that crosses a layer change is handled. Whatever the approach, cover
  every order of Hypershift down/up against other keys down/up with tests.
- Where the Hypershift pick sits in Choose…, and the exact look of the locked key and dimmed
  fall-through labels. Follow the existing editor and the CSS Loader look.
- The Lighting tab layout for the new switch and colour, within the page height.
- README: replace the roadmap's "keys 02-20" wording (any key can be the Hypershift key), add
  Hypershift to Features and the Editor section, and keep it distinct from Secondary function.

## Testing

- Engine unit tests (no device):
  - layer switching;
  - fall-through;
  - every press/release ordering around the Hypershift key, for bindings, macros and secondary
    functions;
  - per-layer actuation thresholds;
  - D-pad and wheel on both layers;
  - release_all resetting the layer.
- Config tests: round-trip, loading older files, moving the Hypershift key, profile copy.
- Service tests for the new setters and their validation.
- On the Deck, once per milestone through one browser/hands-on check:
  - FPS with key 19 as Hypershift;
  - WASD fall-through while held;
  - no stuck keys when releasing in odd orders;
  - the editor fits 1280×800 on both layers;
  - Hypershift lights on and off.
