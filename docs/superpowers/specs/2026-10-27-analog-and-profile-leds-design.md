# Analog keys and profile LEDs: design

Date: 2026-10-27. Follows the v1 design (`2026-10-25-tartarus-decky-plugin-design.md`) and game
profiles (`2026-10-25-game-profiles-design.md`). Evidence is in `../synapse-capture-findings.md`
and `../spike-findings.md`.

## Why

The user plays RuneScape on the Deck and Ghost Recon Wildlands over Moonlight. They want what
Synapse gives on Windows:

- **Actuation point** per key, adjustable 1.5-3.6 mm like Synapse, on every key 01-20, in every
  profile.
- **Secondary function**: one key becomes two separate keys, A at a shallow point and B at a deep
  one. Use cases: crouch / prone, walk / dodge roll.
- **Profile LEDs**: the three LEDs above the D-pad show which profile is active, as the
  game-profiles design prepared.

## How the keypad does it (facts)

- The keypad has a **normal mode** (keys 01-20 are plain on/off keyboard keys at a fixed hardware
  point) and a **driver mode**:
  - Keys 01-20 send no key events.
  - Instead, interface 1 streams **depth reports**: report ID `0x06`, byte n = depth of key n
    (`0x00` up to `0xFF` fully down), the thumb key (k20) is byte 20, bytes 21-23 unused.
  - Reports arrive only when a value changes, about 1 ms apart while a key moves.
  - The top button, D-pad and wheel behave the same in both modes.
- Synapse does all analog work on the PC. The keypad stores no actuation settings.
- Commands (all checked on the Deck, status `0x02`):
  - Get mode: class `0x00` cmd `0x84`, args `00 00`. Reply args[0] is the mode.
  - Driver mode: `0x00`/`0x04`, args `03 00`. Normal mode: same with `00 00`. Both take effect
    at once with no reset.
  - Profile LEDs: `0x0F`/`0x02`, args `01 0B 01 00 01 01 R G B`. R = top LED, G = middle,
    B = bottom; `FF` on, `00` off. Works in normal mode; driver mode not yet checked.
- **A replug (or USB hub reset) puts the keypad back in normal mode.**
- Measured depth where Synapse fires a key: 1.5 mm ≈ 16, 2.5 mm ≈ 120, 3.6 mm ≈ 251.

## Goals

1. **Driver mode whenever the plugin has the keypad**, in every profile. Analog behaviour is built
   from depth reports on the Deck.
2. **Actuation point per key** for keys 01-20, 1.5-3.6 mm in 0.1 mm steps, stored per profile, with
   a way to set **all keys** of a profile at once.
3. **Secondary function per key** (keys 01-20): a second binding B at a deeper actuation point.
4. **Profile LEDs** shown on every profile switch, on connect and on resume, with a pattern picker
   in the editor.

## Non-goals

- **Hypershift.** The user decided it waits until the secondary function works.
- Rapid trigger / retrigger (InputPlumber has it; not asked for).
- Analog output (e.g. depth as a joystick axis).
- Analog on the top button, D-pad or wheel (they aren't analog).
- Per-game backlight lighting.

## Anti-goals

- **Keys that leak to Steam or the system.** The first driver-mode test was followed by a Steam
  suspend 3 s later. The cause is unconfirmed; a passed-through system-control key is the main
  suspect. Keys that could reach the system must not.
- **Noticeable latency.** A key fires on the report that crosses its point. No buffering or
  smoothing that waits for later reports.
- **CPU drain while idle.** Nothing runs when no key moves, beyond today's polling.
- **Sending commands not in the list above** (the v1 rule, with the list now extended by evidence).
- **Copying InputPlumber code** (GPL). Reading it for ideas is fine.

## Accepted trade-off (user)

v1's anti-goal "the keypad becomes unusable when the plugin stops or crashes" can't fully hold in
driver mode: **if the plugin dies without cleaning up, keys 01-20 stay dead** until the keypad is
replugged (confirmed to restore normal mode) or the plugin starts again. The user accepted this to
have actuation everywhere. Everything that *can* restore normal mode must:

- a clean stop or uninstall sends normal mode before releasing the keypad
- a plugin restart re-enters driver mode and works again

## Design

### Device mode lifecycle

- **On connect** (including the reconnect after resume and after a replug):
  1. grab the evdev nodes as today
  2. send driver mode and check the status is `0x02`
  3. start reading interface 1's hidraw node for depth reports
  4. apply lighting, then the active profile's LEDs
- **If driver mode fails** (no interface 1 or 2 hidraw node, OSError, status not `0x02`), keep
  going in normal mode: keys work as on/off keys at the hardware point, no analog, no secondary
  functions. Log it and show it in the panel (e.g. "Analog keys unavailable").
- **On stop**: release all held outputs, send normal mode, then ungrab and close as today.
  - **Unload bug to fix:** on the Deck, Decky reported the plugin "still alive 5 seconds after
    stop request" and SIGKILLed it. A killed plugin never sends normal mode, so `stop()` must
    finish well inside that limit. The builder finds the cause (the supervisor, a pending macro,
    the hidraw reader, the frontend…) and fixes it. *Claude's call:* `stop()` targets under
    1 s; it releases held outputs, then sends normal mode, before anything that can block.
- **Analog switch** (*Claude's call*): a global panel toggle "Analog keys", on by default. Off =
  normal mode, today's behaviour. It's an escape hatch if driver mode misbehaves, and a quick way
  to compare. It is global, not per profile, because the user wants analog in every profile.
  It's stored in the settings file and survives restarts. Switching it at runtime first releases
  all held outputs, then sends the mode and starts or stops the depth reader.
- **Mode checks** (*Claude's call*): no periodic `00/84` polling. A hub reset shows up as a
  disconnect plus reconnect, which re-sends driver mode anyway.

### Keys the plugin must never pass on

- In both modes, the plugin drops `KEY_POWER`, `KEY_SLEEP` and `KEY_WAKEUP` coming from the
  keypad, instead of passing unknown codes to the virtual keyboard.
- In driver mode, keys 01-20 send no evdev events. If one of their factory codes arrives anyway,
  drop it and log it once. The top button and D-pad (interface 0) and the wheel (interface 2)
  still arrive as evdev events and are handled as today.
- *Claude's call:* other unknown codes keep passing through as today; only these system keys
  are dropped.

### From depth to key presses

Per key, each depth report is compared with that key's thresholds; the first report that crosses
a threshold acts.

**Millimetres to depth** (*Claude's call*): piecewise linear through the measured points
(1.5 → 16, 2.5 → 120, 3.6 → 251), rounded, so a setting matches what Synapse does on the same
keypad. The table lives in one place so it can be refined.

**Hysteresis** (*Claude's call*): a key releases when depth drops below its fire point minus 8
(about 0.07 mm). This stops chatter at the threshold. Synapse shows little or none, and 8 is small
enough not to feel different. Release at 1.5 mm is therefore at depth 8.

**Single function:** down when depth ≥ fire point, up when depth < fire point − 8.

**Secondary function** (user's semantics, deliberately unlike Synapse, which keeps A held under B):

- Going down past A's point: **A down**, held for as long as the key stays between A and B
  (crouch stays held).
- Going further past B's point: **A up, then B down**. Only one of the two is ever held.
- Coming back up below B's release point: **B up**. A does **not** fire again.
- Further up, below A's release point: the key re-arms. The next press starts at A.
- A report that jumps straight past B (fast press) sends only B, never an A tap first
  (*Claude's call*, follows "two separate keys").
- If the key comes up from B, stays between A and B, then goes back past B: B fires again (B's
  own hysteresis). A stays silent until the key re-arms.

B must sit at least 0.5 mm deeper than A (*Claude's call*), so the two keys can't fight. The
editor enforces it.

**Into the engine:** A behaves exactly like today's control `kNN`: same binding types (keys,
combos, macros, Steam actions, mouse buttons) and the same held/release bookkeeping. B is a second
binding slot on the same key with the same binding types. How the engine names it (e.g. a
`kNN.b` control) is the builder's call. Releases on disconnect, profile switch and stop cover B
too.

**Recording (binding picker):** the existing "press a key on the keypad" capture runs with
`passthrough` on and reads factory key codes. In driver mode the same capture must work from depth
reports. *Claude's call:* the first key to reach depth 16 (1.5 mm) is the one recorded,
  whatever its own setting.

### Data model

Per profile, with defaults so existing files load unchanged:

- `actuation`: control → mm, keys k01-k20 only. Missing = the profile default.
- *Claude's call:* the **default for a key without a setting is 1.5 mm**, Synapse's own default.
  The normal-mode hardware point isn't known yet. The builder measures it once in driver mode
  (depth at which normal mode fired) and notes it in the findings. If it's more than 0.3 mm
  deeper, the builder asks the user which default to ship before release; the rest of the work
  goes on meanwhile.
- `secondary`: control → `{binding, actuation}` for keys that have a B. Missing = none.
- Whether this needs a schema bump (`SCHEMA_VERSION` 3 and a migration) or loads as optional v2
  fields is the builder's call. A v2 file must load without losing anything, and the backup rule
  from game profiles applies if the file is rewritten.
- "Copy from" on profile creation copies actuation and secondary functions too.
- Bad values (outside 1.5-3.6, not on a 0.1 step, B not 0.5 mm deeper than A, a binding that doesn't
  parse) are dropped per key with a log line, like today's bad-binding rule.

### Editor

Pattern: today's editor (profile bar, keypad drawing, binding picker per control). Additions:

- Selecting a key 01-20 shows, next to its binding:
  - **Actuation**: a slider, 1.5-3.6 mm, 0.1 mm steps, showing the value in mm.
  - **Secondary function**: off/on. When on, a second binding (same picker) and its actuation
    slider.
- **All keys**: a control that sets the actuation of all 20 keys in the profile to one value. It
  doesn't touch secondary functions. *Claude's call:* if a key's B would end up less than 0.5 mm
  below the new value, B moves down to keep the gap, capped at 3.6 mm; if that's impossible, the
  value is refused.
- The keypad drawing marks keys with a non-default actuation or a secondary function (badge or
  label; looks are the builder's call).
- When analog is off or unavailable, these controls stay editable but show a note that they apply
  only with analog keys on.
- Steam Deck QAM is narrow and gamepad-driven: everything works with the D-pad and A button, as the
  current editor does.

### Profile LEDs

- On every profile switch, on connect (after lighting) and on resume, send the active profile's
  `leds` as the LED command (`FF`/`00` per LED). Default is all off.
- If the command fails or the status isn't `0x02`, log it and leave everything else alone (as
  game profiles specified).
- Editor: the profile bar shows the active pattern and lets the user pick another free pattern
  among the 7 lit ones (Default stays all off, as game profiles specified). Every profile keeps a
  unique pattern.
- To check on hardware during building, with the user approving each send:
  - The LED command in driver mode.
  - Whether changing backlight effect or brightness clears it.
  - *Claude's call:* re-send the LEDs after every lighting change anyway (cheap).
  - If the LED command doesn't work in driver mode, try sending it just before entering driver
    mode, in case the LEDs keep their state. If that fails too, stop and ask the user.

## Constraints

- Everything from the v1 and game-profiles designs still holds:
  - stdlib-only Python
  - root backend
  - atomic settings writes
  - nothing outside the home directory
  - Python tests for logic
- Tests cover at least:
  - mm → depth mapping and hysteresis
  - single and secondary state machines, including fast jumps, re-arm, and a B re-press without
    re-arm
  - release on disconnect, profile switch and stop, with A or B held
  - the dropped system keys
  - the mode lifecycle with a fake hidraw (driver mode OK, failure fallback, normal mode on stop)
  - config load and save of the new fields, including bad values
  - LED sending on switch, connect and resume
- **Hardware checks need the user.** Claude has no sudo on the Deck and asks before anything new
  is sent to the keypad. `scripts/deck-probe.py` and `scripts/read-depth.py` are the existing
  tools for this.
- The Deck's USB hub (`05e3:0608`) sometimes drops and comes back on its own. The plugin's
  existing reconnect handles it; with this design it also re-enters driver mode.

## Left to the builder

- Engine shape for B, the hidraw reader, and how depth events reach the engine.
- Schema version choice.
- Editor layout details within the pattern above.
- Cause and fix of the slow unload.
