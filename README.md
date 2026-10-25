# Decky Tartarus

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for the
**Razer Tartarus Pro** (2019, USB `1532:0244`) on a Steam Deck in Game Mode. No Synapse,
no OpenRazer.

- Remaps every control: keys 01-20 (20 is the big thumb key), the button above the
  D-pad, scroll up/down, wheel click and the D-pad (4-way or 8-way).
- Opens the Steam menu and Quick Access menu from a key, also while Moonlight is fullscreen.
- Sets the keypad's lighting: static, breathing, spectrum, wave, reactive, starlight,
  colour and brightness.
- Remapped input goes out through a virtual keyboard and mouse (`Decky Tartarus Keyboard`,
  `Decky Tartarus Mouse`), so streaming apps such as Moonlight forward it like any keyboard.

Quick Access → Tartarus shows whether the keypad is connected, the lighting controls and
**Edit keys**. The editor shows the keypad: pick a key, then choose a quick pick, press
**Record** and press a key or combo on the keypad or any keyboard, or **Type** a binding.
Changes apply at once.

## Install

The backend needs root (`/dev/input`, `/dev/uinput`, `/dev/hidraw*`).

- **From the zip:** build it with `scripts/package.sh` (needs `pnpm`), copy
  `out/decky-tartarus.zip` to the Deck, then in Decky → Settings → enable Developer Mode →
  Developer → Install Plugin from ZIP File (or from a URL to the zip).
- **By hand:** copy the plugin folder to `~/homebrew/plugins/decky-tartarus/`
  (needs `sudo`), then reload Decky or reboot.

## Binding text

| Text | Does |
|---|---|
| `Esc`, `F5`, `A` | one key, held while the trigger is held |
| `Shift`, `Ctrl`, `Alt` | held modifier |
| `Ctrl+C`, `Alt+F4` | shortcut, sent once on press |
| `hold:W+A` | keys held together while the trigger is held |
| `A, B, Ctrl+C` | macro: the steps in order |
| `LMB`, `RMB`, `MMB`, `Mouse4`, `Mouse5`, `WheelUp`, `WheelDown` | mouse |
| `Vol+`, `Vol-`, `Mute`, `Play`, `Next`, `Prev` | media keys |
| `steam:menu`, `steam:qam` | open or close the Steam menu / Quick Access |
| `disable` | the key does nothing |

Names are not case-sensitive. In 4-way mode a diagonal on the D-pad holds both
neighbouring directions' bindings.

## Settings

One JSON file: `~/homebrew/settings/decky-tartarus/settings.json`. It survives reboots and
plugin updates. A file that can't be read is kept as `settings.json.corrupt-<time>` and the
plugin starts with factory keys. Bindings and lighting are reapplied when the keypad is
plugged back in and after sleep.

## Notes

- **Steam menu keys** use Steam's own navigation, not the Ctrl+1 / Ctrl+2 shortcuts: under
  fullscreen Moonlight those keystrokes go to the PC and nothing opens on the Deck.
- **Record** can't capture wheel ticks; type `WheelUp` / `WheelDown` instead.
- Only lighting effects the keypad runs itself are offered. Ripple needs software-streamed
  frames and is left out. The plugin sends only commands OpenRazer sends for this keypad.

## Uninstall

Remove it in Decky. The keypad goes back to its factory keys at once: the grab and the
virtual devices are tied to the plugin's process, so even a crash or kill releases them.
The settings file stays in `~/homebrew/settings/decky-tartarus/`; delete it if you want.

## Credits

- [KEYZER](https://github.com/jagbhandal/keyzer) (MIT): binding types and the editor layout.
- [OpenTartarus](https://github.com/moparmaniac412/OpenTartarus) (MIT): binding semantics.
- [OpenRazer](https://github.com/openrazer/openrazer): reference for the lighting report
  format and effect commands.

The keypad picture is our own drawing. MIT licence, see `LICENSE`.
