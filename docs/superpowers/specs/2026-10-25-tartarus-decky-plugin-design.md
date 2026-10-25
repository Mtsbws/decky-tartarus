# Decky Tartarus: design

Date: 2026-10-25
Status: approved 2026-10-25

## Intent

The user owns a **Razer Tartarus Pro (2019 model, USB `1532:0244`)**: 20 analog optical keys, a thumb key, an 8-way thumb D-pad and a scroll wheel. They want to use it without Razer Synapse.

Main use: on the couch, with the Tartarus and a wireless mouse plugged into a **Steam Deck (SteamOS, Game Mode)**, streaming PC games (first one: Arc Raiders) from a Windows 11 gaming PC through **Moonlight**. The Deck's own controls are not used at the same time. Synapse cannot run there, and the keypad has no onboard memory, so without Synapse it is a plain USB keyboard with fixed keys.

The immediate pain: the Tartarus has **no Escape key, and no way to open the Steam menu or the Quick Access menu** (the Deck's Steam and `...` buttons), because the Deck's controls are out of reach.

The user already has **Decky Loader** on the Deck and wants this delivered as a Decky plugin. It should combine the features of two Linux projects, [KEYZER](https://github.com/jagbhandal/keyzer) (preferred visual layout) and [OpenTartarus](https://github.com/moparmaniac412/OpenTartarus). Both are MIT-licensed desktop apps that rely on OpenRazer and desktop autostart, and neither works in Game Mode.

## Goals (stage 1)

1. **Background remapping in Game Mode.** The plugin backend grabs the Tartarus's input devices exclusively and re-emits events through a virtual keyboard and mouse (uinput). Moonlight forwards these to the PC like any other keyboard and mouse.
2. **Binding types** (from KEYZER and OpenTartarus):
   - single key (e.g. `Esc`, `F5`)
   - one-shot shortcut, fired once on press (e.g. `Ctrl+C`, `Alt+F4`)
   - held combo, held while the trigger is held (e.g. `W+A` for diagonals)
   - held modifier (`Shift`, `Ctrl`, `Alt`)
   - macro: a sequence of combos sent in order
   - mouse buttons (`LMB`, `RMB`, `MMB`)
   - media keys (`Vol+`, `Vol-`, `Mute`, `Play`)
   - disable (key does nothing)
   - **Steam actions: open Steam menu, open Quick Access menu** (see "Steam menu actions" below)
3. **Bindable controls:** keys 01-20, the thumb key, scroll up, scroll down, wheel click, and the D-pad. The D-pad has two modes: **4-way** (four bindings; diagonals blend two neighbours) and **8-way** (eight independent bindings).
4. **One layout for every game.** The config format is ready for multiple profiles, but stage 1 has exactly one and no profile UI.
5. **Lighting without OpenRazer:** effects static, breathing, spectrum, wave, reactive, ripple, starlight, plus colour and brightness. These are sent as Razer's USB feature-report commands straight from the backend, the same commands OpenRazer's kernel driver sends for `1532:0244`.
6. **UI:**
   - **Quick Access panel (narrow):** connection status, lighting controls (effect, colour, brightness) and an "Edit keys" button. A future profile picker goes here.
   - **Full-screen editor** (Decky route): a keypad picture in KEYZER's style on the left, with each key showing its current binding. Tap a key and the right side offers a quick-pick list (Esc, Steam menu, Quick Access, common keys, mouse, media, Disable), **Record** (press a key or combo on any keyboard to capture it), and **Type** (free-text combo or macro). Changes apply immediately. Also includes the D-pad mode toggle.
7. **Persistence:** settings in a JSON file under Decky's per-plugin settings directory in the user's home. They survive reboots, plugin updates and SteamOS updates. Bindings and lighting are reapplied when the keypad is plugged back in and when the Deck wakes from sleep.
8. **Install** through Decky's Developer Mode (zip or URL) or by copying into `~/homebrew/plugins`. No store submission.

## Steam menu actions

The user wants the Steam menu and Quick Access menu reachable from the keypad. SteamOS opens them with **Ctrl+1** (Steam menu) and **Ctrl+2** (Quick Access) on an external keyboard; the user confirmed these. **Risk:** while Moonlight is fullscreen it grabs the keyboard, so those keystrokes may go to the PC and never reach Steam.

*Builder's call (proposed):* treat these as dedicated action bindings rather than plain combos. On press, the backend notifies the frontend, and the frontend opens the menu through Steam's client navigation API (exposed via `@decky/ui`), so Moonlight's keyboard grab doesn't matter. Fall back to emitting Ctrl+1 / Ctrl+2 if the API route fails. The spike decides which one ships; the user cares about the menus opening, not the mechanism.

## Spike first (throwaway)

Before the real build, a throwaway plugin or script on the Deck answers four questions:

1. Do EVIOCGRAB plus uinput re-emission work in Game Mode, and does Moonlight forward the virtual keyboard/mouse to the PC with no noticeable added latency?
2. Which mechanism opens the Steam menu and Quick Access while Moonlight is fullscreen (see above)?
3. Does a lighting command sent over hidraw (`HIDIOCSFEATURE`, 90-byte Razer report, OpenRazer's transaction ID for this device) change the keypad's lighting?
4. What does the keypad send by default, per physical control (evdev codes, and which event nodes/interfaces they arrive on)? This becomes the shipped key map and the keypad picture's labels.

Findings feed back into the plan. The spike's code is not kept.

## Stage 2 (later, separate design)

Capture Synapse's USB traffic (Wireshark + USBPcap on the Windows PC) while the user toggles analog settings. Then add **dual actuation** (half press sends one binding, full press another, e.g. `W` / `Shift+W`) and **actuation depth**. Whether this needs depth reporting turned on (plugin does the logic) or a device-side setup command is unknown until the capture.

## Non-goals

- Game profiles and per-game switching (planned for later; the panel is where the picker would go)
- Hypershift / second layer
- The rare setup with the keypad plugged directly into the Windows PC (in-game bindings cover it)
- Analog features (stage 2)
- Calibration and support for other Razer devices
- Writing to device memory or firmware

## Anti-goals (failure even if it "works")

- **The keypad becomes unusable when the plugin is stopped, crashes or is uninstalled.** The grab must be released and the keypad must fall back to its default keys.
- **Any risk to the device.** Send only lighting commands known from OpenRazer for this device ID; never probe unknown commands or touch firmware update paths.
- **Changes to SteamOS outside the home directory** (no disabling the read-only root, no pacman packages, no system udev rules). Everything ships inside the plugin.
- Noticeable input latency, or measurable CPU or battery drain while idle.
- Shipping Razer's copyrighted device images (KEYZER's bundled images are Razer's). The keypad picture is our own drawing.

## Constraints and known facts

- Decky plugin: TypeScript/React frontend (`@decky/ui`, `@decky/api`) and a Python backend. The backend needs the `root` flag in `plugin.json` so it can access `/dev/input`, `/dev/uinput` and `/dev/hidraw*`.
- Decky's Python can't rely on pip-installed native modules on the Deck. Use only the standard library (ctypes/fcntl ioctls for evdev, uinput and hidraw) or modules vendored into the plugin.
- The Tartarus Pro exposes several USB interfaces / event nodes. All that carry key input must be grabbed.
- The OpenRazer source (driver C code and `daemon` Python) is the reference for report layout, transaction ID and effect commands for `1532:0244`. OpenTartarus and KEYZER (MIT) are references for binding semantics and the UI.
- Hot-plug and resume must be handled without the user opening the plugin.
- Dev loop: build on the Mac, deploy to the Deck over SSH.

## Decisions made during review (Claude's calls, not the user's)

- **Lighting effects are firmware-native only.** Ship each listed effect only if OpenRazer drives it on `1532:0244` with a single device command. Effects that OpenRazer renders in software by streaming frames (likely ripple, possibly others) are dropped rather than run as a backend loop, to protect idle CPU and battery.
- **The spike is a hard gate.** If grab and uinput re-emission (spike question 1) don't work through Moonlight, stop and redesign with the user. If only lighting fails, ship remapping without lighting. If only the menu actions fail, ship without them and raise it with the user.
- **Releasing the grab.** Grabs and uinput devices are tied to file descriptors, so process death (crash or kill) releases them. On Decky unload, the backend's unload hook explicitly ungrabs and destroys the virtual devices. No separate watchdog process.
- **Steam menu fallback order:** `@decky/ui` navigation API, then Ctrl+1 / Ctrl+2 through the virtual keyboard. If both fail under fullscreen Moonlight, the action ships disabled with a note, and the user is asked about alternatives (for example a virtual controller's Guide button).
- **Record** reads raw, pre-remap events from the Tartarus and from any other keyboard attached to the Deck. Whatever is pressed becomes the binding's output.
- **4-way D-pad diagonals** hold both neighbouring bindings at once (the union of the two).
- **Virtual device naming:** the virtual keyboard and mouse get distinct names (e.g. `Decky Tartarus Keyboard`) so they can be told apart in logs and in any Steam Input settings. Spike question 1 confirms Moonlight receives them.

## Left to the builder

Project scaffolding (start from the official decky-plugin-template), config schema details (must hold a list of profiles with one active), how macros are timed, hot-plug detection method, keypad drawing (SVG), exact quick-pick list contents beyond those named above, logging, and tests.
