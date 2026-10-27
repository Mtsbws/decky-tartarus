import { ConfirmModal, DialogButton, Focusable, Menu, MenuItem, showContextMenu, showModal } from "@decky/ui";
import { useState } from "react";

import { activeProfile, createProfile, deleteProfile, errorText, profileById, ProfileState, renameProfile, State } from "../api";
import { StatusLights } from "../StatusLights";
import { Card } from "./Card";
import { BUTTON, ERROR, PAGE_HEIGHT } from "./layout";
import { LightsModal } from "./LightsModal";
import { NameModal } from "./NameModal";

// A grey 40×28 button, as CSS Loader's row buttons.
const MORE = { width: 40, minWidth: 0, height: 28, padding: 0, flexShrink: 0, lineHeight: "28px" };

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

  function menu(p: ProfileState, target: EventTarget | null) {
    showContextMenu(
      <Menu label={p.name}>
        <MenuItem onSelected={() => onEdit(p.id)}>Edit keys</MenuItem>
        {!p.is_default && (
          <MenuItem onSelected={() => showModal(<LightsModal state={state} profile={p} onChanged={onChanged} />)}>Lights</MenuItem>
        )}
        <MenuItem onSelected={() => rename(p)}>Rename</MenuItem>
        {!p.is_default && (
          <MenuItem tone="destructive" onSelected={() => remove(p)}>
            Delete
          </MenuItem>
        )}
      </Menu>,
      target ?? undefined,
    );
  }

  return (
    <div style={{ height: PAGE_HEIGHT }}>
      <Card title="Profiles" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Two columns so the maximum of 8 fits; the list may still scroll inside the card (the only scrolling allowed).
            No flow-children: the D-pad moves through the grid by position. */}
        <Focusable
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 4,
            alignContent: "start",
          }}
        >
          {state.profiles.map((p) => (
            <Focusable
              key={p.id}
              flow-children="row"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                minHeight: 52,
                padding: "4px 12px",
                borderRadius: 4,
                background: "rgba(255, 255, 255, 0.06)",
                boxSizing: "border-box",
              }}
            >
              <StatusLights leds={p.leds} size={9} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</span>
                  {p.id === state.active_profile && (
                    <span style={{ fontSize: 11, padding: "1px 6px", borderRadius: 8, background: "#5bd14a", color: "#0e141b", flexShrink: 0 }}>
                      in use
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, opacity: 0.7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.is_default ? "Every game without its own profile" : p.games.join(", ") || "No games"}
                </div>
              </div>
              <DialogButton style={MORE} onClick={(e) => menu(p, e.currentTarget)}>
                ⋯
              </DialogButton>
            </Focusable>
          ))}
        </Focusable>
        {error && <div style={{ color: ERROR, marginTop: 4 }}>{error}</div>}
        <Focusable flow-children="row" style={{ display: "flex", marginTop: 8 }}>
          <DialogButton style={BUTTON} disabled={state.profiles.length >= state.max_profiles} onClick={create}>
            New profile
          </DialogButton>
        </Focusable>
      </Card>
    </div>
  );
}
