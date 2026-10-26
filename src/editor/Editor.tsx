import { ToggleField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { EV_STATE, activeProfile, getState, profileById, setDpadMode, State } from "../api";
import { errorText } from "../Panel";
import { BindingPicker } from "./BindingPicker";
import { controlName, Keypad } from "./Keypad";
import { ProfileBar } from "./ProfileBar";

export function Editor() {
  const [state, setState] = useState<State | null>(null);
  const [selected, setSelected] = useState<string>("k01");
  const [error, setError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<string | null>(null);

  useEffect(() => {
    getState().then((s) => {
      setState(s);
      setViewing((v) => v ?? s.active_profile);
    });
    const listener = addEventListener<[State]>(EV_STATE, setState);
    return () => {
      removeEventListener(EV_STATE, listener);
    };
  }, []);

  // Falls back to the active profile when the viewed one was deleted.
  const viewedProfile = (s: State) => (viewing !== null && profileById(s, viewing)) || activeProfile(s);

  function toggleDpad(eight: boolean) {
    if (state === null) return;
    setDpadMode(viewedProfile(state).id, eight ? "8way" : "4way")
      .then((s) => {
        setState(s);
        setError(null);
        if (!eight && /^dpad_.*_/.test(selected)) setSelected("dpad_up");
      })
      .catch((e) => setError(errorText(e)));
  }

  function switchView(id: string) {
    setViewing(id);
    const p = state && profileById(state, id);
    if (p && p.dpad_mode === "4way" && /^dpad_.*_/.test(selected)) setSelected("dpad_up");
  }

  if (state === null) return <div style={{ marginTop: 40, padding: 16 }}>Loading…</div>;

  const profile = viewedProfile(state);

  return (
    <div style={{ marginTop: 40, height: "calc(100% - 40px)", display: "flex", gap: 16, padding: "8px 16px", boxSizing: "border-box" }}>
      <div style={{ flex: 3, minWidth: 0 }}>
        <ProfileBar state={state} viewing={profile.id} onView={switchView} onChanged={setState} />
        <Keypad profile={profile} selected={selected} onSelect={setSelected} />
        <ToggleField label="8-way D-pad" checked={profile.dpad_mode === "8way"} onChange={toggleDpad} />
        {error && <div style={{ color: "#e05050" }}>{error}</div>}
        {!state.connected && <div style={{ opacity: 0.7 }}>Keypad not connected: changes are saved and apply when it's plugged in.</div>}
      </div>
      <div style={{ flex: 2, minWidth: 0, overflowY: "auto" }}>
        <h3 style={{ margin: "0 0 8px" }}>
          Key {controlName(selected)}: {profile.bindings[selected]?.label}
        </h3>
        <BindingPicker control={selected} state={state} profile={profile} onChanged={setState} />
      </div>
    </div>
  );
}
