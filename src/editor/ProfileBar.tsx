import { ConfirmModal, DialogButton, Dropdown, showModal } from "@decky/ui";
import { useState } from "react";

import { activeProfile, createProfile, deleteProfile, profileById, renameProfile, setLeds, State } from "../api";
import { errorText } from "../Panel";
import { NameModal } from "./NameModal";

// LED patterns as dropdown keys and labels, top light first.
const ledKey = (leds: boolean[]) => leds.map((on) => (on ? "1" : "0")).join("");
const ledLabel = (leds: boolean[]) => leds.map((on) => (on ? "●" : "○")).join("");

function LedDots({ leds }: { leds: boolean[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {leds.map((on, i) => (
        <div key={i} style={{ width: 6, height: 6, borderRadius: 3, background: on ? "#dfe3e6" : "#434b57" }} />
      ))}
    </div>
  );
}

type Props = { state: State; viewing: string; onView(id: string): void; onChanged(s: State): void };

export function ProfileBar({ state, viewing, onView, onChanged }: Props) {
  const [error, setError] = useState<string | null>(null);
  const profile = profileById(state, viewing) ?? activeProfile(state);
  const active = activeProfile(state);
  const games = profile.games.join(", ");
  const usedBy = profile.is_default
    ? "Used by every game without its own profile" + (games ? `: ${games}` : "")
    : `Used by: ${games || "no games"}`;

  // The viewed profile's own pattern plus the ones no other profile uses.
  const ledOptions = state.led_patterns.filter(
    (leds) => ledKey(leds) === ledKey(profile.leds) || !state.profiles.some((p) => p.id !== profile.id && ledKey(p.leds) === ledKey(leds)),
  );

  function pickLeds(key: string) {
    const leds = ledOptions.find((l) => ledKey(l) === key);
    if (!leds) return;
    setLeds(viewing, leds)
      .then((s) => {
        setError(null);
        onChanged(s);
      })
      .catch((e) => setError(errorText(e)));
  }

  function create() {
    showModal(
      <NameModal
        title="New profile"
        initial=""
        onSubmit={async (name) => {
          const s = await createProfile(name, viewing);
          const made = s.profiles.find((p) => p.name.toLowerCase() === name.trim().toLowerCase());
          setError(null);
          onChanged(s);
          if (made) onView(made.id);
        }}
      />,
    );
  }

  function rename() {
    showModal(
      <NameModal
        title="Rename profile"
        initial={profile.name}
        onSubmit={async (name) => {
          const s = await renameProfile(viewing, name);
          setError(null);
          onChanged(s);
        }}
      />,
    );
  }

  function remove() {
    const n = profile.games.length;
    const desc = n === 0 ? "No games use it." : `${n} ${n === 1 ? "game" : "games"} will go back to Default.`;
    showModal(
      <ConfirmModal
        strTitle={`Delete ${profile.name}?`}
        strDescription={desc}
        onOK={() => {
          deleteProfile(viewing)
            .then((s) => {
              setError(null);
              onChanged(s);
              onView(activeProfile(s).id);
            })
            .catch((e) => setError(errorText(e)));
        }}
      />,
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "0 0 8px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <div style={{ minWidth: 220 }}>
          <Dropdown
            rgOptions={state.profiles.map((p) => ({ data: p.id, label: p.name }))}
            selectedOption={profile.id}
            onChange={(o) => onView(o.data)}
          />
        </div>
        <LedDots leds={profile.leds} />
        {!profile.is_default && (
          <div style={{ minWidth: 110 }}>
            <Dropdown
              rgOptions={ledOptions.map((l) => ({ data: ledKey(l), label: `LEDs ${ledLabel(l)}` }))}
              selectedOption={ledKey(profile.leds)}
              onChange={(o) => pickLeds(o.data)}
            />
          </div>
        )}
        <DialogButton style={{ width: "auto", minWidth: 0 }} disabled={state.profiles.length >= state.max_profiles} onClick={create}>New</DialogButton>
        <DialogButton style={{ width: "auto", minWidth: 0 }} onClick={rename}>Rename</DialogButton>
        <DialogButton style={{ width: "auto", minWidth: 0 }} disabled={profile.is_default} onClick={remove}>Delete</DialogButton>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {error && <div style={{ color: "#e05050" }}>{error}</div>}
        <div>
          {profile.id === active.id
            ? `Editing ${profile.name}. The keypad is using it now.`
            : `Editing ${profile.name}. The keypad is using ${active.name} right now.`}
        </div>
        <div style={{ opacity: 0.7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{usedBy}</div>
      </div>
    </div>
  );
}
