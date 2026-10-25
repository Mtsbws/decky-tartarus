import { staticClasses } from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener } from "@decky/api";
import { FaKeyboard } from "react-icons/fa";

import { EV_STEAM_ACTION } from "./api";
import { Panel } from "./Panel";
import { openSteamAction, SteamAction } from "./steamActions";

export default definePlugin(() => {
  const steamListener = addEventListener<[action: SteamAction]>(EV_STEAM_ACTION, openSteamAction);

  return {
    name: "Decky Tartarus",
    titleView: <div className={staticClasses.Title}>Tartarus</div>,
    content: <Panel />,
    icon: <FaKeyboard />,
    onDismount() {
      removeEventListener(EV_STEAM_ACTION, steamListener);
    },
  };
});
