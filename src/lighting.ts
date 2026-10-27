import { useEffect, useState } from "react";

import { errorText, getState, LightingState, setLighting, setLightingEnabled, State } from "./api";

const DEBOUNCE_MS = 250;

// Steam remounts the whole panel each time a dropdown menu opens, and the pick
// arrives in the old instance. The lighting draft lives out here so the mounted
// panel (and the editor's Lighting page) sees it.
let draft: LightingState | null = null;
let error: string | null = null;
let expanded = false;
let timer: number | undefined;
let writing = 0;
const listeners = new Set<() => void>();

function publish() {
  listeners.forEach((l) => l());
}

// Takes the backend's lighting unless an edit is pending or in flight (that edit is newer).
export function syncLighting(s: State) {
  if (timer !== undefined || writing > 0) return;
  draft = s.lighting;
  publish();
}

function change(patch: Partial<Omit<LightingState, "enabled">>) {
  if (!draft) return;
  const next = { ...draft, ...patch };
  draft = next;
  publish();
  window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    timer = undefined;
    writing++;
    setLighting(next.effect, next.color, next.brightness)
      .then(() => (error = null))
      .catch((e) => (error = errorText(e)))
      .finally(() => {
        writing--;
        publish();
      });
  }, DEBOUNCE_MS);
}

// The switch flips at once; a refusal puts back what the backend has.
function setEnabled(on: boolean) {
  if (!draft) return;
  draft = { ...draft, enabled: on };
  publish();
  writing++;
  setLightingEnabled(on)
    .then(() => (error = null))
    .catch((e) => {
      error = errorText(e);
      return getState().then((s) => {
        if (draft) draft = { ...draft, enabled: s.lighting.enabled };
      });
    })
    .finally(() => {
      writing--;
      publish();
    });
}

function setExpanded(open: boolean) {
  expanded = open;
  publish();
}

export function useLighting() {
  const [, rerender] = useState(0);
  useEffect(() => {
    const listener = () => rerender((n) => n + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return { draft, error, expanded, change, setEnabled, setExpanded };
}
