import { ToggleField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { EV_STATE, getState, setDpadMode, State } from "../api";
import { errorText } from "../Panel";
import { BindingPicker } from "./BindingPicker";
import { controlName, Keypad } from "./Keypad";

export function Editor() {
  const [state, setState] = useState<State | null>(null);
  const [selected, setSelected] = useState<string>("k01");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getState().then(setState);
    const listener = addEventListener<[State]>(EV_STATE, setState);
    return () => {
      removeEventListener(EV_STATE, listener);
    };
  }, []);

  function toggleDpad(eight: boolean) {
    setDpadMode(eight ? "8way" : "4way")
      .then((s) => {
        setState(s);
        setError(null);
        if (!eight && /^dpad_.*_/.test(selected)) setSelected("dpad_up");
      })
      .catch((e) => setError(errorText(e)));
  }

  if (state === null) return <div style={{ marginTop: 40, padding: 16 }}>Loading…</div>;

  return (
    <div style={{ marginTop: 40, height: "calc(100% - 40px)", display: "flex", gap: 16, padding: "8px 16px", boxSizing: "border-box" }}>
      <div style={{ flex: 3, minWidth: 0 }}>
        <Keypad state={state} selected={selected} onSelect={setSelected} />
        <ToggleField label="8-way D-pad" checked={state.dpad_mode === "8way"} onChange={toggleDpad} />
        {error && <div style={{ color: "#e05050" }}>{error}</div>}
        {!state.connected && <div style={{ opacity: 0.7 }}>Keypad not connected: changes are saved and apply when it's plugged in.</div>}
      </div>
      <div style={{ flex: 2, minWidth: 0, overflowY: "auto" }}>
        <h3 style={{ margin: "0 0 8px" }}>
          Key {controlName(selected)}: {state.bindings[selected]?.label}
        </h3>
        <BindingPicker control={selected} state={state} onChanged={setState} />
      </div>
    </div>
  );
}
