import { Focusable } from "@decky/ui";
import type { CSSProperties, ReactNode } from "react";

export function Card({ title, style, children }: { title?: ReactNode; style?: CSSProperties; children: ReactNode }) {
  return (
    <div style={{ background: "#14181d", borderRadius: 6, padding: "12px 14px", boxSizing: "border-box", ...style }}>
      {title && (
        <div style={{ color: "#5bd14a", textTransform: "uppercase", fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

// A slim settings row: Steam's Field is about 78 px tall, too tall for a card that must fit the page.
// Stacked puts the children under the label: Steam's slider track is a fixed 250 px wide.
export function Row(props: { label: ReactNode; description?: ReactNode; stacked?: boolean; children?: ReactNode }) {
  const { label, description, stacked, children } = props;
  return (
    <Focusable
      flow-children={stacked ? "column" : "row"}
      style={{
        display: "flex",
        flexDirection: stacked ? "column" : "row",
        alignItems: stacked ? "stretch" : "center",
        gap: stacked ? 0 : 10,
        minHeight: 44,
        padding: stacked ? "8px 12px 0" : "4px 12px",
        marginTop: 4,
        borderRadius: 4,
        background: "rgba(255, 255, 255, 0.06)",
        boxSizing: "border-box",
      }}
    >
      <div style={{ flex: stacked ? undefined : 1, minWidth: 0 }}>
        <div>{label}</div>
        {description && <div style={{ fontSize: 12, opacity: 0.7 }}>{description}</div>}
      </div>
      {children}
    </Focusable>
  );
}
