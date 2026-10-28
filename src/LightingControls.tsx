import { ButtonItem, DropdownItem, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import { RiArrowDownSFill, RiArrowUpSFill } from "react-icons/ri";

import { ColourField } from "./ColourField";
import { useLighting } from "./lighting";

// Effects that send no colour to the keypad (spike findings: spectrum and wave).
export const COLOURLESS = new Set(["spectrum", "wave"]);

const capitalise = (s: string) => s[0].toUpperCase() + s.slice(1);

// A slim full-width bar under the toggle, as CSS Loader's themes have. Steam's
// ButtonItem nesting differs between client versions, hence the three selectors.
const COLLAPSE_CLASS = "Tartarus_CollapseButton";
const COLLAPSE_CSS = [3, 4, 5]
  .map((depth) => `.${COLLAPSE_CLASS} ${"> div ".repeat(depth)}> button { height: 10px !important; }`)
  .join("\n");
const CARET = { transform: "translate(0, -13px)", fontSize: "1.5em" };

// The lighting rows shared by the Quick Access panel (collapsible) and the editor's Lighting page.
export function LightingControls({ effects, collapsible }: { effects: string[]; collapsible: boolean }) {
  const { draft, error, expanded, change, setEnabled, setExpanded } = useLighting();
  if (!draft) return null;
  const open = draft.enabled && (expanded || !collapsible);

  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Lighting"
          description={draft.enabled && collapsible ? `${capitalise(draft.effect)} · ${draft.brightness}%` : undefined}
          bottomSeparator={draft.enabled && collapsible ? "none" : "standard"}
          checked={draft.enabled}
          onChange={setEnabled}
        />
      </PanelSectionRow>
      {draft.enabled && collapsible && (
        <div className={COLLAPSE_CLASS}>
          <style>{COLLAPSE_CSS}</style>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              bottomSeparator={expanded ? "none" : "standard"}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <RiArrowUpSFill style={CARET} /> : <RiArrowDownSFill style={CARET} />}
            </ButtonItem>
          </PanelSectionRow>
        </div>
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
          <ColourField color={draft.color} onChange={(color) => change({ color })} />
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
