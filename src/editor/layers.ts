import type { BindingDict, ProfileState, SecondaryState } from "../api";

export type Layer = "standard" | "hypershift";

export const HYPERSHIFT_ACCENT = "#ff6000";

// The controls that can be the Hypershift key: keys 01-20 and the top button, never the wheel or thumbpad.
export const HYPERSHIFT_KEYS: string[] = [
  ...Array.from({ length: 20 }, (_, i) => `k${String(i + 1).padStart(2, "0")}`),
  "top_button",
];

// "k05" -> "k05.h", "k05.b" -> "k05.h.b"; the standard layer leaves the name alone.
export function onLayer(control: string, layer: Layer): string {
  if (layer === "standard") return control;
  const [base, ...suffix] = control.split(".");
  return [base, "h", ...suffix.filter((s) => s === "b")].join(".");
}

// "k05.h.b" -> "k05": the plain control, without layer or secondary suffix.
export function baseControl(control: string): string {
  return control.split(".")[0];
}

// The binding for X, X.b, X.h or X.h.b.
export function bindingOf(p: ProfileState, control: string): BindingDict | undefined {
  const [base, ...suffix] = control.split(".");
  const rest = suffix.join(".");
  switch (rest) {
    case "":
      return p.bindings[base]?.binding;
    case "b":
      return p.secondary[base]?.binding;
    case "h":
      return p.hypershift.bindings[base]?.binding;
    case "h.b":
      return p.hypershift.secondary[base]?.binding;
    default:
      return undefined;
  }
}

export const hasEntry = (p: ProfileState, control: string): boolean => bindingOf(p, control) !== undefined;

// A key's actuation on a layer: its Hypershift entry's own point, else the standard one.
export function layerMm(p: ProfileState, key: string, layer: Layer, defaultMm: number): number {
  const standard = p.actuation[key] ?? defaultMm;
  return layer === "hypershift" ? (p.hypershift.actuation[key] ?? standard) : standard;
}

// The key's secondary function on a layer: the Hypershift entry's own on the layer, the standard one otherwise.
export function layerSecondary(p: ProfileState, key: string, layer: Layer): SecondaryState | undefined {
  return layer === "hypershift" ? p.hypershift.secondary[key] : p.secondary[key];
}
