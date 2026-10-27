import { DialogButton, Field, Focusable, ToggleField } from "@decky/ui";
import { useEffect, useState } from "react";

import { ProfileState, State } from "../api";
import { Card } from "./Card";
import { EditingRow } from "./EditingRow";
import { controlTitle, Keypad } from "./Keypad";
import { ERROR, PAGE_HEIGHT } from "./layout";
import { SubPage } from "./SubPage";

const buttonStyle = { width: "auto", minWidth: 0, padding: "4px 14px" };

export function CustomizePage(props: {
  state: State;
  profile: ProfileState;
  selected: string;
  error: string | null;
  onSelect(c: string): void;
  onView(id: string): void;
  onDpad(eight: boolean): void;
  onChanged(s: State): void;
}) {
  const { state, profile, selected, error, onSelect, onView, onDpad } = props;
  const [sub, setSub] = useState<"choose" | null>(null);

  // A sub-page belongs to the control and profile it was opened for.
  useEffect(() => setSub(null), [selected, profile.id]);

  const binding = profile.bindings[selected];
  const secondary = profile.secondary[selected];

  return (
    <div style={{ height: PAGE_HEIGHT, display: "flex", flexDirection: "column", gap: 8 }}>
      <EditingRow state={state} profile={profile} onView={onView} />
      {sub === "choose" ? (
        <SubPage title={`Choose a binding for ${controlTitle(selected)}`} onBack={() => setSub(null)}>
          <div>Stub</div>
        </SubPage>
      ) : (
        <Focusable flow-children="row" style={{ flex: 1, minHeight: 0, display: "flex", gap: 16 }}>
          <Keypad profile={profile} view="bindings" selected={[selected]} defaultMm={state.actuation.default_mm} onSelect={onSelect} />
          <Focusable flow-children="column" style={{ flex: 1, minWidth: 300 }}>
            <Card title={controlTitle(selected)}>
              <div style={{ fontSize: 22, fontWeight: 700, margin: "2px 0 6px" }}>{binding?.label}</div>
              <Field label="Binding" padding="compact">
                <DialogButton style={buttonStyle} onClick={() => setSub("choose")}>
                  Choose…
                </DialogButton>
              </Field>
              <Field label="Record from a key" padding="compact">
                <DialogButton style={buttonStyle}>Record</DialogButton>
              </Field>
              {binding?.factory && (
                <Field label={`Factory default (${binding.factory})`} padding="compact">
                  <DialogButton style={buttonStyle}>Reset</DialogButton>
                </Field>
              )}
              {/^k\d\d$/.test(selected) && (
                <Field label="Deep press" padding="compact">
                  <DialogButton style={buttonStyle}>
                    {secondary ? `${secondary.label} · ${secondary.actuation.toFixed(1)} mm ›` : "Off ›"}
                  </DialogButton>
                </Field>
              )}
              {selected.startsWith("dpad_") && (
                <ToggleField label="8-way D-pad" checked={profile.dpad_mode === "8way"} onChange={onDpad} />
              )}
              {error && <div style={{ color: ERROR }}>{error}</div>}
            </Card>
          </Focusable>
        </Focusable>
      )}
    </div>
  );
}
