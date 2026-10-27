import { DialogButton, ModalRoot, TextField } from "@decky/ui";
import { useState } from "react";

import { errorText } from "../Panel";

type Props = { title: string; initial: string; onSubmit(name: string): Promise<void>; closeModal?(): void };

export function NameModal({ title, initial, onSubmit, closeModal }: Props) {
  const [name, setName] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function save() {
    setBusy(true);
    onSubmit(name)
      .then(() => closeModal?.())
      .catch((e) => {
        setError(errorText(e));
        setBusy(false);
      });
  }

  return (
    <ModalRoot onCancel={closeModal}>
      <div style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12 }}>{title}</div>
      <TextField value={name} onChange={(e) => setName(e.target.value)} />
      {error && <div style={{ color: "#e05050", marginTop: 8 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <DialogButton disabled={busy} onClick={save}>Save</DialogButton>
        <DialogButton onClick={() => closeModal?.()}>Cancel</DialogButton>
      </div>
    </ModalRoot>
  );
}
