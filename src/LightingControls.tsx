import { ButtonItem, DropdownItem, Focusable, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import { FaChevronDown, FaChevronUp } from "react-icons/fa";

import { useLighting } from "./lighting";

// Effects that send no colour to the keypad (spike findings: spectrum and wave).
const COLOURLESS = new Set(["spectrum", "wave"]);
const SWATCHES = [
  "#ff0000", "#ff6000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#8000ff", "#ff00ff", "#ffffff",
];

const capitalise = (s: string) => s[0].toUpperCase() + s.slice(1);

// The lighting rows shared by the Quick Access panel (collapsible) and the editor's Lighting page.
export function LightingControls({ effects, collapsible }: { effects: string[]; collapsible: boolean }) {
  const { draft, error, expanded, change, setEnabled, setExpanded } = useLighting();
  if (!draft) return null;
  const open = draft.enabled && (expanded || !collapsible);

  return (
    <>
      <PanelSectionRow>
        <ToggleField label="Lighting" checked={draft.enabled} onChange={setEnabled} />
      </PanelSectionRow>
      {draft.enabled && collapsible && (
        <PanelSectionRow>
          <ButtonItem
            layout="inline"
            label={`${capitalise(draft.effect)} · ${draft.brightness}%`}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <FaChevronUp /> : <FaChevronDown />}
          </ButtonItem>
        </PanelSectionRow>
      )}
      {open && (
        <PanelSectionRow>
          <DropdownItem
            label="Mode"
            rgOptions={effects.map((e) => ({ data: e, label: capitalise(e) }))}
            selectedOption={draft.effect}
            onChange={(o) => change({ effect: o.data })}
          />
        </PanelSectionRow>
      )}
      {open && !COLOURLESS.has(draft.effect) && (
        <PanelSectionRow>
          <Focusable flow-children="horizontal" style={{ display: "flex", justifyContent: "space-between" }}>
            {SWATCHES.map((c) => (
              <Focusable
                key={c}
                onActivate={() => change({ color: c })}
                onClick={() => change({ color: c })}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 4,
                  background: c,
                  cursor: "pointer",
                  outline: draft.color.toLowerCase() === c ? "2px solid #dfe3e6" : "none",
                  outlineOffset: 2,
                }}
              >
                {null}
              </Focusable>
            ))}
          </Focusable>
        </PanelSectionRow>
      )}
      {open && (
        <PanelSectionRow>
          <SliderField
            label="Brightness"
            value={draft.brightness}
            min={0}
            max={100}
            step={5}
            showValue
            valueSuffix="%"
            onChange={(v) => change({ brightness: v })}
          />
        </PanelSectionRow>
      )}
      {error && (
        <PanelSectionRow>
          <div style={{ color: "#e05050" }}>Not applied: {error}</div>
        </PanelSectionRow>
      )}
    </>
  );
}
