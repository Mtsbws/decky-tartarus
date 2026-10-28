import { DialogButton, Focusable, ModalRoot, TextField } from "@decky/ui";
import { useState } from "react";

import { createProfile, errorText, State } from "../api";
import { StatusLights } from "../StatusLights";
import { ROW, ROW_CLASS, ROW_CSS } from "./profileRows";

type Props = {
  state: State;
  initialSourceId: string;
  onCreated(s: State, name: string): void;
  closeModal?(): void;
};

const NAME = { flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const };

// A name plus the profile to copy. Selecting a row only picks the source; Save creates.
export function NewProfileModal({ state, initialSourceId, onCreated, closeModal }: Props) {
  const [name, setName] = useState("");
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function save() {
    setBusy(true);
    createProfile(name, sourceId)
      .then((s) => {
        onCreated(s, name);
        closeModal?.();
      })
      .catch((e) => {
        setError(errorText(e));
        setBusy(false);
      });
  }

  function row(id: string, label: string, leds: boolean[]) {
    return (
      <DialogButton
        key={id}
        className={id === sourceId ? `${ROW_CLASS} Tartarus_Selected` : ROW_CLASS}
        onClick={() => setSourceId(id)}
        style={ROW}
      >
        <StatusLights leds={leds} size={7} />
        <span style={NAME}>{label}</span>
      </DialogButton>
    );
  }

  return (
    <ModalRoot onCancel={closeModal}>
      <style>{ROW_CSS}</style>
      <div style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12 }}>New profile</div>
      <TextField value={name} onChange={(e) => setName(e.target.value)} />
      <div style={{ fontSize: 12, opacity: 0.6, textTransform: "uppercase", margin: "12px 0 2px" }}>Copy from</div>
      <Focusable flow-children="column" style={{ maxHeight: 260, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
        {state.profiles.map((p) => row(p.id, p.name, p.leds))}
      </Focusable>
      {error && <div style={{ color: "#e05050", marginTop: 8 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <DialogButton disabled={busy} onClick={save}>Save</DialogButton>
        <DialogButton onClick={() => closeModal?.()}>Cancel</DialogButton>
      </div>
    </ModalRoot>
  );
}
