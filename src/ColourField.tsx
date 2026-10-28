import { DialogButton, DropdownItem, ModalRoot, showModal, TextField } from "@decky/ui";
import { useState } from "react";

const COLOURS = [
  { name: "Red", hex: "#ff0000" },
  { name: "Orange", hex: "#ff6000" },
  { name: "Yellow", hex: "#ffff00" },
  { name: "Green", hex: "#00ff00" },
  { name: "Cyan", hex: "#00ffff" },
  { name: "Blue", hex: "#0000ff" },
  { name: "Purple", hex: "#8000ff" },
  { name: "Pink", hex: "#ff00ff" },
  { name: "White", hex: "#ffffff" },
];
const CUSTOM = "custom";

const Dot = ({ hex }: { hex: string }) => (
  <span
    style={{
      display: "inline-block",
      width: 12,
      height: 12,
      borderRadius: "50%",
      background: hex,
      marginRight: 8,
      verticalAlign: "middle",
    }}
  />
);

const withDot = (hex: string, name: string) => (
  <span>
    <Dot hex={hex} />
    {name}
  </span>
);

// "ff6000", "#FF6000" -> "#ff6000"; null when not six hex digits.
function parseHex(text: string): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(text.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
}

function ColourModal({ initial, onApply, closeModal }: { initial: string; onApply(hex: string): void; closeModal?(): void }) {
  const [text, setText] = useState(initial);
  const [invalid, setInvalid] = useState(false);
  const preview = parseHex(text);

  function apply() {
    if (!preview) {
      setInvalid(true);
      return;
    }
    onApply(preview);
    closeModal?.();
  }

  return (
    <ModalRoot onCancel={closeModal}>
      <div style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12 }}>Custom colour</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <TextField
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setInvalid(false);
            }}
          />
        </div>
        <span
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: preview ?? "transparent",
            border: "1px solid #dfe3e6",
          }}
        />
      </div>
      <div style={{ opacity: 0.6, marginTop: 8 }}>Six hex digits, like #ff6000.</div>
      {invalid && <div style={{ color: "#e05050", marginTop: 8 }}>Use six hex digits, like #ff6000.</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <DialogButton onClick={apply}>Apply</DialogButton>
        <DialogButton onClick={() => closeModal?.()}>Cancel</DialogButton>
      </div>
    </ModalRoot>
  );
}

// The colour picker shared by the lighting rows: named colours, then any #rrggbb through a modal.
export function ColourField({ color, onChange }: { color: string; onChange: (hex: string) => void }) {
  const current = color.toLowerCase();
  const named = COLOURS.some((c) => c.hex === current);
  const options = [
    ...(named ? [] : [{ data: current, label: withDot(current, current) }]),
    ...COLOURS.map((c) => ({ data: c.hex, label: withDot(c.hex, c.name) })),
    { data: CUSTOM, label: "Custom colour…" },
  ];

  return (
    <DropdownItem
      label="Colour"
      rgOptions={options}
      selectedOption={current}
      onChange={(o) => {
        if (o.data === CUSTOM) showModal(<ColourModal initial={current} onApply={onChange} />);
        else onChange(o.data);
      }}
    />
  );
}
