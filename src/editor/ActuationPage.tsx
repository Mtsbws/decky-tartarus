import { DialogButton, Focusable, SliderField } from "@decky/ui";
import { useEffect, useState } from "react";

import { errorText, ProfileState, setActuationKeys, State } from "../api";
import { Card, Row } from "./Card";
import { EditingRow } from "./EditingRow";
import { Keypad } from "./Keypad";
import { hasEntry, Layer, layerMm, onLayer as onLayerName } from "./layers";
import { LayerSwitch } from "./LayerSwitch";
import { actuationNote, BUTTON, ERROR, mmText, PAGE_HEIGHT, tenth } from "./layout";

const KEYS = Array.from({ length: 20 }, (_, i) => `k${String(i + 1).padStart(2, "0")}`);

export function ActuationPage({ state, profile, layer, onLayer, onView, onChanged }: {
  state: State;
  profile: ProfileState;
  layer: Layer;
  onLayer(l: Layer): void;
  onView(id: string): void;
  onChanged(s: State): void;
}) {
  const { default_mm, min_mm, max_mm } = state.actuation;
  const [selection, setSelection] = useState<string[]>([]);
  const [value, setValue] = useState(default_mm);
  const [error, setError] = useState<string | null>(null);

  const onHypershift = layer === "hypershift";
  // On the Hypershift layer only keys with an entry can be edited; a depth never creates an entry.
  const editable = onHypershift ? KEYS.filter((c) => hasEntry(profile, onLayerName(c, layer))) : KEYS;

  const keyMm = (p: ProfileState, c: string) => layerMm(p, c, layer, default_mm);

  // The slider starts at the first selected key's value when the selection goes from empty to
  // non-empty and when the edited profile changes; adding or removing keys leaves it where it is.
  useEffect(() => {
    if (selection.length > 0) setValue(keyMm(profile, selection[0]));
    setError(null);
  }, [profile.id]);

  // Switching layer starts a fresh selection: the other layer's keys may not be editable here.
  function changeLayer(l: Layer) {
    setSelection([]);
    setError(null);
    onLayer(l);
  }

  function changeSelection(next: string[]) {
    if (selection.length === 0 && next.length > 0) setValue(keyMm(profile, next[0]));
    setSelection(next);
    setError(null);
  }

  function toggle(c: string) {
    changeSelection(selection.includes(c) ? selection.filter((k) => k !== c) : [...selection, c]);
  }

  function apply() {
    setActuationKeys(
      profile.id,
      selection.map((c) => onLayerName(c, layer)),
      value,
    )
      .then((s) => {
        setError(null);
        onChanged(s);
      })
      .catch((e) => setError(errorText(e)));
  }

  const n = selection.length;
  const note = actuationNote(state);

  return (
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      <Keypad profile={profile} view="actuation" layer={layer} selected={selection} defaultMm={default_mm} onSelect={toggle} />
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        <EditingRow state={state} profile={profile} onView={onView} />
        <LayerSwitch layer={layer} onChange={changeLayer} />
        <Card title={`Actuation · ${n} ${n === 1 ? "key" : "keys"} selected`}>
          <div style={{ fontSize: 13, opacity: 0.7 }}>
            {onHypershift && editable.length === 0
              ? "No keys have a Hypershift binding yet."
              : "Press depth that triggers the key."}
          </div>
          <Row label={`Depth: ${mmText(value)}`} stacked>
            <SliderField value={value} min={min_mm} max={max_mm} step={0.1} bottomSeparator="none" onChange={(v) => setValue(tenth(v))} />
          </Row>
          <Focusable flow-children="row" style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <DialogButton style={BUTTON} disabled={editable.length === 0} onClick={() => changeSelection(editable)}>
              Select all
            </DialogButton>
            <DialogButton style={BUTTON} onClick={() => changeSelection([])}>
              Clear
            </DialogButton>
            <DialogButton style={BUTTON} disabled={n === 0 || editable.length === 0} onClick={apply}>
              Apply to selected
            </DialogButton>
          </Focusable>
          {error && <div style={{ color: ERROR, marginTop: 4 }}>{error}</div>}
          {note && <div style={{ fontSize: 12, opacity: 0.7, marginTop: 6 }}>{note}</div>}
        </Card>
      </Focusable>
    </Focusable>
  );
}
