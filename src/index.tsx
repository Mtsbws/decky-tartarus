import { DialogButton, Focusable, staticClasses } from "@decky/ui";
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
      // Laid out like CSS Loader's title: name on the left, a 40×28 button on the right.
      <Focusable
        className={staticClasses.Title}
        style={{ display: "flex", alignItems: "center", width: "100%", padding: 0, boxShadow: "none" }}
      >
        <div style={{ marginRight: "auto" }}>Tartarus</div>
        <DialogButton style={{ height: 28, width: 40, minWidth: 0, padding: "10px 12px" }} onClick={openEditor}>
          <FaCog style={{ marginTop: -4, display: "block" }} />
        </DialogButton>
      </Focusable>
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
