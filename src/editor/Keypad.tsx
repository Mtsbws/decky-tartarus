import { Focusable } from "@decky/ui";

import { State } from "../api";

// Our own drawing (no Razer images), laid out like KEYZER's picture of the
// Tartarus Pro: four staggered key rows, the scroll wheel to their right, and
// the thumb area with the top button, D-pad and thumb key (k20).
const W = 540;
const H = 340;

const KEY = 56;
const PITCH = 62;

function row(first: number, count: number, x0: number, y: number) {
  const out: Record<string, Box> = {};
  for (let i = 0; i < count; i++) {
    out[`k${String(first + i).padStart(2, "0")}`] = { x: x0 + i * PITCH, y, w: KEY, h: KEY };
  }
  return out;
}

type Box = { x: number; y: number; w: number; h: number };

const LAYOUT: Record<string, { x: number; y: number; w: number; h: number }> = {
  ...row(1, 5, 20, 20),
  ...row(6, 5, 30, 82),
  ...row(11, 5, 40, 144),
  ...row(16, 4, 50, 206),
  wheel_up: { x: 345, y: 50, w: 44, h: 40 },
  wheel_click: { x: 345, y: 92, w: 44, h: 40 },
  wheel_down: { x: 345, y: 134, w: 44, h: 40 },
  top_button: { x: 420, y: 146, w: 60, h: 30 },
  dpad_up: { x: 428, y: 186, w: 44, h: 44 },
  dpad_right: { x: 472, y: 230, w: 44, h: 44 },
  dpad_down: { x: 428, y: 274, w: 44, h: 44 },
  dpad_left: { x: 384, y: 230, w: 44, h: 44 },
  dpad_up_right: { x: 476, y: 192, w: 34, h: 34 },
  dpad_down_right: { x: 476, y: 280, w: 34, h: 34 },
  dpad_down_left: { x: 390, y: 280, w: 34, h: 34 },
  dpad_up_left: { x: 390, y: 192, w: 34, h: 34 },
  k20: { x: 296, y: 270, w: 80, h: 50 },
};

const DIAGONALS = new Set(["dpad_up_right", "dpad_down_right", "dpad_down_left", "dpad_up_left"]);

const SHORT: Record<string, string> = {
  top_button: "top",
  wheel_up: "wheel ▲",
  wheel_click: "click",
  wheel_down: "wheel ▼",
  dpad_up: "↑",
  dpad_right: "→",
  dpad_down: "↓",
  dpad_left: "←",
  dpad_up_right: "↗",
  dpad_down_right: "↘",
  dpad_down_left: "↙",
  dpad_up_left: "↖",
};

// The small number or name shown in the corner of each key.
export function controlName(control: string): string {
  return SHORT[control] ?? control.replace(/^k/, "");
}

const pct = (v: number, of: number) => `${(v / of) * 100}%`;

export function Keypad(props: { state: State; selected: string | null; onSelect(control: string): void }) {
  const { state, selected, onSelect } = props;
  const controls = Object.keys(LAYOUT).filter(
    (c) => c in state.bindings && (state.dpad_mode === "8way" || !DIAGONALS.has(c)),
  );

  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: `${W} / ${H}` }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <rect x={8} y={8} width={392} height={262} rx={22} fill="#1d2329" stroke="#3d4450" strokeWidth={2} />
        <rect x={340} y={44} width={54} height={136} rx={14} fill="#14181d" stroke="#3d4450" />
        <circle cx={450} cy={252} r={84} fill="#1d2329" stroke="#3d4450" strokeWidth={2} />
        <circle cx={450} cy={252} r={50} fill="#14181d" />
      </svg>
      <Focusable style={{ position: "absolute", inset: 0 }} flow-children="grid">
        {controls.map((c) => {
          const box = LAYOUT[c];
          const isSelected = c === selected;
          return (
            <Focusable
              key={c}
              onActivate={() => onSelect(c)}
              onClick={() => onSelect(c)}
              style={{
                position: "absolute",
                left: pct(box.x, W),
                top: pct(box.y, H),
                width: pct(box.w, W),
                height: pct(box.h, H),
                boxSizing: "border-box",
                borderRadius: 8,
                border: `2px solid ${isSelected ? "#1a9fff" : "#4b5361"}`,
                background: isSelected ? "#1a3d5c" : "#2a313b",
                color: "#dfe3e6",
                padding: "2px 4px",
                overflow: "hidden",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div style={{ fontSize: 9, opacity: 0.6, lineHeight: 1 }}>{controlName(c)}</div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  textAlign: "center",
                }}
              >
                {state.bindings[c].label}
              </div>
            </Focusable>
          );
        })}
      </Focusable>
    </div>
  );
}
