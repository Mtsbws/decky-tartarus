import { DialogButton, Focusable, SliderField, Toggle } from "@decky/ui";
import { useEffect, useState } from "react";

import { clearHypershiftEntry, errorText, ProfileState, setActuation, setBindingText, State } from "../api";
import { Card, Row } from "./Card";
import { ChoosePage } from "./ChoosePage";
import { EditingRow } from "./EditingRow";
import { useKeypadGlow } from "./glow";
import { controlTitle, Keypad } from "./Keypad";
import { bindingOf, hasEntry, HYPERSHIFT_ACCENT, Layer, layerMm, layerSecondary, onLayer } from "./layers";
import { LayerSwitch } from "./LayerSwitch";
import { actuationNote, BUTTON, ERROR, mmText, PAGE_HEIGHT, tenth } from "./layout";
import { RecordButton } from "./RecordButton";
import { SecondaryPage } from "./SecondaryPage";
import { useDebounce } from "./useDebounce";

export function CustomizePage(props: {
  state: State;
  profile: ProfileState;
  selected: string;
  layer: Layer;
  onLayer(l: Layer): void;
  error: string | null;
  onSelect(c: string): void;
  onView(id: string): void;
  onDpad(eight: boolean): void;
  onChanged(s: State): void;
}) {
  const { state, profile, selected, layer, onLayer: onLayerChange, error, onSelect, onView, onDpad, onChanged } = props;
  const { default_mm, min_mm, max_mm } = state.actuation;
  const [sub, setSub] = useState<"choose" | "secondary" | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [draft, setDraft] = useState<number | null>(null);
  const debounce = useDebounce(300);
  const glow = useKeypadGlow(state, profile, layer);

  // A sub-page, a card error and a slider draft belong to the control and profile they came from.
  useEffect(() => {
    setSub(null);
    setCardError(null);
    setDraft(null);
    return () => debounce.flush();
  }, [selected, profile.id, layer]);

  function reset(factory: string) {
    setBindingText(profile.id, selected, factory)
      .then((r) => {
        setCardError(r.ok ? null : r.error);
        onChanged(r.state);
      })
      .catch((e) => setCardError(errorText(e)));
  }

  function clearEntry() {
    clearHypershiftEntry(profile.id, control)
      .then((s) => {
        setCardError(null);
        onChanged(s);
      })
      .catch((e) => setCardError(errorText(e)));
  }

  function changeActuation(v: number) {
    const mm = tenth(v);
    const profileId = profile.id;
    const target = control;
    setDraft(mm);
    debounce.schedule(() => {
      setActuation(profileId, target, mm)
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

  // The control the card edits: the plain name on Standard, "k05.h" on Hypershift.
  const control = onLayer(selected, layer);
  const onHypershift = layer === "hypershift";
  const binding = profile.bindings[selected];
  const entry = bindingOf(profile, control);
  const entryLabel = onHypershift ? profile.hypershift.bindings[selected]?.label : binding?.label;
  const secondary = layerSecondary(profile, selected, layer);
  const isKey = /^k\d\d$/.test(selected);
  const isHypershiftKey = profile.hypershift.key === selected;
  const actuation = draft ?? layerMm(profile, selected, layer, default_mm);

  if (sub === "choose") {
    return (
      <div style={{ height: PAGE_HEIGHT }}>
        <ChoosePage control={control} state={state} profile={profile} onChanged={onChanged} onDone={() => setSub(null)} />
      </div>
    );
  }
  if (sub === "secondary") {
    return (
      <div style={{ height: PAGE_HEIGHT }}>
        <SecondaryPage control={control} state={state} profile={profile} onChanged={onChanged} onBack={() => setSub(null)} />
      </div>
    );
  }

  return (
    // The drawing takes the full page height; the Editing row sits above the card.
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      <Keypad profile={profile} view="bindings" layer={layer} selected={[selected]} defaultMm={default_mm} {...glow} leds={profile.leds} onSelect={onSelect} />
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        <EditingRow state={state} profile={profile} onView={onView} />
        <LayerSwitch layer={layer} onChange={onLayerChange} />
        <Card title={controlTitle(selected)}>
          {onHypershift && profile.hypershift.key === null && (
            <div style={{ fontSize: 13, opacity: 0.7, marginBottom: 6 }}>
              No Hypershift key yet. On Standard, pick a key's Choose… → Hypershift.
            </div>
          )}
          {onHypershift && isHypershiftKey ? (
            <div>{controlTitle(selected)} is the Hypershift key. Hold it to use this layer.</div>
          ) : (
            <>
              <Row
                label={
                  <>
                    Binding:{" "}
                    {onHypershift && !entry ? (
                      <>
                        <b>Same as Standard</b> ({binding?.label})
                      </>
                    ) : (
                      <b style={onHypershift ? { color: HYPERSHIFT_ACCENT } : undefined}>{entryLabel}</b>
                    )}
                  </>
                }
              >
                <DialogButton style={BUTTON} onClick={() => setSub("choose")}>
                  Choose…
                </DialogButton>
                <RecordButton control={control} profile={profile} onChanged={onChanged} onError={setCardError} />
              </Row>
              {onHypershift && hasEntry(profile, control) && (
                <Row label="Hypershift binding">
                  <DialogButton style={BUTTON} onClick={clearEntry}>
                    Clear
                  </DialogButton>
                </Row>
              )}
              {!onHypershift && binding?.factory && (
                <Row label={`Factory default (${binding.factory})`}>
                  <DialogButton style={BUTTON} onClick={() => reset(binding.factory)}>
                    Reset
                  </DialogButton>
                </Row>
              )}
              {isKey && (!onHypershift || entry) && (
                <Row label={`Actuation: ${mmText(actuation)}`} stacked>
                  <SliderField value={actuation} min={min_mm} max={max_mm} step={0.1} bottomSeparator="none" onChange={changeActuation} />
                </Row>
              )}
              {isKey && !isHypershiftKey && (!onHypershift || entry) && (
                <Row label="Secondary function">
                  <DialogButton style={BUTTON} onClick={() => setSub("secondary")}>
                    {secondary ? `${secondary.label} · ${mmText(secondary.actuation)} ›` : "Off ›"}
                  </DialogButton>
                </Row>
              )}
            </>
          )}
          {selected.startsWith("dpad_") && (
            <Row label="8-way D-pad">
              <Toggle value={profile.dpad_mode === "8way"} onChange={onDpad} />
            </Row>
          )}
          {isKey && !(onHypershift && isHypershiftKey) && actuationNote(state) && (
            <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>{actuationNote(state)}</div>
          )}
          {cardError && <div style={{ color: ERROR, marginTop: 4 }}>{cardError}</div>}
          {error && <div style={{ color: ERROR, marginTop: 4 }}>{error}</div>}
        </Card>
      </Focusable>
    </Focusable>
  );
}
