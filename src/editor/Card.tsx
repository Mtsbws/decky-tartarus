import { Focusable } from "@decky/ui";
import type { ReactNode } from "react";

export function Card({ title, children }: { title?: ReactNode; children: ReactNode }) {
  return (
    <div style={{ background: "#14181d", borderRadius: 6, padding: "12px 14px", boxSizing: "border-box" }}>
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
export function Row({ label, description, children }: { label: ReactNode; description?: ReactNode; children?: ReactNode }) {
  return (
    <Focusable
      flow-children="row"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        minHeight: 44,
        padding: "4px 12px",
        marginTop: 4,
        borderRadius: 4,
        background: "rgba(255, 255, 255, 0.06)",
        boxSizing: "border-box",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div>{label}</div>
        {description && <div style={{ fontSize: 12, opacity: 0.7 }}>{description}</div>}
      </div>
      {children}
    </Focusable>
  );
}
