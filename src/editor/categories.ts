export type Pick = { label: string; text: string };
export type Category = { id: string; label: string; picks: Pick[]; modifiers: boolean };

const same = (names: string[]): Pick[] => names.map((n) => ({ label: n, text: n }));
const named = (pairs: [string, string][]): Pick[] => pairs.map(([text, label]) => ({ label, text }));

// The keys the backend knows (py_modules/tartarus/codes.py), grouped like Synapse's
// Category / Key dropdowns. "modifiers" offers Ctrl, Shift, Alt and Super to combine with the key.
export const CATEGORIES: Category[] = [
  { id: "letters", label: "Letters", modifiers: true, picks: same("ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("")) },
  { id: "numbers", label: "Numbers", modifiers: true, picks: same("1234567890".split("")) },
  { id: "function", label: "Function keys", modifiers: true, picks: same(Array.from({ length: 24 }, (_, i) => `F${i + 1}`)) },
  {
    id: "navigation",
    label: "Navigation",
    modifiers: true,
    picks: named([
      ["Esc", "Esc"], ["Tab", "Tab"], ["Space", "Space"], ["Enter", "Enter"], ["Backspace", "Backspace"],
      ["Delete", "Delete"], ["Insert", "Insert"], ["Home", "Home"], ["End", "End"], ["PageUp", "Page Up"],
      ["PageDown", "Page Down"], ["Up", "↑"], ["Down", "↓"], ["Left", "←"], ["Right", "→"],
      ["CapsLock", "Caps Lock"], ["PrintScreen", "Print Screen"], ["Pause", "Pause"], ["ScrollLock", "Scroll Lock"],
      ["NumLock", "Num Lock"],
    ]),
  },
  {
    id: "symbols",
    label: "Symbols",
    modifiers: true,
    picks: named([
      ["Minus", "-"], ["Equal", "="], ["LeftBracket", "["], ["RightBracket", "]"], ["Backslash", "\\"],
      ["Semicolon", ";"], ["Apostrophe", "'"], ["Grave", "`"], ["Comma", ","], ["Period", "."], ["Slash", "/"],
    ]),
  },
  {
    id: "numpad",
    label: "Numpad",
    modifiers: true,
    picks: [
      ...Array.from({ length: 10 }, (_, i): Pick => ({ label: `Num ${i}`, text: `KP${i}` })),
      ...named([["KPPlus", "Num +"], ["KPMinus", "Num -"], ["KPAsterisk", "Num *"], ["KPSlash", "Num /"], ["KPDot", "Num ."], ["KPEnter", "Num Enter"]]),
    ],
  },
  {
    id: "modifiers",
    label: "Modifiers",
    modifiers: true,
    picks: named([["Ctrl", "Ctrl"], ["Shift", "Shift"], ["Alt", "Alt"], ["Super", "Super"], ["RCtrl", "Right Ctrl"], ["RShift", "Right Shift"], ["RAlt", "Right Alt"]]),
  },
  {
    id: "mouse",
    label: "Mouse",
    modifiers: true,
    picks: named([
      ["LMB", "Left click"], ["RMB", "Right click"], ["MMB", "Middle click"], ["Mouse4", "Back (Mouse 4)"],
      ["Mouse5", "Forward (Mouse 5)"], ["WheelUp", "Wheel up"], ["WheelDown", "Wheel down"],
    ]),
  },
  {
    id: "media",
    label: "Media",
    modifiers: false,
    picks: named([["Vol+", "Volume up"], ["Vol-", "Volume down"], ["Mute", "Mute"], ["Play", "Play / Pause"], ["Next", "Next track"], ["Prev", "Previous track"]]),
  },
  { id: "steam", label: "Steam", modifiers: false, picks: named([["steam:menu", "Steam menu"], ["steam:qam", "Quick Access"]]) },
  { id: "disable", label: "Disable", modifiers: false, picks: [] },
  { id: "type", label: "Type a binding", modifiers: false, picks: [] },
];

export const MODIFIERS = ["Ctrl", "Shift", "Alt", "Super"];
