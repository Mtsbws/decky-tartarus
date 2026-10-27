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

## Still a guess

- Whether the profile-LED command works in **normal mode** (no `00/04`), the mode the plugin
  uses. Every capture was in driver mode.
- Whether the key-depth reports (`0x06` on interface 1) are sent in **normal mode** too, or only in
  driver mode. If only in driver mode, analog features need `00/04 03 00`. Then the keypad
  sends no plain keyboard input, which clashes with the anti-goal "the keypad stays usable when the
  plugin stops". This can be checked on the Deck by reading interface 1's hidraw node,
  read-only, while pressing a key slowly.
- Byte order of the other keys in the depth report. Key 01 = byte 1 is confirmed, and the
  profile-switch key in `19b` (key 14, from the user's memory) showed up as byte 14. So byte n is
  probably key n for keys 01-20; bytes 21-23 (thumb key? D-pad?) are unknown.
- How depth maps to millimetres (presumably 0x00-0xFF over the 1.5-3.6 mm range or the full travel).
- Whether the profile LED stays as set when the plugin changes backlight effects or brightness, and
  whether values between `00` and `FF` dim it.
- What `args[4] = 0x01` means (OpenRazer and the plugin send `0x00` for static).

## Terms (user)

- **Secondary function** (dual actuation): per key, a first binding at one actuation point and a
  second at another, e.g. `A` at 1.5 mm and `B` at 3.6 mm. Actuation can be set per key or for all
  keys.
- **Hypershift**: a key (e.g. 01) that, while held, switches keys 02-20 to a second set of bindings.
  Not captured (USB-wise it is probably host-side too); the user wants it added later.
