import { callable } from "@decky/api";

export type BindingDict = {
  type: string;
  keys?: string[];
  steps?: string[][];
  action?: string;
};

export type ControlState = { binding: BindingDict; label: string; factory: string };

export type LightingState = { effect: string; color: string; brightness: number };

export type ActuationState = {
  enabled: boolean;
  status: "on" | "off" | "unavailable" | null;
  default_mm: number;
  min_mm: number;
  max_mm: number;
  min_gap_mm: number;
};

export type ProfileState = {
  id: string;
  name: string;
  is_default: boolean;
  games: string[];
  dpad_mode: "4way" | "8way";
  leds: [boolean, boolean, boolean];
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
export const setAdjustableActuation = callable<[enabled: boolean], State>("set_adjustable_actuation");
export const setLeds = callable<[profileId: string, leds: boolean[]], State>("set_leds");
export const recordStart = callable<[], void>("record_start");
export const recordCancel = callable<[], void>("record_cancel");

export const EV_STEAM_ACTION = "steam_action";
export const EV_STATE = "state_changed";
export const EV_RECORD = "record_result";
