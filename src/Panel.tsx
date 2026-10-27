import { ButtonItem, DropdownItem, Navigation, PanelSection, PanelSectionRow, ToggleField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { activeProfile, assignRunningGame, errorText, EV_STATE, getState, setAdjustableActuation, State } from "./api";
import { LightingControls } from "./LightingControls";
import { syncLighting } from "./lighting";

export const EDITOR_ROUTE = "/decky-tartarus/editor";

// Errors live out here: Steam remounts the whole panel each time a dropdown menu opens.
let assignError: string | null = null;
let actuationError: string | null = null;
const listeners = new Set<() => void>();

function publish() {
  listeners.forEach((l) => l());
}

// The switch shows the backend's value; the state event after the call updates it.
function switchActuation(enabled: boolean) {
  setAdjustableActuation(enabled)
    .then(() => (actuationError = null))
    .catch((e) => (actuationError = errorText(e)))
    .finally(publish);
}

const ACTUATION_NOTES: Record<string, string> = {
  unavailable: "Adjustable actuation unavailable: keys fire at the fixed hardware point.",
  off: "Keys fire at the fixed hardware point.",
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
      syncLighting(s);
    });
    const stateListener = addEventListener<[State]>(EV_STATE, (s) => {
      setState(s);
      syncLighting(s);
    });
    return () => {
      listeners.delete(listener);
      removeEventListener(EV_STATE, stateListener);
    };
  }, []);

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
              label="Adjustable actuation"
              description={state.connected && state.actuation.status ? ACTUATION_NOTES[state.actuation.status] : undefined}
              checked={state.actuation.enabled}
              onChange={switchActuation}
            />
            {actuationError && <div style={{ color: "#e05050" }}>{actuationError}</div>}
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
      {state && state.effects.length > 0 && (
        <PanelSection title="Lighting">
          <LightingControls effects={state.effects} collapsible />
        </PanelSection>
      )}
    </>
  );
}
