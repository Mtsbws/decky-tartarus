import { DialogButton, Focusable, ModalRoot } from "@decky/ui";
import { useState } from "react";

import { errorText, ProfileState, setLeds, State } from "../api";
import { StatusLights } from "../StatusLights";
import { ERROR } from "./layout";

const ledKey = (leds: readonly boolean[]) => leds.map((on) => (on ? "1" : "0")).join("");

// Every status-light pattern in colour; one another profile uses shows its name and can't be picked.
export function LightsModal({ state, profile, onChanged, closeModal }: {
  state: State;
  profile: ProfileState;
  onChanged(s: State): void;
  closeModal?(): void;
}) {
  const [error, setError] = useState<string | null>(null);

  function pick(leds: boolean[]) {
    setLeds(profile.id, leds)
      .then((s) => {
        onChanged(s);
        closeModal?.();
      })
      .catch((e) => setError(errorText(e)));
  }

  return (
    <ModalRoot onCancel={closeModal}>
      <div style={{ fontSize: 18, fontWeight: "bold", marginBottom: 12 }}>Lights for {profile.name}</div>
      <Focusable flow-children="row" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {state.led_patterns.map((leds) => {
          const key = ledKey(leds);
          const current = key === ledKey(profile.leds);
          const owner = current ? undefined : state.profiles.find((p) => ledKey(p.leds) === key);
          return (
            <DialogButton
              key={key}
              disabled={owner !== undefined}
              onClick={() => (current ? closeModal?.() : pick(leds))}
              style={{
                width: 96,
                minWidth: 0,
                height: 96,
                padding: 8,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <StatusLights leds={leds} size={14} />
              <div style={{ fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" }}>
                {current ? "Current" : owner ? owner.name : "Free"}
              </div>
            </DialogButton>
          );
        })}
      </Focusable>
      {error && <div style={{ color: ERROR, marginTop: 8 }}>{error}</div>}
    </ModalRoot>
  );
}
