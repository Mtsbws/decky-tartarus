export type QuickPick = { label: string; text: string };

// Shown in this order. "More keys" collapses the F-keys; "Factory default" is
// added by the picker because its text depends on the control.
export const QUICK_PICKS: QuickPick[] = [
  { label: "Esc", text: "Esc" },
  { label: "Steam menu", text: "steam:menu" },
  { label: "Quick Access", text: "steam:qam" },
  { label: "Tab", text: "Tab" },
  { label: "Space", text: "Space" },
  { label: "Enter", text: "Enter" },
  { label: "Shift", text: "Shift" },
  { label: "Ctrl", text: "Ctrl" },
  { label: "Alt", text: "Alt" },
  ...Array.from({ length: 12 }, (_, i) => ({ label: `F${i + 1}`, text: `F${i + 1}` })),
  { label: "LMB", text: "LMB" },
  { label: "RMB", text: "RMB" },
  { label: "MMB", text: "MMB" },
  { label: "Vol+", text: "Vol+" },
  { label: "Vol-", text: "Vol-" },
  { label: "Mute", text: "Mute" },
  { label: "Play", text: "Play" },
  { label: "Disable", text: "disable" },
];

export const isSteamPick = (p: QuickPick) => p.text.startsWith("steam:");
export const isMoreKey = (p: QuickPick) => /^F\d+$/.test(p.text);
