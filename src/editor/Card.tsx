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
