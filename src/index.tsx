import { PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener } from "@decky/api";
import { FaKeyboard } from "react-icons/fa";

import { EV_STEAM_ACTION } from "./api";
import { openSteamAction, SteamAction } from "./steamActions";

function Content() {
  return (
    <PanelSection title="Keypad">
      <PanelSectionRow>Coming soon</PanelSectionRow>
    </PanelSection>
  );
}

export default definePlugin(() => {
  const steamListener = addEventListener<[action: SteamAction]>(EV_STEAM_ACTION, openSteamAction);

  return {
    name: "Decky Tartarus",
    titleView: <div className={staticClasses.Title}>Tartarus</div>,
    content: <Content />,
    icon: <FaKeyboard />,
    onDismount() {
      removeEventListener(EV_STEAM_ACTION, steamListener);
    },
  };
});
