import { callable } from "@decky/api";

export type BindingDict = {
  type: string;
  keys?: string[];
  steps?: string[][];
  action?: string;
};

export type ControlState = { binding: BindingDict; label: string; factory: string };

export type LightingState = { effect: string; color: string; brightness: number };

export type State = {
  connected: boolean;
  device: string | null;
  device_id: string | null;
  dpad_mode: "4way" | "8way";
  steam_mode: string;
  bindings: Record<string, ControlState>;
  lighting: LightingState;
  effects: string[];
};

export type SetTextResult = { ok: boolean; error: string | null; state: State };

export const getState = callable<[], State>("get_state");
export const setBinding = callable<[control: string, binding: BindingDict], State>("set_binding");
export const setBindingText = callable<[control: string, text: string], SetTextResult>("set_binding_text");
export const setDpadMode = callable<[mode: "4way" | "8way"], State>("set_dpad_mode");
export const setLighting = callable<[effect: string, color: string, brightness: number], State>("set_lighting");
export const recordStart = callable<[], void>("record_start");
export const recordCancel = callable<[], void>("record_cancel");

export const EV_STEAM_ACTION = "steam_action";
export const EV_STATE = "state_changed";
export const EV_RECORD = "record_result";
