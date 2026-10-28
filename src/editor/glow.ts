import { ProfileState, State } from "../api";
import { useLighting } from "../lighting";
import { COLOURLESS } from "../LightingControls";
import { Glow, rainbow } from "./Keypad";
import { Layer } from "./layers";

// What the keypad lights for this profile and layer, for the drawing on every page:
// the backlight on Standard, the Hypershift lights on Hypershift (as while the key is held).
// Follows the lighting draft, so an edit shows before it reaches the keypad.
export function useKeypadGlow(state: State, profile: ProfileState, layer: Layer): { glow: Glow; glowLevel: number } {
  const backlight = useLighting().draft ?? state.lighting;
  const { enabled: hsEnabled, color: hsColor } = state.lighting.hypershift;
  const glowLevel = 0.2 + (0.8 * backlight.brightness) / 100;

  if (!backlight.enabled) return { glow: () => null, glowLevel };
  if (layer === "hypershift") {
    const lit = new Set(Object.keys(profile.hypershift.bindings));
    if (profile.hypershift.key) lit.add(profile.hypershift.key);
    return { glow: (c) => (hsEnabled && lit.has(c) ? hsColor : null), glowLevel };
  }
  if (COLOURLESS.has(backlight.effect)) return { glow: rainbow, glowLevel };
  return { glow: () => backlight.color, glowLevel };
}
