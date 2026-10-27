import { Dropdown, Focusable } from "@decky/ui";

import { ProfileState, State, profileById } from "../api";

// The profile being edited, shown at the top of Customize and Actuation.
export function EditingRow({ state, profile, onView }: { state: State; profile: ProfileState; onView(id: string): void }) {
  let note: string | null = null;
  if (!state.connected) note = "Not connected: changes apply when it's plugged in.";
  else if (profile.id !== state.active_profile) note = `Keypad uses ${profileById(state, state.active_profile)?.name ?? "another profile"} now`;
  return (
    <Focusable flow-children="row" style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
      <div>Editing</div>
      <div style={{ minWidth: 200 }}>
        <Dropdown
          rgOptions={state.profiles.map((p) => ({ data: p.id, label: p.name }))}
          selectedOption={profile.id}
          onChange={(o) => onView(o.data)}
        />
      </div>
      {note && <div style={{ opacity: 0.7, fontSize: 13 }}>{note}</div>}
    </Focusable>
  );
}
