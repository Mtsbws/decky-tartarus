import { DropdownItem, Navigation, PanelSection, PanelSectionRow } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { activeProfile, assignRunningGame, errorText, EV_STATE, getState, State } from "./api";
import { LightingControls } from "./LightingControls";
import { syncLighting } from "./lighting";
import { StatusLights } from "./StatusLights";

export const EDITOR_ROUTE = "/decky-tartarus/editor";

// Errors live out here: Steam remounts the whole panel each time a dropdown menu opens.
let assignError: string | null = null;
const listeners = new Set<() => void>();

function publish() {
  listeners.forEach((l) => l());
}

function assignGame(profileId: string) {
  assignRunningGame(profileId)
    .then(() => (assignError = null))
    .catch((e) => (assignError = errorText(e)))
    .finally(publish);
}

export function openEditor() {
  Navigation.Navigate(EDITOR_ROUTE);
  Navigation.CloseSideMenus();
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

  return (
    <PanelSection>
      <PanelSectionRow>
        <div style={{ color: state?.connected ? "#5ba32b" : "#b8bcbf" }}>
          {state === null ? "Loading…" : state.connected ? `${state.device ?? "Keypad"} connected` : "Not connected"}
          {state?.connected && state.device_id && (
            <div style={{ color: "#b8bcbf", fontSize: "12px" }}>USB ID {state.device_id}</div>
          )}
        </div>
      </PanelSectionRow>
      {state?.running_app && (
        <PanelSectionRow>
          <DropdownItem
            label={`${state.running_app.name} uses:`}
            rgOptions={state.profiles.map((p) => ({
              data: p.id,
              label: (
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <StatusLights leds={p.leds} size={6} />
                  {p.is_default ? `${p.name} (default)` : p.name}
                </span>
              ),
            }))}
            selectedOption={state.active_profile}
            onChange={(o) => assignGame(o.data)}
          />
          {assignError && <div style={{ color: "#e05050" }}>{assignError}</div>}
        </PanelSectionRow>
      )}
      {state && profile && !state.running_app && (
        <PanelSectionRow>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <StatusLights leds={profile.leds} size={6} />
            Keypad uses {profile.name}
          </div>
        </PanelSectionRow>
      )}
      {state && state.effects.length > 0 && <LightingControls effects={state.effects} collapsible />}
    </PanelSection>
  );
}
