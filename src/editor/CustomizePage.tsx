import { DialogButton, Field, Focusable, ToggleField } from "@decky/ui";
import { useEffect, useState } from "react";

import { errorText, ProfileState, setBindingText, State } from "../api";
import { Card } from "./Card";
import { ChoosePage } from "./ChoosePage";
import { DeepPressPage } from "./DeepPressPage";
import { EditingRow } from "./EditingRow";
import { controlTitle, Keypad } from "./Keypad";
import { BUTTON, DRIVER_NOTE, ERROR, PAGE_HEIGHT } from "./layout";
import { RecordButton } from "./RecordButton";

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
  const { state, profile, selected, error, onSelect, onView, onDpad, onChanged } = props;
  const [sub, setSub] = useState<"choose" | "deep" | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  // A sub-page and a card error belong to the control and profile they came from.
  useEffect(() => {
    setSub(null);
    setCardError(null);
  }, [selected, profile.id]);

  function reset(factory: string) {
    setBindingText(profile.id, selected, factory)
      .then((r) => {
        setCardError(r.ok ? null : r.error);
        onChanged(r.state);
      })
      .catch((e) => setCardError(errorText(e)));
  }

  const binding = profile.bindings[selected];
  const secondary = profile.secondary[selected];

  return (
    // The drawing takes the full page height; the Editing row sits above the card.
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      {sub === null && (
        <Keypad profile={profile} view="bindings" selected={[selected]} defaultMm={state.actuation.default_mm} onSelect={onSelect} />
      )}
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        <EditingRow state={state} profile={profile} onView={onView} />
        {sub === "choose" ? (
          <ChoosePage control={selected} state={state} profile={profile} onChanged={onChanged} onDone={() => setSub(null)} />
        ) : sub === "deep" ? (
          <DeepPressPage control={selected} state={state} profile={profile} onChanged={onChanged} onBack={() => setSub(null)} />
        ) : (
          <Card title={controlTitle(selected)}>
            <div style={{ fontSize: 22, fontWeight: 700, margin: "2px 0 6px" }}>{binding?.label}</div>
            <Field label="Binding" padding="compact">
              <DialogButton style={BUTTON} onClick={() => setSub("choose")}>
                Choose…
              </DialogButton>
            </Field>
            <Field label="Record from a key" padding="compact">
              <RecordButton control={selected} profile={profile} onChanged={onChanged} onError={setCardError} />
            </Field>
            {binding?.factory && (
              <Field label={`Factory default (${binding.factory})`} padding="compact">
                <DialogButton style={BUTTON} onClick={() => reset(binding.factory)}>
                  Reset
                </DialogButton>
              </Field>
            )}
            {/^k\d\d$/.test(selected) && (
              <Field
                label="Deep press"
                description={state.actuation.status !== "on" ? DRIVER_NOTE : undefined}
                padding="compact"
              >
                <DialogButton style={BUTTON} onClick={() => setSub("deep")}>
                  {secondary ? `${secondary.label} · ${secondary.actuation.toFixed(1)} mm ›` : "Off ›"}
                </DialogButton>
              </Field>
            )}
            {selected.startsWith("dpad_") && (
              <ToggleField label="8-way D-pad" checked={profile.dpad_mode === "8way"} onChange={onDpad} />
            )}
            {cardError && <div style={{ color: ERROR }}>{cardError}</div>}
            {error && <div style={{ color: ERROR }}>{error}</div>}
          </Card>
        )}
      </Focusable>
    </Focusable>
  );
}
