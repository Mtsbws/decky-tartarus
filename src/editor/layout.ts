import type { State } from "../api";

// The height of a page's content area under the editor's tabs,
// sized so nothing reaches the Steam footer on the Deck's 1280×800 screen.
// Measured on the Deck: Steam's tab panel leaves 356 of the 534 CSS px (40 + 58 above, 40 + 40 below).
export const PAGE_HEIGHT = "calc(100vh - 178px)";

export const ERROR = "#e05050";

// Compact grey buttons, as in CSS Loader's rows.
export const BUTTON = { width: "auto", minWidth: 0, padding: "4px 14px" };
export const PICK = { width: "auto", minWidth: 0, padding: "4px 10px", margin: 0, fontSize: 13 };

// Slider steps of 0.1 arrive as floats like 2.6000000000000005.
export const tenth = (v: number) => Math.round(v * 10) / 10;
export const mmText = (v: number) => `${v.toFixed(1)} mm`;

// Adjustable actuation has no switch in the UI; these say why the mm values don't apply right now.
const ACTUATION_NOTES: Record<string, string> = {
  unavailable: "Adjustable actuation unavailable: keys fire at the fixed hardware point.",
  off: "Adjustable actuation is off: keys fire at the fixed hardware point.",
};
export const actuationNote = (s: State) => (s.connected && s.actuation.status ? ACTUATION_NOTES[s.actuation.status] ?? null : null);
