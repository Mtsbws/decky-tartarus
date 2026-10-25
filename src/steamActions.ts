import { Navigation, Router, SideMenu } from "@decky/ui";

export type SteamAction = "menu" | "qam";

// Toggle like the Deck's own buttons: a second press closes the menu (S3).
// MenuStore has circular fields, so never JSON.stringify it.
export function openSteamAction(action: SteamAction): void {
  const target = action === "menu" ? SideMenu.Main : SideMenu.QuickAccess;
  const open = (Router.WindowStore?.GamepadUIMainWindowInstance?.MenuStore as any)?.m_eOpenSideMenu;
  if (open === target) Navigation.CloseSideMenus();
  else if (action === "menu") Navigation.OpenSideMenu(SideMenu.Main);
  else Navigation.OpenQuickAccessMenu();
}
