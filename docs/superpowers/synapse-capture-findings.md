# Synapse USB capture findings (2026-10-27)

Captures: Synapse 4.0.86 on Windows, Tartarus Pro `1532:0244` at device address 5, recorded with
`scripts/record-synapse.ps1` (25 files; the user keeps them outside the repo). Read with a small
stdlib USBPcap parser, no tshark. Nothing was sent to the keypad.

All Razer commands are 90-byte `SET_REPORT` feature reports to **interface 2** (`wIndex 2`),
each followed by a `GET_REPORT` whose status byte is `0x02` (success) unless noted. This matches the
layout in `spike-findings.md` and `py_modules/tartarus/lighting.py`.

## Profile LEDs: confirmed

One command per profile switch, nothing else (Synapse sent the same when re-selecting the active
profile, and when switching with a keypad key):

```
class 0x0F, command 0x02, data_size 0x09
args: 01 0B 01 00 01 01 RR GG BB
```

The three profile LEDs are one RGB LED (`0x0B`) to the firmware. Each channel drives one LED:

| Profile | LEDs seen (top/middle/bottom) | RR GG BB |
|---|---|---|
| 1 | 100 orange | FF 00 00 |
| 2 | 010 green | 00 FF 00 |
| 3 | 001 blue | 00 00 FF |
| 4 | 110 | FF FF 00 |
| 5 | 101 | FF 00 FF |
| 6 | 011 | 00 FF FF |
| 7 | 111 | FF FF FF |
| 8 | 000 | 00 00 00 |

So: R = top (orange), G = middle (green), B = bottom (blue). All 8 combinations exist, which fits
the spec's cap of 8 profiles.

Compared with OpenRazer and the plugin: it is the same extended-matrix "static" command the
plugin sends for the backlight, with three differences. LED `0x0B` instead of `0x05`. `args[4]` is
`0x01` where OpenRazer and the plugin send `0x00`. And Synapse's transaction IDs vary per command
(`0x00`-`0x1E`), where the plugin always sends `0x1F`; the keypad accepted all of them. OpenRazer has no
profile-LED support for this PID; its older Tartarus models use class `0x03` LEDs `0x0C`-`0x0E`,
and Synapse's one class-`0x03` probe here (`03/80` for LED `0x0D`) got status `0x05` (not supported).

## Analog (actuation, secondary function): confirmed host-side

Changing the actuation point (key 01 to 1.5, 3.6 and 2.5 mm; all keys to 2.5 mm), turning the
secondary function on and off, and changing it sent **no command to the keypad at all**. The only
traffic in those captures is Synapse's periodic lighting frame.

Instead the keypad streams key depth. Interrupt endpoint `0x82` (interface 1) sends 24-byte
input reports, report ID `0x06`, one byte per key: `0x00` released to `0xFF` fully pressed, with
around 200 distinct values in one slow press. It sends whenever a value changes (reports about 1 ms
apart while moving). Byte 1 is key 01 (confirmed). The slow presses with the secondary function on
and off look identical at USB level. Synapse turns depth into actions itself.

No standard keyboard reports (endpoint `0x81`) arrived for these presses: Synapse runs the
keypad in driver mode (below), where key 01 only shows up as depth.

## Synapse startup: device mode

At startup Synapse asks the device mode (`00/84`, reply `0x00`), sets it with
**`00/04` args `03 00`** (driver mode), and later reads back `0x03`. Then it selects custom-frame
lighting (`0F/02` args `00 00 08 00 00 00`) and sends a full frame every 5 s
(`0F/03`, args `00 00 00 00 14` + 21 RGB triplets), plus brightness `0F/04 01 00 7F` (50 %, the
same command as the plugin's). The keypad kept device address 5 through all later captures, so
there was no reset or re-enumeration that the capture could see.

This conflicts with the plugin's rule "never send `00/04`", which comes from OpenRazer's note that
the Tartarus Pro resets on it. Here it didn't, at least under Windows with this firmware.

Other startup queries: `00/82` (serial number, ASCII), `00/81`, `00/86`, `00/87`; `07/8B`
answered "not supported".

## Deck and Windows checks (2026-10-27, afternoon)

Tools: `scripts/read-depth.py` (read-only hidraw logger) and `scripts/deck-probe.py` (fixed
commands: `getmode`, `setmode 03|00`, `led R G B`, `read N`), each send approved by the user.
Windows timing came from a USBPcap capture next to a key-log window, matched by timestamp.

**Normal mode (Deck):**

- No `0x06` depth reports. Keys 01-20 arrive only as on/off boot-keyboard reports (report ID 1,
  interface 1), as evdev keys.
- Interface 1's descriptor declares report IDs 1-6:
  - 2 is consumer control.
  - 3 is system control (usages `0x81`-`0x83`: power down, sleep, wake up).
  - 4, 5 and 6 are 23-byte vendor-like fields (GD usage `0x03`, 0-255).
- **The profile-LED command works in normal mode.** `led 00 00 FF` turned the top LED off and
  the bottom LED on, status `0x02`.

**Driver mode (`00/04 03 00`) on the Deck:**

- Reply status `0x02`; `00/84` then reads `0x03`.
- Keys 01-20 send no evdev events. Interface 1 streams `0x06` depth reports for all of them:
  - byte n is key n for keys 01-19
  - the thumb key is byte 20
  - bytes 21-23 stayed `0x00`
- The button above the D-pad (`KEY_LEFTALT`, interface 0), the D-pad (interface 0) and the
  wheel (interface 2) behave exactly as in normal mode.
- `00/04 00 00` returns to normal mode at once: key 01 types `1` again.
- **No reset or re-enumeration from either switch.** The disconnects seen on the Deck were the
  whole USB hub (`05e3:0608`, together with the Realtek LAN adapter). The same hub drop also
  happened on Oct 25 and on Oct 27 at 09:53, with the keypad in normal mode.
- **A replug resets the keypad to normal mode.** After the hub drop with the keypad in driver
  mode, `00/84` read `0x00`.
- About 3 s after the first `setmode 03`, the Deck suspended. Steam requested it (`dbus-send`
  from the user session). The plugin was running and passes unknown key codes through. A
  system-control sleep key from report 3 reaching Steam is a possible cause, unconfirmed: with
  the probe grabbing the nodes, no sleep key was seen while pressing keys in driver mode.
  systemd-logind also watches the keypad's keyboard node for system buttons.

**Depth to millimetres (Windows, Synapse, single function on key 01):**

| Setting | Fires at depth | Released at depth |
|---|---|---|
| 1.5 mm | about 16 | 14-17 |
| 2.5 mm | about 120 | 112-114 |
| 3.6 mm | about 251 | 245-246 |

The gap between firing and releasing is about the key-log latency, so Synapse uses little or no
hysteresis. The curve is close to linear but not quite (linear 1.5 → 0, 3.6 → 255 would put
2.5 mm at 121).

**Synapse secondary function (A at 1.5 mm, B at 3.6 mm):**

- A fired at depth about 4. This is a Synapse quirk; the setting was saved at 1.5 mm.
- B fired at about 252, **with A still held**.
- On the way up, B released at about 250-253 and A at about 4.

**Prior art:** InputPlumber PR #518 (ShadowBlip, open, not merged) implements Tartarus Pro analog
mode host-side:

- linear actuation 1.4-3.6 mm over depth 0-255
- dual function
- a "retrigger" (rapid trigger) option
- device mode managed outside it

Read for ideas only; it's GPL.

**Plugin in driver mode (Deck check M2, 2026-10-27):** the profile-LED command works in driver
mode (status `0x02`; patterns changed with the game). The LEDs stayed correct through effect and
brightness changes, switch off/on, replug, suspend/resume and plugin disable/enable. Keys 01-20
typed at a light press, the top button, D-pad and wheel worked, and the Deck didn't suspend.
Every unload stopped in 0.2 s.

**Normal-mode hardware point (Deck check M3, 2026-10-27, key 01):** in normal mode, `read 30`
showed the key-down live. The user held the key once it appeared, sent `setmode 03` from a
second terminal, then released slowly. The first depth report after the switch:

| Run | Held | First depth | mm (DEPTH_POINTS) |
|---|---|---|---|
| 1 | 12.6 s | 95 | 2.3 |
| 2 | 16.6 s | 185 | 3.05 |
| 3 | 7.9 s | 189 | 3.1 |

These are upper bounds. The key-down reached the user through ssh with a delay, so the key went on
past the point before the user stopped. Run 1 puts the hardware point at **2.3 mm or less**, which
is more than 1.8 mm (depth 47). In all three runs, `setmode 03` sent an evdev release (`value 0`)
for the held key at the moment of the switch, so entering driver mode can't leave a normal-mode
key stuck.

## Still a guess

- Whether profile-LED values between `00` and `FF` dim it.
- Whether a backlight effect or brightness change clears the profile LEDs by itself: the plugin
  re-sends them after every lighting change, so the Deck check below can't tell.
- What `args[4] = 0x01` means (OpenRazer and the plugin send `0x00` for static).
- The cause of the suspend after the first `setmode 03`.
- The exact normal-mode hardware point: only an upper bound (2.3 mm) is measured.

## Terms (user)

- **Secondary function** (dual actuation): per key, a first binding at one actuation point and a
  second at another, e.g. `A` at 1.5 mm and `B` at 3.6 mm. Actuation can be set per key or for all
  keys.
- **Hypershift**: a key (e.g. 01) that, while held, switches keys 02-20 to a second set of bindings.
  Not captured (USB-wise it is probably host-side too). Deferred until the secondary function
  works (user, 2026-10-27).
