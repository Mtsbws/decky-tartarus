# Starter profiles: design

> **Superseded in part (2026-10-28, user decision during S2):** the starters are only preinstalled profiles on a fresh
> install, edited or deleted like any other. There are no `starter:` ids, no "Starter profiles" section in the New
> profile modal, and "Copy from" lists the user's own profiles only. Text below that says otherwise is out of date.

Status: approved by the user on 2026-10-28. Decisions by the user are marked as theirs;
everything marked **(my call)** was chosen by the assistant and is open to change.

## Why

New Tartarus users find it hard to design a layout from scratch. The plugin ships three starter
profiles — a generic FPS with movement on the WASD keys, a generic FPS with movement on the thumb
D-pad, and a generic MMO — so a new user can see how profiles, modifiers, Hypershift and dual-stage
keys fit together, copy one, and adjust it.

Success: a fresh install shows Default plus three working, editable profiles; "New profile" can copy
any starter; the repo has a reference table for each starter that a user can read without the Deck.

## Goals

1. **Three built-in starters**, named `FPS – WASD`, `FPS – D-pad` and `MMO` (user's decision on
   the set and the fact that MMO has no WASD version; names are my call: the name says how you move,
   the MMO needs no suffix because it has one version). Names must fit `NAME_MAX` (24).
2. **"Copy from" list.** The New profile flow lists the user's own profiles first, then a
   `Starter profiles` group with the three starters. Picking one creates a new profile holding a
   copy of that starter under the name the user types. (User's decision.)
3. **Fresh install gets real profiles.** When there is no settings file, the install starts with
   Default, FPS – WASD, FPS – D-pad and MMO, as ordinary profiles that can be edited, renamed or
   deleted. (User's decision.)
4. **Never re-applied.** Starters are added only at that first creation. A deleted starter stays
   deleted; an update, reinstall or restart never adds, resets or changes any profile in an existing
   settings file. (User's decision.) The "copy from" starters are read from the plugin code, so they
   are available to existing installs too without touching their settings.
5. **A reference image of the Default profile** (user's request): a labelled picture of the Tartarus
   showing how to get around SteamOS Game Mode with it — the D-pad, the button above it (Enter), the
   steam menu / Quick Access / on-screen keyboard keys, the controller-button keys (F3/F4/F6/F7/F8/F9
   as X, Y, L1, R1, View, Menu), the wheel (volume, play/pause) and the thumb key. It is built from
   the `STEAMOS_DEFAULT` table in `config.py` so the two can't drift, committed under
   `docs/screenshots/` (or a sibling folder), and shown in the README's "Default layout" section in
   place of or beside the text block. Format is the builder's call (an SVG drawn from the data is
   preferred, since it stays sharp and can be regenerated). The three starters get the same kind of
   labelled picture (user's decision), generated from their definitions in the same way, shown in
   `docs/starter-profiles.md` next to each table; the MMO picture also shows its Hypershift layer.
6. **Reference tables in the repo**, one per starter, in `docs/starter-profiles.md`, linked from the
   README. Same style as the README's Default layout block. (User's decision.)

7. **A screenshot task at the end of the plan.** The last task of the plan does not take screenshots
   itself; it gives the user a short, numbered shot list of what to capture on the Deck (one line each:
   page, what must be visible, file name under `docs/screenshots/`), and says where in the README each
   one goes. Suggested list, for the plan to refine: (a) the Profiles page on a fresh install showing
   Default plus the three starters; (b) New profile with the "copy from" list open on the
   `Starter profiles` group; (c) Customize on `FPS – WASD`; (d) Customize on `FPS – D-pad`; (e) Customize
   on `MMO`, standard layer; (f) the same with the Hypershift layer showing; (g) the Actuation page on
   `MMO` showing k18's secondary function; (h) the Default profile's Customize page. After the user
   captures them, a short follow-up step wires the files into the README and `docs/starter-profiles.md`
   and removes any placeholder.

## Non-goals

- Game-specific profiles. The user's ARC Raiders profile stays on their Deck only and is not
  shipped; it is only the reference for the FPS layouts.
- An MMO version with movement on WASD.
- Automatically assigning the starters to any game.
- Hypershift in the FPS starters (user's decision: no Hypershift there).
- Shipping starters as an import/export file format.

## Anti-goals

- A plugin update that alters a user's profile, or brings back a profile they deleted.
- An MMO ability that depends on a dual-stage key (WoW and similar games may treat one press that
  sends two bindings as against the one-press-one-action rule; forum reports only, not official
  policy). Only one dual-stage key is used, on a non-essential function, purely as a demonstration.
- Sprint that depends on how hard a key is pressed (user rejected it: you cannot sprint sideways or
  backwards).

## Reference games

The user named the games the layouts should suit (their decision). The starters stay generic: a key
is chosen because it is the common default across these games, not for one game's quirks.

- **FPS starters:** Call of Duty, Battlefield and Wardogs (the user's spelling; the game was not
  its PC defaults were found: WARDOGS, a PC early-access shooter on Steam).
  Checked against each game's PC defaults on 2026-10-28 (web sources, not the in-game menus): R reload,
  V melee, F interact, Tab inventory or scoreboard, M map, Shift sprint, Space jump and Q/E lean agree
  or nearly agree across them. C is crouch in Wardogs and Battlefield (hold); Call of Duty
  uses Left Ctrl. Z is **not** shared (prone and slide in Battlefield, cycle sights in Wardogs, a
  separate ping/prone setup in Call of Duty), so k17 is documented as a spare key and the reference
  doc tells users to bind it in-game to whatever they want. Q is ping in Battlefield, and G is
  grenade in Call of Duty and Battlefield but bipod in Wardogs; the doc notes these.
- **MMO starter:** World of Warcraft (the baseline) and RuneScape 3 (not Old School; the user's
  correction). WoW fixes the hotbar on 1-0 - = with Shift/Ctrl/Alt bars. RuneScape 3's ability bars
  use the same number keys and modifiers, so one layout serves both. RS3 also opens its interface
  panels with keys the user can set in-game; none are placed on the profile (my call), since twenty
  keys already hold the hotbar and modifiers.

**The repo must say this.** `docs/starter-profiles.md` opens with a "Made for" line per starter
naming these games, and the README link to that file repeats it in one sentence. The reference doc
also tells users that the profiles are starting points, not tested per game (the MMO has not been
tested in a game at all).

## Layouts

Key rows on the Tartarus: row 1 = keys 01-05, row 2 = 06-10, row 3 = 11-15, row 4 = 16-19, thumb
key = 20, plus the button above the D-pad (`top_button`), the wheel and the D-pad. Binding text is
the plugin's own syntax. Anything not listed keeps its factory key and should be set explicitly by
the builder, not left to the factory default, so the table is complete. The FPS tables are derived
from the user's ARC Raiders profile (p2), with game-specific picks made generic. The key letters are
conventional defaults; the reference doc notes what each is "usually" used for.

Shared by all three: D-pad mode `4way`; `k01` Esc at an actuation of 2.5 mm (avoids opening the
menu by accident; the user's setting on ARC Raiders); no Hypershift in the FPS starters.

### FPS – WASD (movement on keys, D-pad = weapon slots 3-6)

| Control | Binding | Usual use |
|---|---|---|
| k01 | Esc (2.5 mm) | menu |
| k02, k03 | 1, 2 | weapon slots 1-2 |
| k04 | T | use gadget / voice (my call) |
| k05 | F | interact |
| k06 | Tab | scoreboard / inventory |
| k07, k09 | Q, E | lean (ping in Battlefield) |
| k08, k12, k13, k14 | W, A, S, D | move |
| k10 | R | reload |
| k11 | Shift (modifier) | sprint |
| k15 | Y | chat |
| k16 | M | map |
| k17 | Z | spare action: prone, cycle sights or ping, whichever the game puts on Z (my call) |
| k18 | G | grenade |
| k19 | C | toggle crouch |
| k20 | Space | jump |
| top_button | Alt (modifier) | slow walk / dodge |
| dpad up/right/down/left | 3, 4, 5, 6 | weapon slots 3-6 / quick use |
| dpad diagonals | unused in 4-way | |
| wheel up / down / click | H, V, N | holster / melee / night vision (my call) |

### FPS – D-pad (movement on D-pad, all 20 keys free)

D-pad up/right/down/left = W, D, S, A (4-way: a diagonal holds both neighbours). The keys that held
WASD take the weapon slots and interact, so every function from the WASD version is still on one key.

| Control | Binding | Usual use |
|---|---|---|
| k01 | Esc (2.5 mm) | menu |
| k02-k05 | 1, 2, 3, 4 | weapon slots 1-4 |
| k06 | Tab | scoreboard / inventory |
| k07, k09 | Q, E | lean (ping in Battlefield) |
| k08 | 5 | weapon slot 5 |
| k10 | R | reload |
| k11 | Shift (modifier) | sprint |
| k12 | 6 | weapon slot 6 |
| k13 | F | interact |
| k14 | T | use gadget / voice (my call) |
| k15 | G | grenade (bipod in Wardogs) |
| k16 | M | map |
| k17 | Z | spare action: prone, cycle sights or ping, whichever the game puts on Z (my call) |
| k18 | X | free (my call: X) |
| k19 | C | toggle crouch |
| k20 | Space | jump |
| top_button | Alt (modifier) | slow walk / dodge |
| dpad | W, D, S, A | move |
| wheel up / down / click | H, V, N | holster / melee / night vision |

Note: Y (chat) is not placed in this version; the builder may keep it off — only 20 keys exist and
chat is rare (my call).

### MMO (movement on D-pad; World of Warcraft default bindings as the baseline)

Based on the common community pattern: number-key hotbar, Shift/Ctrl/Alt modifiers for more bars.
Not tested in a game (the user has none to test with); built from WoW's default key binds.

| Control | Binding | Usual use |
|---|---|---|
| k01 | Esc (2.5 mm) | game menu |
| k02-k05 | 1, 2, 3, 4 | action bar 1 |
| k06 | Tab | target next enemy |
| k07-k10 | 5, 6, 7, 8 | action bar 1 |
| k11 | Shift (modifier) | bar 3 modifier (Shift+1…) |
| k12-k15 | 9, 0, -, = | action bar 1 |
| k16 | Ctrl (modifier) | modifier |
| k17 | C | character panel |
| k18 | M, with secondary B at a deeper press | map; deep press opens bags (the one dual-stage demo) |
| k19 | Hypershift | hold for action bar 2 |
| k20 | Alt (modifier) | modifier |
| top_button | Space | jump |
| dpad | W, D, S, A | move |
| wheel up / down | Page Up / Page Down | camera zoom (WoW has no default; user binds in-game) |
| wheel click | Num Lock | auto-run |

Hypershift layer (held k19), for k02-k05, k07-k10, k12-k15: Ctrl+1 … Ctrl+= (the same twelve
buttons, Ctrl held). The user binds bar 2 to Ctrl+number in the game's keybindings. Every other
control falls through to its standard binding. Keys send one binding per press; no ability sits on a
dual-stage key. Secondary actuation for k18: B at a deeper point than the default; builder picks a
valid depth (see `actuation.py`, `gap_ok`).

## Where it lives in the code (builder to confirm against the code)

- A new module of starter definitions: for each starter an id, a display name, a D-pad mode, and
  the bindings (binding text → `parse_binding_text`), plus actuation, secondary and Hypershift for
  the MMO. Built from the same text syntax used by `STEAMOS_DEFAULT`, and checked by tests that every
  starter parses, has all controls, and respects the profile limits (names ≤ 24, ≤ 8 profiles).
- `default_config()` (used when no settings file exists) adds the three starters after Default with
  unique ids (`new_profile_id`) and distinct LED patterns from `LED_ORDER` (`next_leds`).
- `create_profile` (`service.py`, `main.py`, `api.ts`) accepts a starter id as its `copy_from_id` as
  well as a profile id; copying a starter never changes the starter.
- The New profile flow (`ProfilesPage.tsx`) shows the "copy from" list with a `Starter profiles`
  group (the user's own profiles first). Fits 1280×800, usable with the D-pad and A/B.
- Profile limit: a fresh install has 4 of the 8 allowed profiles.

## Open points settled by my call (check these)

- **Ids.** "Copy from" ids live in their own namespace (`starter:fps-wasd`, `starter:fps-dpad`,
  `starter:mmo`), so they can't collide with profile ids. The profiles a fresh install creates get
  ordinary generated ids.
- **Which function builds the fresh config.** The builder may either change `default_config()` or add
  a separate first-run function and update the existing tests that expect one profile. Either way the
  missing-file and corrupt-file cases both start with the starters; a v1-migrated file does not.
- **Key names.** The code uses its own spellings (`Minus`, `Equal`, `PageUp`, `PageDown`, `NumLock`); the
  reference doc uses the usual labels (-, =, Page Up, Page Down, Num Lock).
- **`FPS – D-pad` has no chat key** (only 20 keys), and `k18` is X; the note is authoritative over the
  intro sentence that every WASD-version function stays on one key.
- **MMO `k18`'s secondary** (B) falls through on the Hypershift layer like its primary; the builder
  confirms against `engine.py` and adds a test.
- Names and the en dash in them (a plain hyphen if the editor font lacks the dash).
- The letters marked "my call" above, and no chat key in `FPS – D-pad`.
- The missing-file case only: a corrupt settings file is moved aside as today and the recovered
  install is also fresh, so it also gets the starters.
- The MMO's Hypershift on k19 (matches the FPS crouch key position), jump on the top button, and
  Ctrl+number as the Hypershift layer.
- Wheel: Page Up/Down for zoom and Num Lock for auto-run in the MMO.

## Constraints

- Settings file schema stays compatible: existing files load unchanged.
- The editor keeps the CSS Loader look and the existing row/card components.
- The plugin still runs without the starters touching an existing install.
