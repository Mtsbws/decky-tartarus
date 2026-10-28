import { Navigation, Router, SideMenu } from "@decky/ui";

export type SteamAction = "menu" | "qam" | "keyboard";

// Toggle like the Deck's own buttons: a second press closes the menu (S3).
// MenuStore has circular fields, so never JSON.stringify it.
export function openSteamAction(action: SteamAction): void {
  if (action === "keyboard") return toggleKeyboard();
  const target = action === "menu" ? SideMenu.Main : SideMenu.QuickAccess;
  const open = (Router.WindowStore?.GamepadUIMainWindowInstance?.MenuStore as any)?.m_eOpenSideMenu;
  if (open === target) Navigation.CloseSideMenus();
  else if (action === "menu") Navigation.OpenSideMenu(SideMenu.Main);
  else Navigation.OpenQuickAccessMenu();
}

// Steam's on-screen keyboard. steam://open/keyboard does nothing in Game Mode, so this
// goes through the window's keyboard manager (internal fields, like MenuStore above).
function toggleKeyboard(): void {
  const keyboard = (Router.WindowStore?.GamepadUIMainWindowInstance as any)?.VirtualKeyboardManager;
  if (keyboard?.m_bIsVirtualKeyboardShowing?.m_currentValue) keyboard.SetVirtualKeyboardHidden();
  else keyboard?.SetVirtualKeyboardVisible();
}
