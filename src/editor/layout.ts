// The height of a page's content area under the editor's tabs,
// sized so nothing reaches the Steam footer on the Deck's 1280×800 screen.
// Measured on the Deck: Steam's tab panel leaves 316 of the 534 CSS px (60 + 58 above, 40 + 60 below).
export const PAGE_HEIGHT = "calc(100vh - 218px)";

export const ERROR = "#e05050";

// Compact grey buttons, as in CSS Loader's rows.
export const BUTTON = { width: "auto", minWidth: 0, padding: "4px 14px" };
export const PICK = { width: "auto", minWidth: 0, padding: "4px 10px", margin: 0, fontSize: 13 };

// Slider steps of 0.1 arrive as floats like 2.6000000000000005.
export const tenth = (v: number) => Math.round(v * 10) / 10;
export const mmText = (v: number) => `${v.toFixed(1)} mm`;

export const DRIVER_NOTE = "Applies only with Adjustable actuation on.";
