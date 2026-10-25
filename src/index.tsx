import { PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { definePlugin } from "@decky/api";
import { FaKeyboard } from "react-icons/fa";

function Content() {
  return (
    <PanelSection title="Keypad">
      <PanelSectionRow>Coming soon</PanelSectionRow>
    </PanelSection>
  );
}

export default definePlugin(() => {
  return {
    name: "Decky Tartarus",
    titleView: <div className={staticClasses.Title}>Tartarus</div>,
    content: <Content />,
    icon: <FaKeyboard />,
    onDismount() {},
  };
});
