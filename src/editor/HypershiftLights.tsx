import { PanelSectionRow, ToggleField } from "@decky/ui";
import { useState } from "react";

import { errorText, setHypershiftLights, State } from "../api";
import { ColourField } from "../ColourField";
import { useLighting } from "../lighting";
import { COLOURLESS } from "../LightingControls";

// Colour of the keys with a Hypershift binding while the Hypershift key is held. Writes go straight through, no debounce.
export function HypershiftLights({ state, onChanged }: { state: State; onChanged: (s: State) => void }) {
  const [error, setError] = useState<string | null>(null);
  const { enabled, color } = state.lighting.hypershift;
  // The backlight's colour can't double as the Hypershift colour, or the lit keys wouldn't stand out.
  const backlight = useLighting().draft ?? state.lighting;
  const taken = COLOURLESS.has(backlight.effect) ? undefined : backlight.color.toLowerCase();

  const write = (nextEnabled: boolean, nextColor: string) => {
    setError(null);
    setHypershiftLights(nextEnabled, nextColor)
      .then(onChanged)
      .catch((e) => setError(errorText(e)));
  };

  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Hypershift lights"
          description="Light the keys with a Hypershift binding while the Hypershift key is held."
          checked={enabled}
          onChange={(v) => write(v, color)}
        />
      </PanelSectionRow>
      {enabled && (
        <PanelSectionRow>
          <ColourField color={color} exclude={taken} onChange={(c) => write(enabled, c)} />
        </PanelSectionRow>
      )}
      {enabled && color.toLowerCase() === taken && (
        <PanelSectionRow>
          <div style={{ color: "#e05050" }}>This is also the backlight colour. Pick another one so the keys stand out.</div>
        </PanelSectionRow>
      )}
      {error && (
        <PanelSectionRow>
          <div style={{ color: "#e05050" }}>Not applied: {error}</div>
        </PanelSectionRow>
      )}
      {!state.lighting.enabled && (
        <PanelSectionRow>
          <div style={{ opacity: 0.6 }}>Lighting is off, so Hypershift lights stay off.</div>
        </PanelSectionRow>
      )}
    </>
  );
}
