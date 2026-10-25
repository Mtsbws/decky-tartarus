# Spike findings (M0)

Date: 2026-10-25. Deck: SteamOS kernel `7.2.7-valve2`, Decky Loader v3.3.0, system Python 3.14 (Decky runs its own bundled Python). Keypad: Razer Tartarus Pro `1532:0244`, plugged in through a USB hub. Spike code and raw logs are on the `spike` branch (`spike/`, `spike/data/`). That branch is never merged.

All four spike questions passed. The plan goes ahead as written, with the amendments marked `(amended from spike)`.

## Access and deploy loop

- SSH: `Host deck` in `~/.ssh/config` → `steamdeck.local` (it was 192.168.0.245), user `deck`, key `~/.ssh/id_ed25519`. The user enabled `sshd` on the Deck.
- Root: the user types `ssh -t deck sudo …` in their own terminal. Claude has no sudo on the Deck, and sudoers is not edited.
- **Decky live-reloads.** It watches `~/homebrew/plugins/` with inotify. Copying changed files into a plugin folder unloads the backend and frontend and loads them again within about a second, with no restart. One `cp` burst can trigger two reloads, which is harmless.
- **Never `systemctl restart plugin_loader` for a deploy.** Doing that right after a copy left the old plugin process running ("Unit process … remains running after unit stopped"). It still held the grab, so the new copy's `EVIOCGRAB` failed with `EBUSY`, and Game Mode hung on load until the user rebooted.
- Decky re-owns plugin folders as root, so a `deck`-owned plugin folder doesn't stay that way. Deploys need one sudo copy.
- The deploy that worked:
  ```
  # Mac (no sudo): build and stage
  pnpm build
  rsync -a --delete dist main.py plugin.json package.json LICENSE py_modules deck:~/decky-tartarus-stage/
  # user's terminal: one sudo copy; Decky reloads it by itself
  ssh -t deck 'sudo mkdir -p /home/deck/homebrew/plugins/decky-tartarus && sudo cp -r /home/deck/decky-tartarus-stage/. /home/deck/homebrew/plugins/decky-tartarus/'
  ```
  Use `rsync` into the stage folder, not `cp`, so deleted files go away. The sudo `cp` doesn't remove files from the plugin folder. If a file is removed from the plugin, delete it there by hand.
- Backend logs: `journalctl -u plugin_loader` (no sudo needed) and `~/homebrew/logs/<plugin>/`. Frontend messages can be read on the Mac by sending them through a `log` callable into `decky.logger`.

## Control → evdev map (S1)

The keypad has four event nodes on three USB interfaces. Event and hidraw numbers **change on replug and reboot** (event18 → event24 → event11 during the spike), so discover them through sysfs.

| Node (name) | USB iface | Caps | Carries |
|---|---|---|---|
| `Razer Razer Tartarus Pro` | 0 | KEY, MSC, LED, REP | D-pad, button above the D-pad |
| `Razer Razer Tartarus Pro Keyboard` | 1 | KEY, REL(HWHEEL), ABS, MSC, REP | keys 01-20 |
| `Razer Razer Tartarus Pro` | 1 | ABS only | nothing seen |
| `Razer Razer Tartarus Pro` | 2 | KEY(BTN_LEFT..EXTRA), REL(X, Y, WHEEL, WHEEL_HI_RES), MSC | scroll wheel |

| Control id | Physical | Factory code (EV_KEY unless noted) |
|---|---|---|
| k01-k05 | row 1 | `KEY_1 KEY_2 KEY_3 KEY_4 KEY_5` |
| k06-k10 | row 2 | `KEY_TAB KEY_Q KEY_W KEY_E KEY_R` |
| k11-k15 | row 3 | `KEY_CAPSLOCK KEY_A KEY_S KEY_D KEY_F` |
| k16-k19 | row 4 (4 keys) | `KEY_LEFTSHIFT KEY_Z KEY_X KEY_C` |
| k20 | thumb key (the big space-bar key; Razer numbers it 20) | `KEY_SPACE` |
| top_button | the small button above the D-pad | `KEY_LEFTALT` (iface 0) |
| wheel_up / wheel_down | scroll wheel | `EV_REL REL_WHEEL +1 / -1`, each with `REL_WHEEL_HI_RES ±120` |
| wheel_click | wheel press | `BTN_MIDDLE` (iface 2) |
| dpad_up/right/down/left | D-pad | `KEY_UP KEY_RIGHT KEY_DOWN KEY_LEFT` (iface 0) |

There is **no separate thumb key** besides k20. The plan's `thumb` control does not exist, and the button above the D-pad is a control the plan didn't have.

Capslock on the keypad toggles the Deck's caps-lock LED state (`EV_LED LED_CAPSL` on the iface 0 node).

## D-pad

The D-pad is 8-way in hardware and sends **two cardinal codes for a diagonal**, for example up-right = `KEY_UP` + `KEY_RIGHT`. There are no diagonal codes of its own. Holding a direction gives kernel autorepeat (`value 2`) at about 34 ms. Task 3's design (resolve diagonals from pressed cardinals) stands.

## hidraw / lighting interface

Each interface has one hidraw node. Lighting goes to the **USB interface 2** hidraw: `bInterfaceProtocol 02` (mouse), which matches OpenRazer's `wIndex 0x02` for this PID. Find it through sysfs. The resolved path contains `:1.2/` and `:1532:0244.`.

## Q1: grab + uinput through Moonlight (hard gate): PASS

`spike/passthrough.py` grabbed all four nodes and re-emitted through uinput `Decky Tartarus Keyboard` and `Decky Tartarus Mouse` (`BUS_USB`, vendor `0x1209`, product `0x0001`). It dropped `value 2` repeats. The user confirmed these in Game Mode → Moonlight → Arc Raiders:

- key 01 → Esc worked, and wheel click → right mouse button worked
- scrolling and movement keys felt unchanged
- `kill -9` → factory keys back at once, with no replug
- Ctrl+C stop (SIGINT, same handler as SIGTERM) → ungrab and destroy, factory keys back

Latency over 294 events:

| Measure | p50 | p99 | max |
|---|---|---|---|
| read → write (processing) | 25 µs | 116 µs | 134 µs |
| kernel event timestamp → write (`EVIOCSCLOCKID` monotonic) | 89 µs | 190 µs | 196 µs |

The virtual mouse didn't declare `REL_WHEEL_HI_RES`, so the kernel dropped those writes. Scrolling still worked through `REL_WHEEL`.

## Q2: Steam menu mechanism: `STEAM_ACTION_MODE = "api"`, with a toggle

| Key | Steam UI | Moonlight fullscreen (Arc Raiders) |
|---|---|---|
| 02 `Navigation.OpenSideMenu(SideMenu.Main)` | opened; 2nd press did not close | opened; 2nd press did not close |
| 03 `Navigation.OpenQuickAccessMenu()` | opened; 2nd press did not close | opened; 2nd press did not close |
| 02/03 with toggle (below) | open and close | **open and close** |
| 04 Ctrl+1 via virtual keyboard | open and close | nothing |
| 05 Ctrl+2 via virtual keyboard | open and close | nothing |

The native Deck buttons toggle the menus in both cases. So toggling is the expected behaviour.

**Toggle:** read `Router.WindowStore?.GamepadUIMainWindowInstance?.MenuStore.m_eOpenSideMenu` (`0` none, `1` Main, `2` QuickAccess). If it equals the target, call `Navigation.CloseSideMenus()`. Otherwise open the target. Pressing the Steam-menu key while QAM is open switches to the Steam menu. Don't `JSON.stringify` MenuStore fields, because some are circular and throw.

Keys mode is not a fallback: under Moonlight the keystrokes go nowhere visible.

## Q3: lighting over hidraw: PASS

Facts come from the OpenRazer source (`spike/openrazer-facts.md` on the `spike` branch, cited per function). Tested on the device:

| Command | Bytes sent (90-byte report, prefixed with report ID 0) | Status | Result |
|---|---|---|---|
| brightness 255 | `00 1f 00 00 00 03 0f 04 01 00 ff`, CRC `f6` | `0x02` | |
| static green | `00 1f 00 00 00 09 0f 02 01 05 01 00 00 01 00 ff 00`, CRC `ff` | `0x02` | keypad green |
| spectrum | `00 1f 00 00 00 06 0f 02 01 05 03 00 00 00`, CRC `0c` | `0x02` | colours cycle |

Transport: `HIDIOCSFEATURE(91)` with `b"\x00" + report`, sleep 1 ms, then `HIDIOCGFEATURE(91)`. `resp[1]` is the status byte, and the reply echoes txid, class/cmd and args. Report layout: `[0]` status, `[1]` transaction ID, `[2:4]` remaining packets, `[4]` protocol, `[5]` data_size, `[6]` class, `[7]` command, `[8:88]` args, `[88]` CRC = XOR of bytes 2..87, `[89]` 0. Status codes: 0x01 busy, 0x02 success, 0x03 failure, 0x04 timeout, 0x05 not supported.

**Transaction ID:** `0x1F` for everything except breathing, which OpenRazer sends with `0x3F`.

Extended-matrix effect commands: class `0x0F`, command `0x02`, args `01 05 <effect> …` (VARSTORE, BACKLIGHT_LED). From OpenRazer; only static and spectrum were sent in the spike.

| Effect | txid | args |
|---|---|---|
| none (off) | 1F | `01 05 00 00 00 00` |
| static | 1F | `01 05 01 00 00 01 R G B` |
| breathing single | 3F | `01 05 02 01 00 01 R G B` |
| breathing random | 3F | `01 05 02 00 00 00` |
| spectrum | 1F | `01 05 03 00 00 00` |
| wave | 1F | `01 05 04 DIR 28 00` (DIR 1 left→right, 2 right→left) |
| reactive | 1F | `01 05 05 00 SPD 01 R G B` (SPD 1-4) |
| starlight single | 1F | `01 05 07 00 SPD 01 R G B` (SPD 1-3) |
| starlight random | 1F | `01 05 07 00 SPD 00` |
| brightness | 1F | class `0x0F` command **`0x04`**: `01 00 BRI` (LED 0x00, not 0x05) |

**Ships (firmware-native):** static, breathing, spectrum, wave, reactive, starlight. **Dropped:** ripple. The OpenRazer daemon renders it in software with custom frames every 40 ms.

**Never send set-device-mode (class `0x00`, command `0x04`).** OpenRazer skips it for this PID because "Tartarus Pro resets when it receives this command". The daemon also runs this device with `DRIVER_MODE=False`.

Breathing, wave, reactive and starlight are from the source only and weren't sent in the spike. Task 11's Deck check is their first run.

## Things that contradict or change the plan

1. **Controls:** no `thumb` control (the thumb key is k20). New control `top_button` (above the D-pad, `KEY_LEFTALT`). Row 4 has 4 keys (16-19). → Task 2 devmap, Task 13 picture.
2. **Steam actions:** `api` with a toggle via `MenuStore.m_eOpenSideMenu`. → Task 9.
3. **Deploy:** rsync to a stage folder, then one user-run `sudo cp`. Decky live-reloads, so no restart. → Task 8 `deploy.sh`, Task 8 Step 5.
4. **Startup and unload robustness:** `_unload` must work after a partial `_main`, and an `EBUSY` grab (another process still holds it) must be retried by the supervisor, not crash. → Task 8.
5. **Lighting:** two transaction IDs, the brightness command is `0x04` with LED 0x00, ripple dropped, never send `00/04`. → Task 10, Global Constraints.
6. **Virtual device IDs:** `BUS_USB 0x1209:0x0001` is the combination tested through Moonlight. The plan's `BUS_VIRTUAL 0:0` is untested. → Task 6 uses the tested IDs.
7. **Wheel:** the keypad sends `REL_WHEEL_HI_RES` next to `REL_WHEEL`. The engine acts on `REL_WHEEL` only and ignores HI_RES. → Task 4, Task 6.
8. **Python version:** the Deck's system Python is 3.14, but the plugin runs under Decky's bundled interpreter, which the spike didn't check. The 3.11 limit stays.
