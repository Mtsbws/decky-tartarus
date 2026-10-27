import { useRef } from "react";

// One pending write at a time; a new value replaces it. flush() sends it now,
// so moving to another key or profile doesn't drop the last change.
export function useDebounce(ms: number) {
  const pending = useRef<{ timer: number; run(): void } | null>(null);
  const flush = () => {
    const p = pending.current;
    if (p === null) return;
    window.clearTimeout(p.timer);
    pending.current = null;
    p.run();
  };
  const schedule = (run: () => void) => {
    if (pending.current !== null) window.clearTimeout(pending.current.timer);
    const timer = window.setTimeout(() => {
      pending.current = null;
      run();
    }, ms);
    pending.current = { timer, run };
  };
  return { schedule, flush, isPending: () => pending.current !== null };
}
