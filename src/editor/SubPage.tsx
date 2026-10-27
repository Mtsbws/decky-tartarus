import { DialogButton, Focusable } from "@decky/ui";
import type { ReactNode } from "react";

// A page opened from a card. B goes back to the card instead of the sidebar.
export function SubPage({ title, onBack, children }: { title: string; onBack(): void; children: ReactNode }) {
  return (
    <Focusable
      style={{ height: "100%", display: "flex", flexDirection: "column", gap: 8 }}
      onCancel={(e) => {
        e.stopPropagation();
        onBack();
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <DialogButton style={{ width: "auto", minWidth: 0, padding: "4px 14px" }} onClick={onBack}>
          ‹ Back
        </DialogButton>
        <div style={{ fontSize: 18, fontWeight: 600 }}>{title}</div>
      </div>
      {children}
    </Focusable>
  );
}
