// A profile in the list: a slim row, as the Rows on the other pages, that selects the profile.
export const ROW = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  width: "100%",
  minWidth: 0,
  minHeight: 36,
  padding: "4px 12px",
  margin: 0,
  textAlign: "left" as const,
  borderRadius: 4,
  flexShrink: 0,
};
// The row colours live in a stylesheet, not inline, so they give way to Steam's focus style:
// an inline background stayed put on focus while Steam darkened the text, hiding the name.
export const ROW_CLASS = "Tartarus_ProfileRow";
export const ROW_CSS = `
.${ROW_CLASS}:not(.gpfocus):not(:focus) { background: rgba(255, 255, 255, 0.06) !important; color: #dfe3e6 !important; }
.${ROW_CLASS}.Tartarus_Selected:not(.gpfocus):not(:focus) { background: rgba(91, 209, 74, 0.22) !important; }
.${ROW_CLASS}.Tartarus_Selected { box-shadow: inset 3px 0 0 #5bd14a !important; }
`;
export const IN_USE = { fontSize: 11, padding: "1px 6px", borderRadius: 8, background: "#5bd14a", color: "#0e141b", flexShrink: 0 };
