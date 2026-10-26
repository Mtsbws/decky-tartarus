# Decky Tartarus: named profiles with automatic per-game switching

Date: 2026-10-25
Status: approved 2026-10-26
Builds on: [v1 design](2026-10-25-tartarus-decky-plugin-design.md), which listed profiles as "planned for later" and put the picker in the Quick Access panel.

## Intent

The user just got the keypad and wants layouts ready before they need them. The first games they have in mind:

- **RuneScape**, run directly on the Deck (not through Moonlight). Movement is done with the mouse, so the D-pad is free and becomes extra ability keys.
- **Ghost Recon Wildlands**, streamed from the PC with Moonlight (Vibepollo host). The D-pad stays movement.

They want a few **named profiles** (e.g. Default, FPS, MMO). Each game is assigned to one of them, and the keypad switches automatically when the game starts. Several games can share a profile.

Each streamed PC game has its own Moonlight shortcut in Steam (a non-Steam shortcut), so each is its own entry with its own app ID. Switching keys off the app that is running, whether it's a Steam game or a non-Steam shortcut. It does not treat "Moonlight" as a whole as one app.

## What the user decided

- **A profile is a named layout** holding all bindings plus the D-pad mode: keys 01–20, the thumb key, scroll up/down, wheel click and every D-pad binding. **Lighting stays global** for now. Per-game lighting may come later.
- **Profiles can be created, named and renamed** (Default, FPS, MMO, …). **At most 8 profiles**, Default included.
- **Games are assigned to a profile.** Assigning happens while testing in-game. Any game without an assignment, and the Deck with no game running, uses **Default**.
- **The current layout becomes "Default".**
- **The Quick Access panel always says which layout is active.**
- **Profile LEDs (later):** the three indicator LEDs above the D-pad will show which profile is active. Default is all LEDs off, and each other profile gets one of the 7 lit on/off combinations, which is where the cap of 8 comes from. They switch together with the layout, so it's clear when a game has a different profile. The LED command for the Pro (`1532:0244`) isn't confirmed (OpenRazer supports profile LEDs only on Tartarus, Tartarus Chroma and Tartarus V2), so **this spec builds profiles now and the LEDs come in a follow-up** once a Synapse USB capture on the PC confirms the command. See "Prepared for the LEDs".

## Goals

1. **Detect the running app** and switch the keypad to the profile assigned to it, or to Default. This works for Steam games and for non-Steam shortcuts (each Moonlight shortcut separately). It also works when the plugin starts while a game is already running.
2. **Show the active layout** in the Quick Access panel.
3. **Assign the running game to a profile** from the panel.
4. **Manage profiles** (new, copy, rename, delete) and edit any profile's keys in the editor.
5. **Existing settings migrate automatically**, and the current layout carries over unchanged as Default.

## Non-goals

- Hypershift, macro delays, import/export, stage 2 analog (out of scope per the user).
- Driving the profile LEDs (follow-up, see above).
- Per-game lighting (later).
- Manual override: picking a layout by hand that differs from the one the running game implies. *Claude's call:* the user didn't ask for it. Assigning in-game covers the use.
- A list of all known games for assigning a game that isn't running. *Claude's call:* the user assigns while testing in-game. The editor shows which games use each profile (read-only).

## Anti-goals

- **A key stays stuck down** after a switch (e.g. W held when the game changes). The engine's existing `set_profile` releases all held keys and cancels macros. Every switch must go through it.
- **Losing or changing the user's current layout** in the migration.
- **Editing a profile without knowing which one**, and above all not knowing whether it's the one the keypad is using right now.
- Measurable idle CPU/battery cost from detection (v1 anti-goal still applies).
- The keypad depending on the frontend to work. If the frontend never reports an app, the keypad keeps working on Default.
- Sending any unconfirmed command to the keypad (v1 anti-goal). This is why the LEDs wait.

## How it works

### Detecting the running app (frontend)

Based on how decky-lsfg-vk does it (`src/hooks/useGameConfiguration.ts` in xXJSONDeruloXx/decky-lsfg-vk):

- Poll `Router.MainRunningApp` (from `@decky/ui`; it may need an `as any` cast, as lsfg-vk does) every 2 seconds. Run the first poll immediately. lsfg-vk polls rather than using `RegisterForAppLifetimeNotifications` because that event gives `unAppID = 0` for non-Steam shortcuts.
- The app ID is `app.appid` as a 32-bit unsigned number (`Number(appid) >>> 0`), which is the same value for Steam games and non-Steam shortcuts. The name is `app.display_name`. No running app means "none".
- The poll lives at plugin level (in `definePlugin`, started on load and cleared in `onDismount`), not in the panel. That way it runs while the panel is closed.
- *Claude's call:* the frontend reports the running app to the backend **on every poll**, and the backend does nothing when it hasn't changed. A call every 2 s is negligible. It also covers a backend restart while a game runs, which "report only on change" would miss, leaving the keypad on Default.
- The name is whatever the entry is called in Steam. For Moonlight that's the shortcut's own name (e.g. "Ghost Recon Wildlands"), since each game has its own shortcut.
- Switch latency of up to ~2 s after launch or exit is accepted.
- "None" is reported as it comes, with no debounce, the same as lsfg-vk. `MainRunningApp` is the running game, not the focused screen, so opening the Steam menu, Quick Access or the editor while a game runs keeps that game's layout. That has to hold for in-game assigning and testing. Verify on the Deck. If suspending or the overlay does report "none", raise it with the user instead of quietly adding a debounce.

### Choosing the profile (backend)

- `set_running_app(app_id: int | None, name: str | None)` stores the running app in memory (not in the settings file). It looks up the app's assignment (missing → Default) and calls `engine.set_profile(...)` only if the active profile actually changed. It then emits `state_changed`. If the app is assigned, the stored game name is updated to the latest `name`.
- Until the frontend reports, for example right after the backend starts, the running app is "none" and Default is active.
- If the keypad is disconnected or the engine doesn't exist yet, only the running app is stored. The engine always takes the derived active profile when it's created or reconnected.
- *Claude's call:* the active profile is **derived** from the running app plus the assignments, never stored. Today's `active_profile` field goes away, so a stale "active" value can't survive a reboot or crash.
- Anything that changes which profile is active goes through `engine.set_profile`: a game starting or stopping, assigning, or deleting the active profile. Editing the active profile's bindings does too, as it does today. *Claude's call:* a profile switch also cancels a running Record capture.

### Settings file (schema version 2)

```json
{
  "version": 2,
  "profiles": [
    { "id": "default", "name": "Default", "leds": [false, false, false], "dpad_mode": "4way", "bindings": { … } },
    { "id": "p2", "name": "MMO", "leds": [true, false, false], "dpad_mode": "8way", "bindings": { … } }
  ],
  "games": {
    "1343400": { "name": "RuneScape", "profile": "p2" }
  },
  "lighting": { … }
}
```

- `profiles`: 1–8 entries. The profile with id `default` always exists, can't be deleted, and always has all LEDs off. Ids are stable, so assignments survive renames. The id format beyond `default` is the builder's choice.
- `name`: trimmed, 1–24 characters, unique ignoring case. Default can be renamed. It stays the fallback either way, and the UI marks it as such.
- `leds`: *Claude's call:* stored now, so the LED follow-up needs no second migration. A new profile gets the first free lit combination in the order shown in the table below. Each non-default profile's pattern is unique. Nothing reads it or sends it to the device yet, and it's not shown in the UI yet.
- `games`: app ID (as a string key, the 32-bit unsigned value) → `{name, profile}`. `name` is only for display. Unassigned games have no entry. Entries for games that are no longer installed are kept; they're harmless.
- **Migration from version 1** (done in `load_config`, then saved): the layout `active_profile` pointed to (or the first profile if that id is missing) becomes the `default` profile with its bindings and D-pad mode unchanged. It's named "Default". `active_profile` is dropped, `games` is empty and `version` becomes 2. v1 only ever had one profile through the UI. Any extra ones are dropped with a log warning.
- *Claude's call:* before writing the migrated file, keep a copy of the v1 file next to it (`settings.json.v1-backup`).
- Bad entries are skipped with a warning, the way v1 handles bad bindings. *Claude's call:*
  - Profiles beyond 8 are skipped.
  - Duplicate ids or names: the first is kept and the others are skipped.
  - Bad or duplicate `leds` are reassigned.
  - A missing Default is recreated from factory keys.
  - Assignments pointing at an unknown profile, or with a bad app ID, are dropped.
  - A file unusable as a whole still goes through the existing corrupt-file path.
- Downgrading the plugin after migration isn't supported. v1 would treat the v2 file as corrupt and start from factory keys. The backup makes manual recovery possible.

LED order for new profiles (● on, ○ off):

| # | LED 1 | LED 2 | LED 3 |
|---|---|---|---|
| Default | ○ | ○ | ○ |
| 2 | ● | ○ | ○ |
| 3 | ○ | ● | ○ |
| 4 | ○ | ○ | ● |
| 5 | ● | ● | ○ |
| 6 | ● | ○ | ● |
| 7 | ○ | ● | ● |
| 8 | ● | ● | ● |

### Backend callables

All return the new state, like today's callables. Validation errors (bad name, limit reached, unknown id, deleting Default) are raised and shown by the UI, the same way v1's binding setters raise `ValueError`.

- `set_running_app(app_id, name)`: see above.
- `assign_running_game(profile_id)`: assigns the running game to that profile. Choosing Default removes the entry. It does nothing if no game is running.
- `create_profile(name, copy_from_id)`: creates a profile as a copy of `copy_from_id` (bindings and D-pad mode), with the next free LED pattern. It fails at 8 profiles. *Claude's call:* "New" and "Copy" are the same operation. "New" copies the profile being viewed, so the user's basics (Esc, Steam menu) come along.
- `rename_profile(id, name)`
- `delete_profile(id)`: not allowed for Default. Games assigned to it fall back to Default (their entries are removed). If it was active, the keypad switches to Default.
- `set_binding`, `set_binding_text`, `set_dpad_mode` gain a required `profile_id` argument and edit that profile. If it's the active one, the engine updates right away through `set_profile`, which releases held keys. That's today's behaviour, since `_save` already calls `set_profile`.
- Deleting a profile removes its games' assignment entries outright, with no undo. The confirmation names the count.
- `get_state()` / `state_changed` carry the profile list (id, name, is_default, the names of games assigned to it), the active profile id, the running app (`{app_id, name}` or null), and enough for the editor to show any profile's bindings and D-pad mode. The exact shape is the builder's call.

### Quick Access panel

In the "Keypad" section, under the connection status:

- **"Layout: MMO"**, the active profile's name. Default is shown as "Layout: Default".
- When a game is running: a dropdown **"RuneScape uses: [MMO ▾]"** listing all profiles. Changing it assigns the game and switches immediately.
- "Edit keys" stays as is. It opens the editor on the active profile.

### Editor

- **Profile bar at the top:** a dropdown of all profiles, plus **New**, **Rename** and **Delete** buttons. New and Rename ask for a name with Steam's on-screen keyboard (a `TextField` in a modal). Delete asks for confirmation through Decky's `ConfirmModal` (never a browser `confirm()`) and says how many games will go back to Default. New is disabled at 8 profiles and Delete is disabled for Default.
- It opens on the **active** profile. The user can pick another to edit.
- **Always clear which one is live:** the bar shows the profile being edited, and when it isn't the active one it says so, e.g. "Editing FPS. The keypad is using MMO right now." *Claude's call:* edits to a non-active profile save normally but don't affect the keys until that profile is active.
- Under the bar: "Used by: RuneScape, Wildlands", or "Used by every game without its own profile" for Default.
- If the active profile changes while the editor is open, the selection stays where the user put it, and the "keypad is using …" note updates.

### Prepared for the LEDs (follow-up, not built now)

- Who: the user records Synapse's USB traffic on the Windows PC (Synapse plus Wireshark with USBPcap, Tartarus plugged into the PC) while switching profiles. The same session also covers the stage 2 analog settings. The `.pcapng` files are analysed on the Mac. Claude writes a recording checklist when the user is ready.
- Then: on every profile switch, on reconnect and on resume (same as lighting), the backend sends that profile's `leds`. The editor shows and lets the user change each profile's pattern among the free ones. If the command can't be confirmed, the LEDs stay off and nothing else changes.

## Constraints

- Everything from the v1 design still holds: stdlib-only Python, the root backend, atomic settings writes via `save_config`, and no changes outside the home directory.
- Python tests cover:
  - migration (v1 → v2, including the backup)
  - the bad-entry rules
  - profile selection by app ID
  - assigning, creating, renaming and deleting, including the 8 cap and Default's protections
  - the LED auto-assignment
  - that a switch releases held keys
- Frontend detection is checked on the Deck.

## Left to the builder

Profile id format, exact panel and editor wording and layout, how the poll is structured in TypeScript, state shape and typing in `src/api.ts`, logging, and test layout.
