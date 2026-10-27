import { Focusable } from "@decky/ui";
import type { CSSProperties } from "react";

import { ProfileState } from "../api";
import { LED_COLOURS } from "../StatusLights";

// Our own drawing of the Tartarus Pro (no Razer images), traced from a
// top-down photo: five key columns with the pinky column dropped half a key,
// the scroll wheel under key 15, and the thumb wing on the right with the top
// button above the thumbstick and the tilted thumb key (k20) hanging below.
// The SVG is only the picture; the controls are boxes laid over it.
const W = 600;
const H = 630;

const KEY_W = 66;
const KEY_H = 62;
const COL_X = [28, 108, 188, 268, 348];
const ROW_Y = [32, 108, 184, 260];
const PINKY_DROP = 38;
// Each column's underglow, as on the default rainbow lighting.
const COLUMN_GLOW = ["#ff4040", "#ffb02e", "#5cff3b", "#2ec5ff", "#c13bff"];

type Box = { x: number; y: number; w: number; h: number; rot?: number };

function keys() {
  const out: Record<string, Box> = {};
  for (let n = 1; n <= 19; n++) {
    const r = Math.floor((n - 1) / 5);
    const c = (n - 1) % 5;
    out[`k${String(n).padStart(2, "0")}`] = {
      x: COL_X[c] + (n === 16 ? 18 : 0),
      y: ROW_Y[r] + (c === 0 ? PINKY_DROP : 0),
      w: KEY_W,
      h: KEY_H,
    };
  }
  return out;
}

// Thumbstick centre.
const PX = 530;
const PY = 432;

const LAYOUT: Record<string, Box> = {
  ...keys(),
  wheel_up: { x: 370, y: 266, w: 40, h: 36 },
  wheel_click: { x: 370, y: 304, w: 40, h: 36 },
  wheel_down: { x: 370, y: 342, w: 40, h: 36 },
  top_button: { x: 456, y: 334, w: 52, h: 28 },
  dpad_up: { x: PX - 18, y: PY - 58, w: 36, h: 36 },
  dpad_right: { x: PX + 22, y: PY - 18, w: 36, h: 36 },
  dpad_down: { x: PX - 18, y: PY + 22, w: 36, h: 36 },
  dpad_left: { x: PX - 58, y: PY - 18, w: 36, h: 36 },
  dpad_up_right: { x: PX + 22, y: PY - 50, w: 28, h: 28 },
  dpad_down_right: { x: PX + 22, y: PY + 22, w: 28, h: 28 },
  dpad_down_left: { x: PX - 50, y: PY + 22, w: 28, h: 28 },
  dpad_up_left: { x: PX - 50, y: PY - 50, w: 28, h: 28 },
  k20: { x: 475, y: 540, w: 110, h: 64, rot: -15 },
};

const DIAGONALS = new Set(["dpad_up_right", "dpad_down_right", "dpad_down_left", "dpad_up_left"]);
const isKey = (c: string) => /^k\d\d$/.test(c);

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

// The control's name as a title: "Key 05", "Wheel up", "Thumbpad up-right".
export function controlTitle(control: string): string {
  if (isKey(control)) return `Key ${control.slice(1)}`;
  const words = control.startsWith("dpad_")
    ? `Thumbpad ${control.slice(5).replace(/_/g, "-")}`
    : control.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// The wheel is too narrow for its full names.
const CORNER: Record<string, string> = { wheel_up: "▲", wheel_click: "●", wheel_down: "▼" };

const pct = (v: number, of: number) => `${(v / of) * 100}%`;

// Keys look like keycaps; the wheel and thumbpad parts are see-through so the
// drawing underneath shows.
function look(control: string, selected: boolean, view: View): CSSProperties {
  if (selected && view === "actuation") {
    return { border: "2px solid #44b030", background: "rgba(46, 92, 30, 0.92)" };
  }
  if (selected) {
    return { border: "2px solid #1a9fff", background: "rgba(26, 61, 92, 0.92)", boxShadow: "0 0 8px #1a9fff" };
  }
  if (isKey(control) || control === "top_button") {
    return {
      border: "1px solid #4b5361",
      background: "linear-gradient(180deg, #3b434e 0%, #272d35 100%)",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.10), 0 2px 3px rgba(0,0,0,0.6)",
    };
  }
  return { border: "1px solid rgba(160,170,185,0.25)", background: "rgba(20,24,29,0.35)" };
}

const rotate = (b: Box) => (b.rot ? `rotate(${b.rot} ${b.x + b.w / 2} ${b.y + b.h / 2})` : undefined);

function glowOf(control: string): string {
  if (isKey(control) && control !== "k20") return COLUMN_GLOW[(Number(control.slice(1)) - 1) % 5];
  return COLUMN_GLOW[4];
}

function Picture() {
  const sockets = Object.entries(LAYOUT).filter(([c]) => isKey(c));
  const top = LAYOUT.top_button;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <defs>
        <linearGradient id="tt-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2e353d" />
          <stop offset="1" stopColor="#171b20" />
        </linearGradient>
        <linearGradient id="tt-wing" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#1a1e23" />
          <stop offset="0.6" stopColor="#30373f" />
          <stop offset="1" stopColor="#1a1e23" />
        </linearGradient>
        <linearGradient id="tt-palm" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2a3037" />
          <stop offset="0.35" stopColor="#1a1e23" />
          <stop offset="1" stopColor="#1a1e23" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="tt-stick" cx="0.38" cy="0.32" r="0.75">
          <stop offset="0" stopColor="#4a525d" />
          <stop offset="1" stopColor="#15191e" />
        </radialGradient>
        <linearGradient id="tt-wheel" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#0d1013" />
          <stop offset="0.5" stopColor="#8a929c" />
          <stop offset="1" stopColor="#0d1013" />
        </linearGradient>
        <filter id="tt-blur">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>

      {/* Cable */}
      <path d="M492 0 V122" stroke="#2a3037" strokeWidth={8} />
      {/* Key deck, with the lower-left corner cut away */}
      <path
        d="M4 26 Q4 6 24 6 H426 Q446 6 446 26 V420 Q446 432 432 432 H44 L4 392 Z"
        fill="url(#tt-body)"
        stroke="#434b57"
        strokeWidth={2}
      />
      {/* Thumb wing: the stem with the status lights, then the stick module */}
      <rect x={456} y={118} width={70} height={232} rx={26} fill="url(#tt-wing)" stroke="#434b57" strokeWidth={2} />
      {[230, 254, 278].map((y, i) => (
        <circle key={y} cx={514} cy={y} r={3} fill={LED_COLOURS[i]} />
      ))}
      <rect x={440} y={316} width={158} height={192} rx={44} fill="url(#tt-wing)" stroke="#434b57" strokeWidth={2} />
      {/* Arm that holds the thumb key */}
      <rect x={500} y={490} width={56} height={50} fill="#1d2228" />
      {/* Palm rest, fading out at the bottom of the picture */}
      <path
        d={`M30 ${H} V450 Q34 404 120 398 Q230 388 340 398 Q424 406 428 452 V${H} Z`}
        fill="url(#tt-palm)"
        stroke="#434b57"
        strokeOpacity={0.5}
      />

      {/* Underglow around every key */}
      {sockets.map(([c, b]) => (
        <rect
          key={`g${c}`}
          x={b.x - 5}
          y={b.y - 5}
          width={b.w + 10}
          height={b.h + 10}
          rx={12}
          fill="none"
          stroke={glowOf(c)}
          strokeWidth={3}
          strokeOpacity={0.75}
          filter="url(#tt-blur)"
          transform={rotate(b)}
        />
      ))}
      {sockets.map(([c, b]) => (
        <rect
          key={c}
          x={b.x - 4}
          y={b.y - 4}
          width={b.w + 8}
          height={b.h + 8}
          rx={11}
          fill="#0e1115"
          stroke={glowOf(c)}
          strokeOpacity={0.55}
          transform={rotate(b)}
        />
      ))}

      {/* Scroll wheel under key 15 */}
      <rect x={364} y={258} width={52} height={128} rx={20} fill="#0e1115" stroke={COLUMN_GLOW[4]} strokeOpacity={0.6} strokeWidth={2} />
      <rect x={378} y={268} width={24} height={108} rx={10} fill="url(#tt-wheel)" />
      {Array.from({ length: 13 }, (_, i) => (
        <line key={i} x1={379} x2={401} y1={274 + i * 8} y2={274 + i * 8} stroke="#0b0d10" strokeWidth={2.5} />
      ))}

      {/* Top button and thumbstick */}
      <circle cx={top.x + top.w / 2} cy={top.y + top.h / 2} r={22} fill="#0e1115" />
      <circle cx={PX} cy={PY} r={66} fill="#0e1115" stroke="#434b57" />
      <circle cx={PX} cy={PY} r={56} fill="url(#tt-stick)" />
      <circle cx={PX} cy={PY} r={18} fill="#1c2127" stroke="#4b5361" />
    </svg>
  );
}

type View = "bindings" | "actuation";

const cornerStyle: CSSProperties = { display: "flex", gap: 4, fontSize: 11, lineHeight: 1 };
// Steam's line height is taller than a key has room for, so labels set their own.
const labelStyle: CSSProperties = {
  fontSize: 13,
  lineHeight: 1.15,
  fontWeight: 600,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
  textAlign: "center",
};

// "bindings": every control can be selected and shows its binding.
// "actuation": only keys 01-20 can be selected and each shows its actuation.
export function Keypad(props: {
  profile: ProfileState;
  view: View;
  selected: readonly string[];
  defaultMm: number;
  onSelect(control: string): void;
}) {
  const { profile, view, selected, defaultMm, onSelect } = props;
  const controls = Object.keys(LAYOUT).filter(
    (c) => c in profile.bindings && (profile.dpad_mode === "8way" || !DIAGONALS.has(c)),
  );

  return (
    // Sized by the page height; the width follows the drawing's shape.
    <div style={{ position: "relative", height: "100%", aspectRatio: `${W} / ${H}`, maxWidth: "100%", flexShrink: 0 }}>
      <Picture />
      <Focusable style={{ position: "absolute", inset: 0 }} flow-children="grid">
        {controls.map((c) => {
          const box = LAYOUT[c];
          const style: CSSProperties = {
            position: "absolute",
            left: pct(box.x, W),
            top: pct(box.y, H),
            width: pct(box.w, W),
            height: pct(box.h, H),
            transform: box.rot ? `rotate(${box.rot}deg)` : undefined,
            boxSizing: "border-box",
            borderRadius: c === "top_button" ? 14 : c.startsWith("dpad") ? 18 : 8,
            color: "#dfe3e6",
            padding: "2px 4px",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            ...look(c, selected.includes(c), view),
          };
          if (view === "actuation" && !isKey(c)) {
            return (
              <div key={c} style={{ ...style, opacity: 0.35 }}>
                <div style={cornerStyle}>
                  <span style={{ opacity: 0.6 }}>{CORNER[c] ?? controlName(c)}</span>
                </div>
              </div>
            );
          }
          return (
            <Focusable
              key={c}
              onActivate={() => onSelect(c)}
              onClick={() => onSelect(c)}
              style={{ ...style, cursor: "pointer" }}
            >
              <div style={cornerStyle}>
                <span style={{ opacity: 0.6 }}>{CORNER[c] ?? controlName(c)}</span>
                <span style={{ flex: 1 }} />
                {view === "bindings" && c in profile.secondary && <span>2×</span>}
              </div>
              <div style={labelStyle}>
                {view === "actuation"
                  ? `${(profile.actuation[c] ?? defaultMm).toFixed(1)} mm`
                  : profile.bindings[c].label}
              </div>
            </Focusable>
          );
        })}
      </Focusable>
    </div>
  );
}
