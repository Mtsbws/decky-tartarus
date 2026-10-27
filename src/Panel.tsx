import { ButtonItem, DropdownItem, Focusable, Navigation, PanelSection, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { activeProfile, assignRunningGame, EV_STATE, getState, LightingState, setAnalog, setLighting, State } from "./api";

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
let assignError: string | null = null;
let analogError: string | null = null;
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

// The switch shows the backend's value; the state event after the call updates it.
function switchAnalog(enabled: boolean) {
  setAnalog(enabled)
    .then(() => (analogError = null))
    .catch((e) => (analogError = errorText(e)))
    .finally(publish);
}

const ANALOG_NOTES: Record<string, string> = {
  unavailable: "Analog keys unavailable: keys work at the fixed hardware point.",
  off: "Keys work at the fixed hardware point.",
};

function assignGame(profileId: string) {
  assignRunningGame(profileId)
    .then(() => (assignError = null))
    .catch((e) => (assignError = errorText(e)))
    .finally(publish);
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
  const profile = state ? activeProfile(state) : null;

  function openEditor() {
    Navigation.Navigate(EDITOR_ROUTE);
    Navigation.CloseSideMenus();
  }

  return (
    <>
      <PanelSection title="Keypad">
        <PanelSectionRow>
          <div style={{ color: state?.connected ? "#5ba32b" : "#b8bcbf" }}>
            {state === null ? "Loading…" : state.connected ? `${state.device ?? "Keypad"} connected` : "Not connected"}
            {state?.connected && state.device_id && (
              <div style={{ color: "#b8bcbf", fontSize: "12px" }}>USB ID {state.device_id}</div>
            )}
          </div>
        </PanelSectionRow>
        {state && profile && (
          <PanelSectionRow>
            <div>Layout: {profile.name}</div>
          </PanelSectionRow>
        )}
        {state && (
          <PanelSectionRow>
            <ToggleField
              label="Analog keys"
              description={state.connected && state.analog.status ? ANALOG_NOTES[state.analog.status] : undefined}
              checked={state.analog.enabled}
              onChange={switchAnalog}
            />
            {analogError && <div style={{ color: "#e05050" }}>{analogError}</div>}
          </PanelSectionRow>
        )}
        {state?.running_app && (
          <PanelSectionRow>
            <DropdownItem
              label={`${state.running_app.name} uses:`}
              rgOptions={state.profiles.map((p) => ({
                data: p.id,
                label: p.is_default ? `${p.name} (default)` : p.name,
              }))}
              selectedOption={state.active_profile}
              onChange={(o) => assignGame(o.data)}
            />
            {assignError && <div style={{ color: "#e05050" }}>{assignError}</div>}
          </PanelSectionRow>
        )}
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
