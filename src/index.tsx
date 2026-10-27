import { staticClasses } from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener, routerHook } from "@decky/api";
import { FaKeyboard } from "react-icons/fa";

import { EV_STEAM_ACTION } from "./api";
import { Editor } from "./editor/Editor";
import { EDITOR_ROUTE, Panel } from "./Panel";
import { startRunningAppPoll } from "./runningApp";
import { openSteamAction, SteamAction } from "./steamActions";

export default definePlugin(() => {
  const steamListener = addEventListener<[action: SteamAction]>(EV_STEAM_ACTION, openSteamAction);
  routerHook.addRoute(EDITOR_ROUTE, Editor, { exact: true });
  const stopPoll = startRunningAppPoll();

  return {
    name: "Decky Tartarus",
    titleView: <div className={staticClasses.Title}>Tartarus</div>,
    content: <Panel />,
    icon: <FaKeyboard />,
    onDismount() {
      removeEventListener(EV_STEAM_ACTION, steamListener);
      stopPoll();
      routerHook.removeRoute(EDITOR_ROUTE);
    },
  };
});
