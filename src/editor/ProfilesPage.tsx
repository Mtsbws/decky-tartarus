import { ConfirmModal, DialogButton, Focusable, showModal } from "@decky/ui";
import { useState } from "react";

import { activeProfile, createProfile, deleteProfile, errorText, profileById, ProfileState, renameProfile, State } from "../api";
import { StatusLights } from "../StatusLights";
import { Card } from "./Card";
import { useKeypadGlow } from "./glow";
import { Keypad } from "./Keypad";
import { BUTTON, ERROR, PAGE_HEIGHT } from "./layout";
import { LightsModal } from "./LightsModal";
import { NameModal } from "./NameModal";
import { IN_USE, ROW, ROW_CLASS, ROW_CSS } from "./profileRows";

export function ProfilesPage({ state, viewing, onEdit, onView, onChanged }: {
  state: State;
  viewing: string;
  onEdit(id: string): void;
  onView(id: string): void;
  onChanged(s: State): void;
}) {
  const [error, setError] = useState<string | null>(null);

  function create() {
    // A new profile copies the one being edited, as before.
    const source = profileById(state, viewing) ?? activeProfile(state);
    showModal(
      <NameModal
        title="New profile"
        initial=""
        onSubmit={async (name) => {
          const s = await createProfile(name, source.id);
          const made = s.profiles.find((p) => p.name.toLowerCase() === name.trim().toLowerCase());
          setError(null);
          onChanged(s);
          if (made) onView(made.id);
        }}
      />,
    );
  }

  function rename(p: ProfileState) {
    showModal(
      <NameModal
        title="Rename profile"
        initial={p.name}
        onSubmit={async (name) => {
          const s = await renameProfile(p.id, name);
          setError(null);
          onChanged(s);
        }}
      />,
    );
  }

  function remove(p: ProfileState) {
    const n = p.games.length;
    const desc = n === 0 ? "No games use it." : `${n} ${n === 1 ? "game" : "games"} will go back to Default.`;
    showModal(
      <ConfirmModal
        strTitle={`Delete ${p.name}?`}
        strDescription={desc}
        onOK={() => {
          deleteProfile(p.id)
            .then((s) => {
              setError(null);
              onChanged(s);
              if (p.id === viewing) onView(activeProfile(s).id);
            })
            .catch((e) => setError(errorText(e)));
        }}
      />,
    );
  }

  const selected = profileById(state, viewing) ?? activeProfile(state);
  const glow = useKeypadGlow(state, selected, "standard");
  const games = selected.is_default ? "Every game without its own profile" : selected.games.join(", ") || "No games yet";

  return (
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      <Keypad profile={selected} view="preview" layer="standard" {...glow} leds={selected.leds} />
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        {/* The list may scroll inside its card (the only scrolling allowed), so the details stay on screen. */}
        <Card title="Profiles" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <style>{ROW_CSS}</style>
          <Focusable flow-children="column" style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            {state.profiles.map((p) => (
              <DialogButton
                key={p.id}
                className={p.id === selected.id ? `${ROW_CLASS} Tartarus_Selected` : ROW_CLASS}
                onClick={() => onView(p.id)}
                style={ROW}
              >
                <StatusLights leds={p.leds} size={7} />
                <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</span>
                {p.id === state.active_profile && <span style={IN_USE}>in use</span>}
              </DialogButton>
            ))}
          </Focusable>
          <Focusable flow-children="row" style={{ display: "flex", marginTop: 8, flexShrink: 0 }}>
            <DialogButton style={BUTTON} disabled={state.profiles.length >= state.max_profiles} onClick={create}>
              New profile
            </DialogButton>
          </Focusable>
        </Card>
        <Card title={selected.name} style={{ flexShrink: 0 }}>
          <div style={{ fontSize: 13, opacity: 0.7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{games}</div>
          <Focusable flow-children="row" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
            <DialogButton style={BUTTON} onClick={() => onEdit(selected.id)}>
              Edit keys
            </DialogButton>
            {!selected.is_default && (
              <DialogButton style={BUTTON} onClick={() => showModal(<LightsModal state={state} profile={selected} onChanged={onChanged} />)}>
                Lights
              </DialogButton>
            )}
            <DialogButton style={BUTTON} onClick={() => rename(selected)}>
              Rename
            </DialogButton>
            {!selected.is_default && (
              <DialogButton style={BUTTON} onClick={() => remove(selected)}>
                Delete
              </DialogButton>
            )}
          </Focusable>
          {error && <div style={{ color: ERROR, marginTop: 4 }}>{error}</div>}
        </Card>
      </Focusable>
    </Focusable>
  );
}
