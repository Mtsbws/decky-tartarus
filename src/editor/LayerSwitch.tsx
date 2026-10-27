import { DialogButton, Focusable } from "@decky/ui";

import { HYPERSHIFT_ACCENT, Layer } from "./layers";
import { PICK } from "./layout";

const GREEN = "#3d8b2f";

// Which layer the editor shows: the keypad's normal bindings, or those that apply while the Hypershift key is held.
export function LayerSwitch({ layer, onChange }: { layer: Layer; onChange(l: Layer): void }) {
  const button = (value: Layer, text: string, colour: string) => (
    <DialogButton
      onClick={() => onChange(value)}
      style={{ ...PICK, ...(layer === value ? { background: colour, color: "#fff" } : {}) }}
    >
      {text}
    </DialogButton>
  );
  return (
    <Focusable flow-children="row" style={{ display: "flex", gap: 8 }}>
      {button("standard", "Standard", GREEN)}
      {button("hypershift", "Hypershift", HYPERSHIFT_ACCENT)}
    </Focusable>
  );
}
