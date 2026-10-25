import { ButtonItem, DropdownItem, Focusable, Navigation, PanelSection, PanelSectionRow, SliderField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { EV_STATE, getState, LightingState, setLighting, State } from "./api";

export const EDITOR_ROUTE = "/decky-tartarus/editor";

// Effects that send no colour to the keypad (spike findings: spectrum and wave).
const COLOURLESS = new Set(["spectrum", "wave"]);
const DEBOUNCE_MS = 250;
const SWATCHES = [
  "#ff0000", "#ff6000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#8000ff", "#ff00ff", "#ffffff",
];

// The backend raises ValueError on bad input; the callable rejects with its message.
export function errorText(e: unknown): string {
  const text = e instanceof Error ? e.message : String(e);
  return text.replace(/^[\s\S]*ValueError:\s*/, "").trim() || "Rejected";
}

// Steam remounts the whole panel each time a dropdown menu opens, and the pick
// arrives in the old instance. The lighting draft lives out here so the mounted
// panel sees it.
let lighting: LightingState | null = null;
let lightingError: string | null = null;
let timer: number | undefined;
let writing = 0;
const listeners = new Set<() => void>();

function publish() {
  listeners.forEach((l) => l());
}

function changeLighting(patch: Partial<LightingState>) {
  if (!lighting) return;
  const next = { ...lighting, ...patch };
  lighting = next;
  publish();
  window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    timer = undefined;
    writing++;
    setLighting(next.effect, next.color, next.brightness)
      .then(() => (lightingError = null))
      .catch((e) => (lightingError = errorText(e)))
      .finally(() => {
        writing--;
        publish();
      });
  }, DEBOUNCE_MS);
}

export function Panel() {
  const [state, setState] = useState<State | null>(null);
  const [, rerender] = useState(0);

  useEffect(() => {
    const listener = () => rerender((n) => n + 1);
    listeners.add(listener);
    getState().then((s) => {
      setState(s);
      if (timer === undefined && writing === 0) lighting = s.lighting; // a pending edit is newer
      publish();
    });
    const stateListener = addEventListener<[State]>(EV_STATE, setState);
    return () => {
      listeners.delete(listener);
      removeEventListener(EV_STATE, stateListener);
    };
  }, []);

  const draft = lighting;
  const error = lightingError;
  const change = changeLighting;

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
              <Focusable flow-children="horizontal" style={{ display: "flex", justifyContent: "space-between" }}>
                {SWATCHES.map((c) => (
                  <Focusable
                    key={c}
                    onActivate={() => change({ color: c })}
                    onClick={() => change({ color: c })}
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 4,
                      background: c,
                      cursor: "pointer",
                      outline: draft.color.toLowerCase() === c ? "2px solid #dfe3e6" : "none",
                      outlineOffset: 2,
                    }}
                  >
                    {null}
                  </Focusable>
                ))}
              </Focusable>
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
