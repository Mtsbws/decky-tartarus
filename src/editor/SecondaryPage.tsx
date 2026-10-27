import { DialogButton, SliderField, Toggle } from "@decky/ui";
import { useEffect, useState } from "react";

import { errorText, ProfileState, setSecondary, State } from "../api";
import { Card, Row } from "./Card";
import { ChoosePage } from "./ChoosePage";
import { controlTitle } from "./Keypad";
import { baseControl, Layer, layerMm, layerSecondary } from "./layers";
import { actuationNote, BUTTON, ERROR, mmText, tenth } from "./layout";
import { RecordButton } from "./RecordButton";
import { SubPage } from "./SubPage";
import { useDebounce } from "./useDebounce";

export function SecondaryPage(props: {
  control: string;
  state: State;
  profile: ProfileState;
  onChanged(s: State): void;
  onBack(): void;
}) {
  const { control, state, profile, onChanged, onBack } = props;
  const { default_mm, max_mm, min_gap_mm } = state.actuation;
  const [choosing, setChoosing] = useState(false);
  const [draft, setDraft] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debounce = useDebounce(300);

  useEffect(() => {
    setChoosing(false);
    setDraft(null);
    setError(null);
    return () => debounce.flush();
  }, [control, profile.id]);

  // "k05" or "k05.h": the Hypershift entry's secondary function is its own, set against the entry's depth.
  const layer: Layer = control.split(".").includes("h") ? "hypershift" : "standard";
  const key = baseControl(control);
  const secondary = layerSecondary(profile, key, layer);
  const value = draft ?? secondary?.actuation ?? max_mm;
  const min = Math.min(tenth(layerMm(profile, key, layer, default_mm) + min_gap_mm), max_mm);

  // Off removes the secondary function with its binding; on starts it at the deepest point, unbound.
  // A depth write still in its debounce would recreate it after the off, so off drops it.
  function toggle(on: boolean) {
    if (!on) {
      debounce.cancel();
      setDraft(null);
    }
    setSecondary(profile.id, control, on ? max_mm : null)
      .then((s) => {
        setError(null);
        onChanged(s);
      })
      .catch((e) => setError(errorText(e)));
  }

  function change(v: number) {
    const mm = tenth(v);
    const profileId = profile.id;
    setDraft(mm);
    debounce.schedule(() => {
      setSecondary(profileId, control, mm)
        .then((s) => {
          setError(null);
          onChanged(s);
          if (!debounce.isPending()) setDraft(null);
        })
        .catch((e) => {
          setError(errorText(e));
          setDraft(null);
        });
    });
  }

  if (choosing) {
    return <ChoosePage control={control + ".b"} state={state} profile={profile} onChanged={onChanged} onDone={() => setChoosing(false)} />;
  }

  return (
    <SubPage title={`Secondary function · ${controlTitle(key)}${layer === "hypershift" ? " · Hypershift" : ""}`} onBack={onBack}>
      <div style={{ maxWidth: 720 }}>
        <Card>
          <Row label="Secondary function" description="A second binding when the key is pressed deeper.">
            <Toggle value={secondary !== undefined} onChange={toggle} />
          </Row>
          {secondary && (
            <>
              <Row label={`Binding: ${secondary.label}`}>
                <DialogButton style={BUTTON} onClick={() => setChoosing(true)}>
                  Choose…
                </DialogButton>
                <RecordButton control={control + ".b"} profile={profile} onChanged={onChanged} onError={setError} />
              </Row>
              <Row label={`Actuation: ${mmText(value)}`} stacked>
                <SliderField value={value} min={min} max={max_mm} step={0.1} bottomSeparator="none" onChange={change} />
              </Row>
            </>
          )}
          {actuationNote(state) && <div style={{ fontSize: 13, opacity: 0.7, marginTop: 6 }}>{actuationNote(state)}</div>}
          {error && <div style={{ color: ERROR, marginTop: 6 }}>{error}</div>}
        </Card>
      </div>
    </SubPage>
  );
}
