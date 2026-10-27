import { DialogButton, staticClasses } from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener, routerHook } from "@decky/api";
import { FaCog, FaKeyboard } from "react-icons/fa";

import { EV_STEAM_ACTION } from "./api";
import { Editor } from "./editor/Editor";
import { EDITOR_ROUTE, openEditor, Panel } from "./Panel";
import { startRunningAppPoll } from "./runningApp";
import { openSteamAction, SteamAction } from "./steamActions";

export default definePlugin(() => {
  const steamListener = addEventListener<[action: SteamAction]>(EV_STEAM_ACTION, openSteamAction);
  routerHook.addRoute(EDITOR_ROUTE, Editor, { exact: true });
  const stopPoll = startRunningAppPoll();

  return {
    name: "Decky Tartarus",
    titleView: (
      <div className={staticClasses.Title} style={{ display: "flex", alignItems: "center", width: "100%" }}>
        Tartarus
        <DialogButton
          style={{ marginLeft: "auto", width: 28, height: 28, minWidth: 0, padding: 0 }}
          onClick={openEditor}
        >
          <FaCog />
        </DialogButton>
      </div>
    ),
    content: <Panel />,
    icon: <FaKeyboard />,
    onDismount() {
      removeEventListener(EV_STEAM_ACTION, steamListener);
      stopPoll();
      routerHook.removeRoute(EDITOR_ROUTE);
    },
  };
});
