import { Focusable } from "@decky/ui";
import { CSSProperties, ReactNode, useLayoutEffect, useRef } from "react";

import { BindingDict, ProfileState } from "../api";
import { LED_COLOURS, LED_UNLIT } from "../StatusLights";
import { HYPERSHIFT_ACCENT, Layer, layerMm, layerSecondary, SECONDARY_ACCENT } from "./layers";

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
  wheel_up: { x: 366, y: 262, w: 48, h: 40 },
  wheel_click: { x: 366, y: 304, w: 48, h: 40 },
  wheel_down: { x: 366, y: 346, w: 48, h: 40 },
  // Big enough to show its binding.
  top_button: { x: 448, y: 320, w: 78, h: 42 },
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

// Only keys 01-20 show their name in the corner: the wheel, thumbpad and top button explain themselves
// and need the room for their binding.
const corner = (c: string) => (isKey(c) ? controlName(c) : null);

const pct = (v: number, of: number) => `${(v / of) * 100}%`;

// Keys look like keycaps; the wheel and thumbpad parts are see-through so the
// drawing underneath shows.
function look(control: string, selected: boolean, view: View, layer: Layer, isHypershiftKey: boolean): CSSProperties {
  if (isHypershiftKey) {
    return { border: `2px solid ${HYPERSHIFT_ACCENT}`, background: "rgba(255, 96, 0, 0.35)" };
  }
  if (selected && layer === "hypershift") {
    return {
      border: `2px solid ${HYPERSHIFT_ACCENT}`,
      background: "rgba(92, 38, 0, 0.92)",
      boxShadow: `0 0 8px ${HYPERSHIFT_ACCENT}`,
    };
  }
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

// The default rainbow, one colour per column; the Lighting page shows it for spectrum and wave.
export function rainbow(control: string): string {
  if (isKey(control) && control !== "k20") return COLUMN_GLOW[(Number(control.slice(1)) - 1) % 5];
  return COLUMN_GLOW[4];
}

// What a control's underglow shows: a colour, or null when its light is off.
export type Glow = (control: string) => string | null;
const UNLIT = "#434b57";

// `level` scales the glow, as the backlight's brightness does. `leds` are the status lights; all lit when left out.
function Picture({ glow, level, leds }: { glow: Glow; level: number; leds?: readonly boolean[] }) {
  const sockets = Object.entries(LAYOUT).filter(([c]) => isKey(c));
  const top = LAYOUT.top_button;
  // The wheel has one light for its three controls.
  const wheel = glow("wheel_up") ?? glow("wheel_click") ?? glow("wheel_down");
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
        <circle key={y} cx={514} cy={y} r={3} fill={!leds || leds[i] ? LED_COLOURS[i] : LED_UNLIT} />
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
      {sockets.map(([c, b]) => glow(c) && (
        <rect
          key={`g${c}`}
          x={b.x - 5}
          y={b.y - 5}
          width={b.w + 10}
          height={b.h + 10}
          rx={12}
          fill="none"
          stroke={glow(c)!}
          strokeWidth={3}
          strokeOpacity={0.75 * level}
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
          stroke={glow(c) ?? UNLIT}
          strokeOpacity={glow(c) ? 0.55 * level : 0.5}
          transform={rotate(b)}
        />
      ))}

      {/* Scroll wheel under key 15 */}
      <rect x={364} y={258} width={52} height={128} rx={20} fill="#0e1115" stroke={wheel ?? UNLIT} strokeOpacity={wheel ? 0.6 * level : 0.5} strokeWidth={2} />
      <rect x={378} y={268} width={24} height={108} rx={10} fill="url(#tt-wheel)" />
      {Array.from({ length: 13 }, (_, i) => (
        <line key={i} x1={379} x2={401} y1={274 + i * 8} y2={274 + i * 8} stroke="#0b0d10" strokeWidth={2.5} />
      ))}

      {/* Top button and thumbstick */}
      <rect x={top.x - 4} y={top.y - 4} width={top.w + 8} height={top.h + 8} rx={18} fill="#0e1115" />
      <circle cx={PX} cy={PY} r={66} fill="#0e1115" stroke="#434b57" />
      <circle cx={PX} cy={PY} r={56} fill="url(#tt-stick)" />
      <circle cx={PX} cy={PY} r={18} fill="#1c2127" stroke="#4b5361" />
    </svg>
  );
}

type View = "bindings" | "actuation" | "preview";

// A small gap: a key with a secondary function needs the room for its "2×".
const cornerStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 2, fontSize: 11, lineHeight: 1 };
// Steam's line height is taller than a key has room for, so labels set their own.
const labelStyle: CSSProperties = { fontSize: 13, lineHeight: 1.1, fontWeight: 600, textAlign: "center" };
const MAX_FONT = 13;
const MIN_FONT = 9;

// A label wraps onto a second line first, then shrinks until it fits its control (9px at the least);
// past that it is cut off with "…", and the card shows it in full.
function FitLabel({ style, children }: { style?: CSSProperties; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = ref.current!;
    const box = el.parentElement!;
    const fit = () => {
      Object.assign(el.style, { display: "", WebkitLineClamp: "", WebkitBoxOrient: "", overflowWrap: "", overflow: "" });
      const fits = (size: number) =>
        el.scrollWidth <= el.clientWidth + 0.5 && el.scrollHeight <= 2 * 1.1 * size + 0.5 && box.scrollHeight <= box.clientHeight + 0.5;
      let size = MAX_FONT;
      el.style.fontSize = `${size}px`;
      while (size > MIN_FONT && !fits(size)) {
        size -= 0.5;
        el.style.fontSize = `${size}px`;
      }
      if (!fits(size)) {
        Object.assign(el.style, { display: "-webkit-box", WebkitLineClamp: "2", WebkitBoxOrient: "vertical", overflowWrap: "anywhere", overflow: "hidden" });
      }
    };
    fit();
    // The keypad is sized by the page, so the controls can change size.
    const watch = new ResizeObserver(fit);
    watch.observe(box);
    return () => watch.disconnect();
  });
  return (
    <div ref={ref} style={{ ...labelStyle, ...style }}>
      {children}
    </div>
  );
}

const tagStyle: CSSProperties = { padding: "0 3px", borderRadius: 3, color: "#111" };
const STEAM_TAGS: Record<string, string> = { menu: "Steam", qam: "QAM", keyboard: "Kbd" };

// Steam actions and Hypershift get a short tag; a shortcut may wrap after each "+".
function shortLabel(binding: BindingDict, label: string): ReactNode {
  if (binding.type === "hypershift") return <span style={{ ...tagStyle, background: HYPERSHIFT_ACCENT }}>HS</span>;
  if (binding.type === "steam") return <span style={{ ...tagStyle, background: "#1a9fff" }}>{STEAM_TAGS[binding.action ?? ""] ?? "Steam"}</span>;
  return label.replace(/\+/g, "+\u200b");
}

// "bindings": every control can be selected and shows its binding.
// "actuation": only keys 01-20 can be selected and each shows its actuation.
// "preview": shows the bindings, nothing can be selected; the D-pad skips the drawing.
export function Keypad(props: {
  profile: ProfileState;
  view: View;
  selected?: readonly string[];
  layer: Layer;
  defaultMm?: number;
  glow?: Glow;
  glowLevel?: number;
  leds?: readonly boolean[];
  onSelect?(control: string): void;
}) {
  const { profile, view, selected = [], layer, defaultMm = 0, glow = rainbow, glowLevel = 1, leds, onSelect = () => {} } = props;
  const hypershift = layer === "hypershift";
  // On the Hypershift layer a control without an entry shows its standard binding, dimmed.
  const shown = (c: string) => (hypershift ? profile.hypershift.bindings[c] : undefined) ?? profile.bindings[c];
  const label = (c: string) => shortLabel(shown(c).binding, shown(c).label);
  const controls = Object.keys(LAYOUT).filter(
    (c) => c in profile.bindings && (profile.dpad_mode === "8way" || !DIAGONALS.has(c)),
  );

  return (
    // Sized by the page height; the width follows the drawing's shape.
    <div style={{ position: "relative", height: "100%", aspectRatio: `${W} / ${H}`, maxWidth: "100%", flexShrink: 0 }}>
      <Picture glow={glow} level={glowLevel} leds={leds} />
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
            justifyContent: corner(c) ? "space-between" : "center",
            ...look(c, selected.includes(c), view, layer, hypershift && c === profile.hypershift.key),
          };
          if (hypershift && c === profile.hypershift.key) {
            // The layer's own key: it can't have a Hypershift entry, so it is only shown.
            return (
              <div key={c} style={style}>
                {corner(c) && (
                  <div style={cornerStyle}>
                    <span style={{ opacity: 0.6 }}>{corner(c)}</span>
                  </div>
                )}
                <FitLabel>{shortLabel({ type: "hypershift" }, "Hypershift")}</FitLabel>
              </div>
            );
          }
          if (view === "actuation" && (!isKey(c) || (hypershift && !(c in profile.hypershift.bindings)))) {
            return (
              <div key={c} style={{ ...style, opacity: 0.35 }}>
                {corner(c) && (
                  <div style={cornerStyle}>
                    <span style={{ opacity: 0.6 }}>{corner(c)}</span>
                  </div>
                )}
              </div>
            );
          }
          const content = (
            <>
              {corner(c) && (
                <div style={cornerStyle}>
                  <span style={{ opacity: 0.6 }}>{corner(c)}</span>
                  {view !== "actuation" && layerSecondary(profile, c, layer) && <span style={{ flexShrink: 0, color: SECONDARY_ACCENT, fontWeight: 700 }}>2×</span>}
                </div>
              )}
              <FitLabel
                style={{
                  // A Hypershift entry is orange; a fall-through standard binding is dimmed.
                  ...(hypershift && c in profile.hypershift.bindings
                    ? { color: HYPERSHIFT_ACCENT }
                    : { opacity: view !== "actuation" && hypershift ? 0.45 : 1 }),
                }}
              >
                {/* A key has about 28 CSS px for its label: "1.5" fits, "1.5 mm" doesn't (the card names the unit). */}
                {view === "actuation" ? layerMm(profile, c, layer, defaultMm).toFixed(1) : label(c)}
              </FitLabel>
            </>
          );
          if (view === "preview") {
            return (
              <div key={c} style={style}>
                {content}
              </div>
            );
          }
          return (
            <Focusable key={c} onActivate={() => onSelect(c)} onClick={() => onSelect(c)} style={{ ...style, cursor: "pointer" }}>
              {content}
            </Focusable>
          );
        })}
      </Focusable>
    </div>
  );
}
