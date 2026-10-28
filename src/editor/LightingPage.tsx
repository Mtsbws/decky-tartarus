import { Dropdown, Focusable, SliderField, Toggle } from "@decky/ui";
import { useState } from "react";

import { activeProfile, errorText, setHypershiftLights, State } from "../api";
import { ColourDropdown } from "../ColourField";
import { useLighting } from "../lighting";
import { capitalise, COLOURLESS } from "../LightingControls";
import { Card, Row } from "./Card";
import { Glow, Keypad, rainbow } from "./Keypad";
import { Layer } from "./layers";
import { LayerSwitch } from "./LayerSwitch";
import { ERROR, PAGE_HEIGHT } from "./layout";

const NOTE = { fontSize: 13, opacity: 0.7 };

// Lighting is the keypad's, not a profile's, so there is no Editing row. The drawing shows what the
// keypad lights: the backlight on Standard, the Hypershift lights on Hypershift.
export function LightingPage({ state, layer, onLayer, onChanged }: {
  state: State;
  layer: Layer;
  onLayer(l: Layer): void;
  onChanged(s: State): void;
}) {
  const { draft, error, change, setEnabled } = useLighting();
  const [hsError, setHsError] = useState<string | null>(null);
  const backlight = draft ?? state.lighting;
  const { enabled: hsEnabled, color: hsColor } = state.lighting.hypershift;
  // The keypad lights the Hypershift keys of the profile in use.
  const profile = activeProfile(state);
  const onHypershift = layer === "hypershift";

  // The backlight's colour can't double as the Hypershift colour, or the lit keys wouldn't stand out.
  const taken = COLOURLESS.has(backlight.effect) ? undefined : backlight.color.toLowerCase();

  function writeHypershift(nextEnabled: boolean, nextColor: string) {
    setHsError(null);
    setHypershiftLights(nextEnabled, nextColor)
      .then(onChanged)
      .catch((e) => setHsError(errorText(e)));
  }

  const lit = new Set(Object.keys(profile.hypershift.bindings));
  if (profile.hypershift.key) lit.add(profile.hypershift.key);
  let glow: Glow;
  if (!backlight.enabled) glow = () => null;
  else if (onHypershift) glow = (c) => (hsEnabled && lit.has(c) ? hsColor : null);
  else if (COLOURLESS.has(backlight.effect)) glow = rainbow;
  else glow = () => backlight.color;

  return (
    <Focusable flow-children="row" style={{ height: PAGE_HEIGHT, display: "flex", gap: 16 }}>
      <Keypad
        profile={profile}
        view="preview"
        layer={layer}
        glow={glow}
        glowLevel={0.2 + (0.8 * backlight.brightness) / 100}
      />
      <Focusable flow-children="column" style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 8 }}>
        <LayerSwitch layer={layer} onChange={onLayer} />
        {!onHypershift ? (
          <Card title="Backlight">
            <Row label="Lighting">
              <Toggle value={backlight.enabled} onChange={setEnabled} />
            </Row>
            {backlight.enabled && (
              <>
                <Row label="Mode">
                  <div style={{ minWidth: 160 }}>
                    <Dropdown
                      rgOptions={state.effects.map((e) => ({ data: e, label: capitalise(e) }))}
                      selectedOption={backlight.effect}
                      onChange={(o) => change({ effect: o.data })}
                    />
                  </div>
                </Row>
                {!COLOURLESS.has(backlight.effect) && (
                  <Row label="Colour">
                    <div style={{ minWidth: 160 }}>
                      <ColourDropdown color={backlight.color} onChange={(color) => change({ color })} />
                    </div>
                  </Row>
                )}
                <Row label={`Brightness: ${backlight.brightness}%`} stacked>
                  <SliderField
                    value={backlight.brightness}
                    min={0}
                    max={100}
                    step={5}
                    bottomSeparator="none"
                    onChange={(v) => change({ brightness: v })}
                  />
                </Row>
              </>
            )}
            {error && <div style={{ color: ERROR, marginTop: 4 }}>Not applied: {error}</div>}
          </Card>
        ) : (
          <Card title="Hypershift lights">
            <div style={NOTE}>
              While the Hypershift key is held, the keys with a Hypershift binding in {profile.name} light up.
            </div>
            <Row label="Hypershift lights">
              <Toggle value={hsEnabled} onChange={(v) => writeHypershift(v, hsColor)} />
            </Row>
            {hsEnabled && (
              <Row label="Colour">
                <div style={{ minWidth: 160 }}>
                  <ColourDropdown color={hsColor} exclude={taken} onChange={(c) => writeHypershift(hsEnabled, c)} />
                </div>
              </Row>
            )}
            {hsEnabled && hsColor.toLowerCase() === taken && (
              <div style={{ color: ERROR, marginTop: 4 }}>This is also the backlight colour. Pick another one so the keys stand out.</div>
            )}
            {hsError && <div style={{ color: ERROR, marginTop: 4 }}>Not applied: {hsError}</div>}
            {!backlight.enabled && <div style={{ ...NOTE, marginTop: 6 }}>Lighting is off, so Hypershift lights stay off.</div>}
            {hsEnabled && profile.hypershift.key === null && (
              <div style={{ ...NOTE, marginTop: 6 }}>{profile.name} has no Hypershift key yet.</div>
            )}
          </Card>
        )}
      </Focusable>
    </Focusable>
  );
}
