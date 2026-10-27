import { DialogButton, Focusable, SliderField, Toggle } from "@decky/ui";
import { useEffect, useState } from "react";

import { errorText, ProfileState, setActuation, setBindingText, State } from "../api";
import { Card, Row } from "./Card";
import { ChoosePage } from "./ChoosePage";
import { EditingRow } from "./EditingRow";
import { controlTitle, Keypad } from "./Keypad";
import { BUTTON, DRIVER_NOTE, ERROR, mmText, PAGE_HEIGHT, tenth } from "./layout";
import { RecordButton } from "./RecordButton";
import { SecondaryPage } from "./SecondaryPage";
import { useDebounce } from "./useDebounce";

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
  const { default_mm, min_mm, max_mm } = state.actuation;
  const [sub, setSub] = useState<"choose" | "secondary" | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [draft, setDraft] = useState<number | null>(null);
  const debounce = useDebounce(300);

  // A sub-page, a card error and a slider draft belong to the control and profile they came from.
  useEffect(() => {
    setSub(null);
    setCardError(null);
    setDraft(null);
    return () => debounce.flush();
  }, [selected, profile.id]);

  function reset(factory: string) {
    setBindingText(profile.id, selected, factory)
      .then((r) => {
        setCardError(r.ok ? null : r.error);
        onChanged(r.state);
      })
      .catch((e) => setCardError(errorText(e)));
  }

  function changeActuation(v: number) {
    const mm = tenth(v);
    const profileId = profile.id;
    const control = selected;
    setDraft(mm);
    debounce.schedule(() => {
      setActuation(profileId, control, mm)
        .then((s) => {
          setCardError(null);
          onChanged(s);
          if (!debounce.isPending()) setDraft(null);
        })
        .catch((e) => {
          setCardError(errorText(e));
          setDraft(null);
        });
    });
  }

  const binding = profile.bindings[selected];
  const secondary = profile.secondary[selected];
  const isKey = /^k\d\d$/.test(selected);
  const actuation = draft ?? profile.actuation[selected] ?? default_mm;

  if (sub === "choose") {
    return (
      <div style={{ height: PAGE_HEIGHT }}>
        <ChoosePage control={selected} state={state} profile={profile} onChanged={onChanged} onDone={() => setSub(null)} />
      </div>
    );
  }
  if (sub === "secondary") {
    return (
      <div style={{ height: PAGE_HEIGHT }}>
        <SecondaryPage control={selected} state={state} profile={profile} onChanged={onChanged} onBack={() => setSub(null)} />
      </div>
    );
  }

  return (
    // The drawing takes the full page height; the Editing row sits above the card.
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      <Keypad profile={profile} view="bindings" selected={[selected]} defaultMm={default_mm} onSelect={onSelect} />
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        <EditingRow state={state} profile={profile} onView={onView} />
        <Card title={controlTitle(selected)}>
          <Row
            label={
              <>
                Binding: <b>{binding?.label}</b>
              </>
            }
          >
            <DialogButton style={BUTTON} onClick={() => setSub("choose")}>
              Choose…
            </DialogButton>
            <RecordButton control={selected} profile={profile} onChanged={onChanged} onError={setCardError} />
          </Row>
          {binding?.factory && (
            <Row label={`Factory default (${binding.factory})`}>
              <DialogButton style={BUTTON} onClick={() => reset(binding.factory)}>
                Reset
              </DialogButton>
            </Row>
          )}
          {isKey && (
            <Row label={`Actuation: ${mmText(actuation)}`} stacked>
              <SliderField value={actuation} min={min_mm} max={max_mm} step={0.1} bottomSeparator="none" onChange={changeActuation} />
            </Row>
          )}
          {isKey && (
            <Row label="Secondary function">
              <DialogButton style={BUTTON} onClick={() => setSub("secondary")}>
                {secondary ? `${secondary.label} · ${mmText(secondary.actuation)} ›` : "Off ›"}
              </DialogButton>
            </Row>
          )}
          {selected.startsWith("dpad_") && (
            <Row label="8-way D-pad">
              <Toggle value={profile.dpad_mode === "8way"} onChange={onDpad} />
            </Row>
          )}
          {isKey && state.actuation.status !== "on" && <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>{DRIVER_NOTE}</div>}
          {cardError && <div style={{ color: ERROR, marginTop: 4 }}>{cardError}</div>}
          {error && <div style={{ color: ERROR, marginTop: 4 }}>{error}</div>}
        </Card>
      </Focusable>
    </Focusable>
  );
}
