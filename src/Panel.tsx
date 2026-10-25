import { ButtonItem, DropdownItem, Navigation, PanelSection, PanelSectionRow, SliderField, TextField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useRef, useState } from "react";

import { EV_STATE, getState, LightingState, setLighting, State } from "./api";

export const EDITOR_ROUTE = "/decky-tartarus/editor";

// Effects that send no colour to the keypad (spike findings: spectrum and wave).
const COLOURLESS = new Set(["spectrum", "wave"]);
const DEBOUNCE_MS = 250;

// The backend raises ValueError on bad input; the callable rejects with its message.
export function errorText(e: unknown): string {
  const text = e instanceof Error ? e.message : String(e);
  return text.replace(/^[\s\S]*ValueError:\s*/, "").trim() || "Rejected";
}

export function Panel() {
  const [state, setState] = useState<State | null>(null);
  const [draft, setDraft] = useState<LightingState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    getState().then((s) => {
      setState(s);
      setDraft(s.lighting);
    });
    const listener = addEventListener<[State]>(EV_STATE, setState);
    return () => {
      removeEventListener(EV_STATE, listener);
      window.clearTimeout(timer.current);
    };
  }, []);

  function change(patch: Partial<LightingState>) {
    if (!draft) return;
    const next = { ...draft, ...patch };
    setDraft(next);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setLighting(next.effect, next.color, next.brightness)
        .then((s) => {
          setState(s);
          setError(null);
        })
        .catch((e) => setError(errorText(e)));
    }, DEBOUNCE_MS);
  }

  function openEditor() {
    Navigation.Navigate(EDITOR_ROUTE);
    Navigation.CloseSideMenus();
  }

  return (
    <>
      <PanelSection title="Keypad">
        <PanelSectionRow>
          <div style={{ color: state?.connected ? "#5ba32b" : "#b8bcbf" }}>
            {state === null ? "Loading…" : state.connected ? "Connected" : "Not connected"}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={openEditor}>
            Edit keys
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      {state && draft && state.effects.length > 0 && (
        <PanelSection title="Lighting">
          <PanelSectionRow>
            <DropdownItem
              label="Effect"
              rgOptions={state.effects.map((e) => ({ data: e, label: e[0].toUpperCase() + e.slice(1) }))}
              selectedOption={draft.effect}
              onChange={(o) => change({ effect: o.data })}
            />
          </PanelSectionRow>
          {!COLOURLESS.has(draft.effect) && (
            <PanelSectionRow>
              <TextField
                label="Colour (#rrggbb)"
                value={draft.color}
                onChange={(e) => change({ color: e.target.value })}
              />
            </PanelSectionRow>
          )}
          <PanelSectionRow>
            <SliderField
              label="Brightness"
              value={draft.brightness}
              min={0}
              max={100}
              step={5}
              showValue
              valueSuffix="%"
              onChange={(v) => change({ brightness: v })}
            />
          </PanelSectionRow>
          {error && (
            <PanelSectionRow>
              <div style={{ color: "#e05050" }}>Not applied: {error}</div>
            </PanelSectionRow>
          )}
        </PanelSection>
      )}
    </>
  );
}
