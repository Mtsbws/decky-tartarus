import { callable } from "@decky/api";

export type BindingDict = {
  type: string;
  keys?: string[];
  steps?: string[][];
  action?: string;
};

export type ControlState = { binding: BindingDict; label: string; factory: string };

export type LightingState = { effect: string; color: string; brightness: number; enabled: boolean };

export type ActuationState = {
  enabled: boolean;
  status: "on" | "off" | "unavailable" | null;
  default_mm: number;
  min_mm: number;
  max_mm: number;
  min_gap_mm: number;
};

// Key kNN's B, at a deeper actuation point. Its binding is set as control "kNN.b".
export type SecondaryState = { binding: BindingDict; label: string; actuation: number };

export type ProfileState = {
  id: string;
  name: string;
  is_default: boolean;
  games: string[];
  dpad_mode: "4way" | "8way";
  leds: [boolean, boolean, boolean];
  actuation: Record<string, number>;
  secondary: Record<string, SecondaryState>;
  bindings: Record<string, ControlState>;
};

export type RunningApp = { app_id: number; name: string };

export type State = {
  connected: boolean;
  device: string | null;
  device_id: string | null;
  steam_mode: string;
  lighting: LightingState;
  actuation: ActuationState;
  effects: string[];
  active_profile: string;
  running_app: RunningApp | null;
  max_profiles: number;
  profiles: ProfileState[];
  led_patterns: boolean[][];
};

// The backend raises ValueError on bad input; the callable rejects with its message.
export function errorText(e: unknown): string {
  const text = e instanceof Error ? e.message : String(e);
  return text.replace(/^[\s\S]*ValueError:\s*/, "").trim() || "Rejected";
}

export const profileById = (state: State, id: string) => state.profiles.find((p) => p.id === id);

// The backend keeps active_profile pointing at an existing profile.
export const activeProfile = (state: State): ProfileState => profileById(state, state.active_profile) ?? state.profiles[0];

export type SetTextResult = { ok: boolean; error: string | null; state: State };

export const getState = callable<[], State>("get_state");
export const setBinding = callable<[profileId: string, control: string, binding: BindingDict], State>("set_binding");
export const setBindingText = callable<[profileId: string, control: string, text: string], SetTextResult>("set_binding_text");
export const setDpadMode = callable<[profileId: string, mode: "4way" | "8way"], State>("set_dpad_mode");
export const setRunningApp = callable<[appId: number | null, name: string | null], State>("set_running_app");
export const assignRunningGame = callable<[profileId: string], State>("assign_running_game");
export const createProfile = callable<[name: string, copyFromId: string], State>("create_profile");
export const renameProfile = callable<[profileId: string, name: string], State>("rename_profile");
export const deleteProfile = callable<[profileId: string], State>("delete_profile");
export const setLighting = callable<[effect: string, color: string, brightness: number], State>("set_lighting");
export const setLightingEnabled = callable<[enabled: boolean], State>("set_lighting_enabled");
export const setActuation = callable<[profileId: string, control: string, mm: number], State>("set_actuation");
export const setActuationKeys = callable<[profileId: string, controls: string[], mm: number], State>("set_actuation_keys");
export const setSecondary = callable<[profileId: string, control: string, mm: number | null], State>("set_secondary");
export const setLeds = callable<[profileId: string, leds: boolean[]], State>("set_leds");
export const recordStart = callable<[], void>("record_start");
export const recordCancel = callable<[], void>("record_cancel");

export const EV_STEAM_ACTION = "steam_action";
export const EV_STATE = "state_changed";
export const EV_RECORD = "record_result";
