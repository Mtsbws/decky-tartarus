import { Dropdown } from "@decky/ui";

import { activeProfile, profileById, State } from "../api";

type Props = { state: State; viewing: string; onView(id: string): void; onChanged(s: State): void };

// Task 9 adds the New / Rename / Delete buttons next to the dropdown.
export function ProfileBar({ state, viewing, onView }: Props) {
  const profile = profileById(state, viewing) ?? activeProfile(state);
  const active = activeProfile(state);
  const games = profile.games.join(", ");
  const usedBy = profile.is_default
    ? "Used by every game without its own profile" + (games ? `: ${games}` : "")
    : `Used by: ${games || "no games"}`;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "0 0 8px" }}>
      <div style={{ minWidth: 220 }}>
        <Dropdown
          rgOptions={state.profiles.map((p) => ({ data: p.id, label: p.name }))}
          selectedOption={profile.id}
          onChange={(o) => onView(o.data)}
        />
      </div>
      <div style={{ minWidth: 0 }}>
        <div>
          {profile.id === active.id
            ? `Editing ${profile.name}. The keypad is using it now.`
            : `Editing ${profile.name}. The keypad is using ${active.name} right now.`}
        </div>
        <div style={{ opacity: 0.7 }}>{usedBy}</div>
      </div>
    </div>
  );
}
