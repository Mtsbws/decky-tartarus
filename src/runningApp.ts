import { Router } from "@decky/ui";

import { setRunningApp } from "./api";

const POLL_MS = 2000;

// Reports on every poll, even when unchanged: the backend ignores repeats, and
// this also re-syncs it after a backend restart.
export function startRunningAppPoll(): () => void {
  const poll = () => {
    const app = (Router as any).MainRunningApp;
    const report = app ? setRunningApp(Number(app.appid) >>> 0, app.display_name ?? null) : setRunningApp(null, null);
    report.catch((e) => console.warn("Tartarus: reporting the running app failed", e));
  };
  poll();
  const timer = setInterval(poll, POLL_MS);
  return () => clearInterval(timer);
}
